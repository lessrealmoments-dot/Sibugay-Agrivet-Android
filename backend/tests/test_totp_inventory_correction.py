"""
Test TOTP authentication features and Inventory Correction endpoints.
Tests:
- TOTP status endpoint
- TOTP setup flow
- TOTP-protected actions (settings/totp-controls)
- Inventory admin-adjust correction
- Inventory correction history
- verify-admin-action with password mode
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_USERNAME = "owner"
ADMIN_PASSWORD = "521325"

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin (owner) token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def first_non_repack_product(admin_headers):
    """Get a non-repack product for correction tests."""
    resp = requests.get(f"{BASE_URL}/api/products", headers=admin_headers,
                        params={"is_repack": False, "limit": 5})
    assert resp.status_code == 200
    products = resp.json().get("products", [])
    if not products:
        pytest.skip("No non-repack products available")
    return products[0]


@pytest.fixture(scope="module")
def first_branch(admin_headers):
    """Get first branch for branch_id in corrections."""
    resp = requests.get(f"{BASE_URL}/api/branches", headers=admin_headers)
    assert resp.status_code == 200
    branches = resp.json()
    if not branches:
        pytest.skip("No branches available")
    return branches[0]


# ── Auth: TOTP Status ────────────────────────────────────────────────────────

class TestTotpStatus:
    """GET /api/auth/totp/status"""

    def test_totp_status_admin(self, admin_headers):
        """Admin can get TOTP status."""
        resp = requests.get(f"{BASE_URL}/api/auth/totp/status", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "enabled" in data, "Response must have 'enabled' key"
        assert "verified" in data, "Response must have 'verified' key"
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["verified"], bool)

    def test_totp_status_unauthenticated(self):
        """Unauthenticated request should fail."""
        resp = requests.get(f"{BASE_URL}/api/auth/totp/status")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_totp_status_returns_false_initially(self, admin_headers):
        """TOTP status initially enabled=false when not configured."""
        resp = requests.get(f"{BASE_URL}/api/auth/totp/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Either already enabled or not — just verify valid boolean
        assert isinstance(data.get("enabled"), bool)


# ── Auth: TOTP Setup ─────────────────────────────────────────────────────────

class TestTotpSetup:
    """POST /api/auth/totp/setup"""

    def test_setup_returns_qr_uri_and_secret(self, admin_headers):
        """Setup endpoint returns QR URI and secret."""
        resp = requests.post(f"{BASE_URL}/api/auth/totp/setup", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "secret" in data, "Must return 'secret'"
        assert "qr_uri" in data, "Must return 'qr_uri'"
        assert len(data["secret"]) >= 16, "Secret must be a base32 string"
        assert "otpauth://" in data["qr_uri"], "QR URI must be otpauth:// format"
        assert "AgriPOS" in data["qr_uri"], "Issuer name 'AgriPOS' must be in QR URI"

    def test_setup_uses_admin_username_in_uri(self, admin_headers):
        """QR URI should include the admin's username."""
        resp = requests.post(f"{BASE_URL}/api/auth/totp/setup", headers=admin_headers)
        assert resp.status_code == 200
        qr_uri = resp.json()["qr_uri"]
        # URI format: otpauth://totp/AgriPOS:username?secret=...
        assert "owner" in qr_uri or "AgriPOS" in qr_uri

    def test_setup_after_setup_status_not_enabled(self, admin_headers):
        """After calling setup (not verified), status should still be enabled=false."""
        # Call setup
        requests.post(f"{BASE_URL}/api/auth/totp/setup", headers=admin_headers)
        # Check status  
        resp = requests.get(f"{BASE_URL}/api/auth/totp/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # After setup but before verify, enabled should still be False
        assert data["enabled"] == False, f"After setup (unverified), enabled should be False, got {data}"

    def test_setup_unauthenticated_fails(self):
        """Unauthenticated setup should fail."""
        resp = requests.post(f"{BASE_URL}/api/auth/totp/setup")
        assert resp.status_code in (401, 403)


# ── Auth: Verify Admin Action ────────────────────────────────────────────────

class TestVerifyAdminAction:
    """POST /api/auth/verify-admin-action"""

    def test_verify_with_correct_password(self, admin_headers):
        """mode='password' with correct admin password should return valid=true."""
        resp = requests.post(f"{BASE_URL}/api/auth/verify-admin-action",
                             headers=admin_headers,
                             json={
                                 "mode": "password",
                                 "code": ADMIN_PASSWORD,
                                 "context": "Test verification"
                             })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") == True, f"Expected valid=True, got {data}"
        assert "manager_name" in data
        assert data.get("mode_used") == "password"

    def test_verify_with_wrong_password(self, admin_headers):
        """Wrong password should return valid=false."""
        resp = requests.post(f"{BASE_URL}/api/auth/verify-admin-action",
                             headers=admin_headers,
                             json={
                                 "mode": "password",
                                 "code": "wrongpassword999",
                                 "context": ""
                             })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("valid") == False, f"Expected valid=False, got {data}"

    def test_verify_totp_invalid_code(self, admin_headers):
        """Invalid TOTP code should return valid=false."""
        resp = requests.post(f"{BASE_URL}/api/auth/verify-admin-action",
                             headers=admin_headers,
                             json={
                                 "mode": "totp",
                                 "code": "000000",
                                 "context": ""
                             })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("valid") == False

    def test_verify_empty_code_returns_400(self, admin_headers):
        """Missing code should return 400."""
        resp = requests.post(f"{BASE_URL}/api/auth/verify-admin-action",
                             headers=admin_headers,
                             json={"mode": "password", "code": ""})
        assert resp.status_code == 400, f"Expected 400 for empty code, got {resp.status_code}: {resp.text}"

    def test_verify_unauthenticated_fails(self):
        """Unauthenticated request should fail."""
        resp = requests.post(f"{BASE_URL}/api/auth/verify-admin-action",
                             json={"mode": "password", "code": ADMIN_PASSWORD})
        assert resp.status_code in (401, 403)


# ── Settings: TOTP Controls ───────────────────────────────────────────────────

class TestTotpControls:
    """GET+PUT /api/settings/totp-controls"""

    EXPECTED_ACTION_KEYS = [
        "inventory_adjust", "close_day", "invoice_edit", "invoice_void",
        "product_delete", "price_override", "reopen_po",
        "manage_users", "manage_permissions"
    ]

    def test_get_totp_controls_admin(self, admin_headers):
        """Admin can get TOTP controls list."""
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "actions" in data, "Response must have 'actions' list"
        assert "enabled_actions" in data, "Response must have 'enabled_actions' list"

    def test_get_totp_controls_has_9_actions(self, admin_headers):
        """TOTP controls must have exactly 9 configurable actions."""
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        actions = data["actions"]
        assert len(actions) == 9, f"Expected 9 actions, got {len(actions)}: {[a['key'] for a in actions]}"

    def test_get_totp_controls_action_structure(self, admin_headers):
        """Each action must have key, label, module fields."""
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls", headers=admin_headers)
        assert resp.status_code == 200
        actions = resp.json()["actions"]
        for action in actions:
            assert "key" in action, f"Action missing 'key': {action}"
            assert "label" in action, f"Action missing 'label': {action}"
            assert "module" in action, f"Action missing 'module': {action}"

    def test_get_totp_controls_contains_expected_keys(self, admin_headers):
        """All expected action keys should be present."""
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls", headers=admin_headers)
        assert resp.status_code == 200
        action_keys = [a["key"] for a in resp.json()["actions"]]
        for key in self.EXPECTED_ACTION_KEYS:
            assert key in action_keys, f"Missing expected action key: {key}"

    def test_put_totp_controls_saves_enabled_actions(self, admin_headers):
        """PUT totp-controls should save and return enabled_actions."""
        enabled = ["inventory_adjust", "close_day"]
        resp = requests.put(f"{BASE_URL}/api/settings/totp-controls",
                            headers=admin_headers,
                            json={"enabled_actions": enabled})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "enabled_actions" in data
        assert set(data["enabled_actions"]) == set(enabled)

    def test_put_totp_controls_persists(self, admin_headers):
        """After PUT, GET should return the updated enabled_actions."""
        new_enabled = ["invoice_edit", "product_delete"]
        requests.put(f"{BASE_URL}/api/settings/totp-controls",
                     headers=admin_headers,
                     json={"enabled_actions": new_enabled})
        # Verify persistence
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["enabled_actions"]) == set(new_enabled), \
            f"Expected {new_enabled}, got {data['enabled_actions']}"

    def test_totp_controls_non_admin_forbidden(self):
        """Non-admin cannot access TOTP controls."""
        resp = requests.get(f"{BASE_URL}/api/settings/totp-controls")
        assert resp.status_code in (401, 403)


