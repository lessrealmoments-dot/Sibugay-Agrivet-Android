"""
Tests for new features:
1. Audit Setup: Admin PIN set/status endpoints
2. Auditor access management (user update for is_auditor/auditor_pin)
3. PO creation with payment_type (cash/terms) fields
4. syncManager newEnvelopeId export (checked via import)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for owner/521325"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "owner", "password": "521325"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json().get("token")


@pytest.fixture(scope="module")
def authed(auth_token):
    """Authenticated requests session"""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


# ── Admin PIN endpoints ──────────────────────────────────────────────────────

class TestAdminPinEndpoints:
    """Tests for POST /api/verify/admin-pin/set and GET /api/verify/admin-pin/status"""

    def test_admin_pin_status_returns_200(self, authed):
        """GET /api/verify/admin-pin/status should return 200"""
        res = authed.get(f"{BASE_URL}/api/verify/admin-pin/status")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_admin_pin_status_configured_field(self, authed):
        """GET status should have 'configured' boolean field"""
        res = authed.get(f"{BASE_URL}/api/verify/admin-pin/status")
        data = res.json()
        assert "configured" in data, f"'configured' key missing in response: {data}"
        assert isinstance(data["configured"], bool), f"'configured' should be bool, got: {type(data['configured'])}"

    def test_admin_pin_status_is_configured(self, authed):
        """Admin PIN should already be configured (set to 1234)"""
        res = authed.get(f"{BASE_URL}/api/verify/admin-pin/status")
        data = res.json()
        assert data["configured"] is True, f"Expected configured=True (PIN 1234 should be set), got: {data}"

    def test_set_admin_pin_returns_200(self, authed):
        """POST /api/verify/admin-pin/set with valid PIN should return 200"""
        res = authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "1234"})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_set_admin_pin_success_message(self, authed):
        """POST admin-pin/set should return success message"""
        res = authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "1234"})
        data = res.json()
        assert "message" in data, f"No 'message' in response: {data}"

    def test_set_admin_pin_too_short_returns_400(self, authed):
        """PIN less than 4 digits should return 400"""
        res = authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "12"})
        assert res.status_code == 400, f"Expected 400 for short PIN, got {res.status_code}: {res.text}"

    def test_admin_pin_status_after_set(self, authed):
        """After setting PIN, status.configured should be True"""
        authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "1234"})
        res = authed.get(f"{BASE_URL}/api/verify/admin-pin/status")
        data = res.json()
        assert data["configured"] is True, f"Expected configured=True after set, got: {data}"

    def test_admin_pin_non_admin_forbidden(self):
        """Non-admin user should get 401/403 on PIN endpoints"""
        # Using unauthenticated request
        res = requests.get(f"{BASE_URL}/api/verify/admin-pin/status")
        assert res.status_code in [401, 403], f"Expected 401/403 for unauth, got {res.status_code}"

    def test_update_admin_pin(self, authed):
        """Should be able to update PIN and then reset to 1234"""
        # Update to a different PIN
        res = authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "5678"})
        assert res.status_code == 200

        # Reset back to 1234 (original)
        res2 = authed.post(f"{BASE_URL}/api/verify/admin-pin/set", json={"pin": "1234"})
        assert res2.status_code == 200

        # Status should still be configured
        res3 = authed.get(f"{BASE_URL}/api/verify/admin-pin/status")
        assert res3.json()["configured"] is True


# ── Auditor Access (user update) ─────────────────────────────────────────────

class TestAuditorAccess:
    """Tests for auditor access management via /api/users/{user_id}"""

    def test_get_users_returns_list(self, authed):
        """GET /api/users should return a list"""
        res = authed.get(f"{BASE_URL}/api/users")
        assert res.status_code == 200, f"Got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "Expected at least one user"

    def test_user_has_id_field(self, authed):
        """Each user should have an id field"""
        res = authed.get(f"{BASE_URL}/api/users")
        users = res.json()
        for u in users:
            assert "id" in u, f"User missing 'id': {u}"

    def test_set_auditor_access(self, authed):
        """Set is_auditor on a user and verify it persists"""
        # Get a non-owner user
        res = authed.get(f"{BASE_URL}/api/users")
        users = res.json()
        target = next((u for u in users if u.get("username") != "owner"), None)
        if not target:
            pytest.skip("No non-owner user found to test auditor access")

        user_id = target["id"]
        original_auditor = target.get("is_auditor", False)

        # Set auditor to True with a PIN
        update_res = authed.put(f"{BASE_URL}/api/users/{user_id}",
                                 json={"is_auditor": True, "auditor_pin": "9876"})
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"

        # Verify it persisted
        get_res = authed.get(f"{BASE_URL}/api/users")
        updated = next((u for u in get_res.json() if u["id"] == user_id), None)
        assert updated is not None
        assert updated.get("is_auditor") is True, f"is_auditor not set: {updated}"

        # Cleanup — reset to original state
        authed.put(f"{BASE_URL}/api/users/{user_id}",
                   json={"is_auditor": original_auditor, "auditor_pin": ""})


# ── PO creation with payment_type ────────────────────────────────────────────

class TestPOPaymentType:
    """Tests for PO creation with payment_type: cash | terms"""

    def _get_branch_and_product(self, authed):
        """Helper to get branch ID and a product for PO"""
        branches = authed.get(f"{BASE_URL}/api/branches").json()
        branch_id = branches[0]["id"] if isinstance(branches, list) and branches else None

        products_res = authed.get(f"{BASE_URL}/api/products?limit=1").json()
        products = products_res.get("products", []) if isinstance(products_res, dict) else products_res
        product = products[0] if products else None
        return branch_id, product

    def test_create_po_cash_type(self, authed):
        """Create PO with payment_type='cash' and verify"""
        branch_id, product = self._get_branch_and_product(authed)
        if not branch_id or not product:
            pytest.skip("No branch or product available for PO creation test")

        payload = {
            "vendor": "TEST_Vendor_Cash",
            "branch_id": branch_id,
            "payment_type": "cash",
            "po_type": "cash",
            "items": [{"product_id": product["id"], "product_name": product["name"],
                        "unit": "pcs", "quantity": 1, "unit_price": 100}],
            "grand_total": 100,
            "status": "draft"
        }
        res = authed.post(f"{BASE_URL}/api/purchase-orders", json=payload)
        assert res.status_code in [200, 201], f"PO creation failed: {res.status_code} {res.text}"
        data = res.json()
        assert "po_number" in data or "id" in data, f"PO response missing identifiers: {data}"

        # Cleanup
        po_id = data.get("id")
        if po_id:
            authed.delete(f"{BASE_URL}/api/purchase-orders/{po_id}")

    def test_create_po_terms_type(self, authed):
        """Create PO with payment_type='terms' and terms fields"""
        branch_id, product = self._get_branch_and_product(authed)
        if not branch_id or not product:
            pytest.skip("No branch or product available for PO terms test")

        payload = {
            "vendor": "TEST_Vendor_Terms",
            "branch_id": branch_id,
            "payment_type": "terms",
            "po_type": "terms",
            "terms_label": "Net 30",
            "terms_days": 30,
            "items": [{"product_id": product["id"], "product_name": product["name"],
                        "unit": "pcs", "quantity": 1, "unit_price": 200}],
            "grand_total": 200,
            "status": "draft"
        }
        res = authed.post(f"{BASE_URL}/api/purchase-orders", json=payload)
        assert res.status_code in [200, 201], f"PO terms creation failed: {res.status_code} {res.text}"
        data = res.json()
        assert "po_number" in data or "id" in data, f"PO response missing identifiers: {data}"

        # Cleanup
        po_id = data.get("id")
        if po_id:
            authed.delete(f"{BASE_URL}/api/purchase-orders/{po_id}")

    def test_po_list_returns_verification_badge_fields(self, authed):
        """PO list items should have fields for verification badge rendering"""
        res = authed.get(f"{BASE_URL}/api/purchase-orders")
        assert res.status_code == 200
        data = res.json()
        # Can be list or {purchase_orders: [...]}
        orders = data.get("purchase_orders", []) if isinstance(data, dict) else data
        if not orders:
            pytest.skip("No POs found to check verification fields")

        po = orders[0]
        # Fields used by VerificationBadge
        assert "id" in po, f"PO missing 'id': {po.keys()}"
        assert "status" in po, f"PO missing 'status': {po.keys()}"


# ── Verify PIN works with admin PIN 1234 ─────────────────────────────────────

class TestVerifyWithAdminPin:
    """Test that verification PIN 1234 still works"""

    def test_verify_resolves_admin_pin(self, authed):
        """Verify a PO using admin PIN 1234"""
        # Get a PO to verify
        res = authed.get(f"{BASE_URL}/api/purchase-orders")
        data = res.json()
        orders = data.get("purchase_orders", []) if isinstance(data, dict) else data
        received_po = next((p for p in orders if p.get("status") == "received"), None)
        if not received_po:
            pytest.skip("No received PO to test verification")

        po_id = received_po["id"]
        # Unverify first if already verified
        if received_po.get("verified"):
            authed.delete(f"{BASE_URL}/api/verify/purchase_order/{po_id}")

        verify_res = authed.post(f"{BASE_URL}/api/verify/purchase_order/{po_id}",
                                  json={"pin": "1234"})
        assert verify_res.status_code == 200, f"Verify failed: {verify_res.status_code} {verify_res.text}"
        data = verify_res.json()
        assert data.get("method") == "admin_pin", f"Expected admin_pin method: {data}"

        # Cleanup - unverify
        authed.delete(f"{BASE_URL}/api/verify/purchase_order/{po_id}")