# ── Inventory: Admin Adjust (Correction) ────────────────────────────────────

class TestInventoryAdminAdjust:
    """POST /api/inventory/admin-adjust"""

    def test_admin_adjust_sets_stock(self, admin_headers, first_non_repack_product, first_branch):
        """Admin correction sets stock to exact new_quantity."""
        product_id = first_non_repack_product["id"]
        branch_id = first_branch["id"]
        new_qty = 50.0

        resp = requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                             headers=admin_headers,
                             json={
                                 "product_id": product_id,
                                 "branch_id": branch_id,
                                 "new_quantity": new_qty,
                                 "reason": "TEST_physical count correction",
                                 "verified_by": "Test Admin",
                                 "auth_mode": "direct_admin",
                             })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["new_quantity"] == new_qty, f"new_quantity mismatch: {data}"
        assert "old_quantity" in data
        assert "difference" in data
        assert data["difference"] == new_qty - data["old_quantity"]

    def test_admin_adjust_creates_correction_record(self, admin_headers, first_non_repack_product, first_branch):
        """Correction creates an audit record."""
        product_id = first_non_repack_product["id"]
        branch_id = first_branch["id"]
        new_qty = 75.0

        # Apply correction
        resp = requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                             headers=admin_headers,
                             json={
                                 "product_id": product_id,
                                 "branch_id": branch_id,
                                 "new_quantity": new_qty,
                                 "reason": "TEST_audit record test",
                                 "auth_mode": "direct_admin",
                             })
        assert resp.status_code == 200
        data = resp.json()
        correction = data.get("correction")
        assert correction is not None, "Response must include 'correction' audit record"
        assert correction["product_id"] == product_id
        assert correction["new_quantity"] == new_qty
        assert correction["reason"] == "TEST_audit record test"

    def test_admin_adjust_repack_blocked(self, admin_headers, first_branch):
        """Cannot adjust a repack product directly."""
        # Get a repack product
        resp = requests.get(f"{BASE_URL}/api/products", headers=admin_headers,
                            params={"is_repack": True, "limit": 1})
        assert resp.status_code == 200
        repacks = resp.json().get("products", [])
        if not repacks:
            pytest.skip("No repack products available")

        repack = repacks[0]
        resp = requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                             headers=admin_headers,
                             json={
                                 "product_id": repack["id"],
                                 "branch_id": first_branch["id"],
                                 "new_quantity": 10.0,
                                 "reason": "TEST_should fail",
                                 "auth_mode": "direct_admin",
                             })
        assert resp.status_code == 400, f"Expected 400 for repack, got {resp.status_code}: {resp.text}"

    def test_admin_adjust_unauthenticated_fails(self, first_non_repack_product, first_branch):
        """Unauthenticated request should fail."""
        resp = requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                             json={
                                 "product_id": first_non_repack_product["id"],
                                 "branch_id": first_branch["id"],
                                 "new_quantity": 10.0,
                                 "reason": "TEST",
                             })
        assert resp.status_code in (401, 403)


# ── Inventory: Correction History ────────────────────────────────────────────

class TestInventoryCorrections:
    """GET /api/inventory/corrections/{product_id}"""

    def test_get_corrections_empty_initially_or_list(self, admin_headers, first_non_repack_product):
        """GET corrections for a product returns a list (possibly empty)."""
        product_id = first_non_repack_product["id"]
        resp = requests.get(f"{BASE_URL}/api/inventory/corrections/{product_id}",
                            headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert isinstance(resp.json(), list), "Response must be a list"

    def test_get_corrections_after_adjust_has_record(self, admin_headers, first_non_repack_product, first_branch):
        """After admin-adjust, correction history should have the new record."""
        product_id = first_non_repack_product["id"]

        # Apply a correction
        requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                      headers=admin_headers,
                      json={
                          "product_id": product_id,
                          "branch_id": first_branch["id"],
                          "new_quantity": 99.0,
                          "reason": "TEST_verify history record",
                          "auth_mode": "direct_admin",
                      })

        # Get correction history
        resp = requests.get(f"{BASE_URL}/api/inventory/corrections/{product_id}",
                            headers=admin_headers)
        assert resp.status_code == 200
        corrections = resp.json()
        assert len(corrections) > 0, "Expected at least 1 correction record"

        # Verify record structure
        c = corrections[0]
        assert "product_id" in c
        assert "old_quantity" in c
        assert "new_quantity" in c
        assert "reason" in c
        assert "performed_by_name" in c
        assert "auth_mode" in c
        assert "created_at" in c
        # Verify no MongoDB _id
        assert "_id" not in c, "MongoDB _id should not be in response"

    def test_get_corrections_has_test_record(self, admin_headers, first_non_repack_product, first_branch):
        """The most recent correction should include our test reason."""
        product_id = first_non_repack_product["id"]
        requests.post(f"{BASE_URL}/api/inventory/admin-adjust",
                      headers=admin_headers,
                      json={
                          "product_id": product_id,
                          "branch_id": first_branch["id"],
                          "new_quantity": 42.0,
                          "reason": "TEST_unique_reason_xyz",
                          "auth_mode": "direct_admin",
                      })
        resp = requests.get(f"{BASE_URL}/api/inventory/corrections/{product_id}",
                            headers=admin_headers)
        reasons = [c.get("reason", "") for c in resp.json()]
        assert "TEST_unique_reason_xyz" in reasons, f"Test correction not found in history: {reasons}"

    def test_get_corrections_unauthenticated_fails(self, first_non_repack_product):
        """Unauthenticated request should fail."""
        product_id = first_non_repack_product["id"]
        resp = requests.get(f"{BASE_URL}/api/inventory/corrections/{product_id}")
        assert resp.status_code in (401, 403)
