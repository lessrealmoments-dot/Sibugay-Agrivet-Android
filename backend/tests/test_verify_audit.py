"""
Test suite for Transaction Verification System, Audit Center (offline-package),
and Upload view-session endpoints.

Features tested:
- /api/verify/admin-pin/set and /api/verify/admin-pin/status
- /api/verify/{doc_type}/{doc_id} (verify transaction)
- /api/verify/discrepancies
- /api/verify/discrepancies/{id}/resolve
- /api/audit/offline-package
- /api/uploads/generate-view-token
- /api/uploads/view-session/{token}

Run with:
  pytest /app/backend/tests/test_verify_audit.py -v --tb=short \
    --junitxml=/app/test_reports/pytest/pytest_verify_audit.xml
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_PIN = "1234"


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Authenticate as admin (owner/521325) and return JWT."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner", "password": "521325"
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    tok = res.json().get("token")
    assert tok, "No token in response"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def cashier_token():
    """Authenticate as cashier (cashier/1234) and return JWT."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "cashier", "password": "1234"
    })
    assert res.status_code == 200, f"Cashier login failed: {res.text}"
    tok = res.json().get("token")
    assert tok, "No token in response"
    return tok


@pytest.fixture(scope="module")
def cashier_headers(cashier_token):
    return {"Authorization": f"Bearer {cashier_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def first_branch_id(admin_headers):
    """Get the first available branch ID for tests."""
    res = requests.get(f"{BASE_URL}/api/branches", headers=admin_headers)
    if res.status_code == 200:
        branches = res.json().get("branches", res.json() if isinstance(res.json(), list) else [])
        if branches:
            return branches[0].get("id", "")
    return ""


@pytest.fixture(scope="module")
def first_po_id(admin_headers):
    """Get the first available purchase order ID for tests."""
    res = requests.get(f"{BASE_URL}/api/purchase-orders", headers=admin_headers)
    if res.status_code == 200:
        data = res.json()
        pos = data.get("purchase_orders", data if isinstance(data, list) else [])
        if pos:
            return pos[0].get("id", "")
    return ""


@pytest.fixture(scope="module")
def first_expense_id(admin_headers):
    """Get the first available expense ID for tests."""
    res = requests.get(f"{BASE_URL}/api/accounting/expenses", headers=admin_headers)
    if res.status_code == 200:
        data = res.json()
        expenses = data.get("expenses", data if isinstance(data, list) else [])
        if expenses:
            return expenses[0].get("id", "")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
#  1. Admin PIN Management
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminPIN:
    """Tests for admin PIN setup and status endpoints."""

    def test_admin_pin_set_requires_admin(self, cashier_headers):
        """Non-admin should get 403 when trying to set admin PIN."""
        res = requests.post(f"{BASE_URL}/api/verify/admin-pin/set",
                            json={"pin": "9999"}, headers=cashier_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        print("PASS: Non-admin blocked from setting admin PIN")

    def test_admin_pin_set_short_pin_rejected(self, admin_headers):
        """PIN less than 4 digits should be rejected."""
        res = requests.post(f"{BASE_URL}/api/verify/admin-pin/set",
                            json={"pin": "12"}, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400 for short PIN, got {res.status_code}: {res.text}"
        print("PASS: Short PIN rejected")

    def test_admin_pin_set_success(self, admin_headers):
        """Admin can set/update PIN successfully."""
        res = requests.post(f"{BASE_URL}/api/verify/admin-pin/set",
                            json={"pin": ADMIN_PIN}, headers=admin_headers)
        assert res.status_code == 200, f"Set PIN failed: {res.text}"
        data = res.json()
        assert "message" in data
        assert "success" in data["message"].lower() or "set" in data["message"].lower()
        print(f"PASS: Admin PIN set successfully. Message: {data['message']}")

    def test_admin_pin_status_is_configured(self, admin_headers):
        """After setting PIN, status should report configured=true."""
        res = requests.get(f"{BASE_URL}/api/verify/admin-pin/status", headers=admin_headers)
        assert res.status_code == 200, f"Status check failed: {res.text}"
        data = res.json()
        assert data.get("configured") is True, f"PIN should be configured, got: {data}"
        print("PASS: Admin PIN status shows configured=true")

    def test_admin_pin_status_requires_admin(self, cashier_headers):
        """Non-admin should get 403 for PIN status."""
        res = requests.get(f"{BASE_URL}/api/verify/admin-pin/status", headers=cashier_headers)
        assert res.status_code == 403
        print("PASS: Non-admin blocked from PIN status")


# ─────────────────────────────────────────────────────────────────────────────
#  2. Transaction Verification
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyTransaction:
    """Tests for verifying transactions (POs, expenses) via PIN."""

    def test_verify_invalid_doc_type(self, admin_headers):
        """Invalid doc_type should return 400."""
        res = requests.post(f"{BASE_URL}/api/verify/unknown_type/some_id",
                            json={"pin": ADMIN_PIN}, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400 for invalid doc_type, got {res.status_code}: {res.text}"
        data = res.json()
        assert "detail" in data
        print(f"PASS: Invalid doc_type returns 400: {data['detail']}")

    def test_verify_nonexistent_doc(self, admin_headers):
        """Verifying a non-existent doc_id should return 404."""
        res = requests.post(f"{BASE_URL}/api/verify/purchase_order/NONEXISTENT_ID_9999",
                            json={"pin": ADMIN_PIN}, headers=admin_headers)
        assert res.status_code == 404, f"Expected 404 for missing doc, got {res.status_code}: {res.text}"
        print("PASS: Non-existent doc_id returns 404")

    def test_verify_wrong_pin(self, admin_headers, first_po_id):
        """Wrong PIN should return 401."""
        if not first_po_id:
            pytest.skip("No purchase orders available to test")
        res = requests.post(f"{BASE_URL}/api/verify/purchase_order/{first_po_id}",
                            json={"pin": "0000"}, headers=admin_headers)
        assert res.status_code == 401, f"Expected 401 for wrong PIN, got {res.status_code}: {res.text}"
        data = res.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower() or "not recognized" in data["detail"].lower()
        print(f"PASS: Wrong PIN returns 401: {data['detail']}")

    def test_verify_purchase_order_success(self, admin_headers, first_po_id):
        """Valid admin PIN should verify a PO successfully."""
        if not first_po_id:
            pytest.skip("No purchase orders available to test")
        res = requests.post(f"{BASE_URL}/api/verify/purchase_order/{first_po_id}",
                            json={"pin": ADMIN_PIN, "has_discrepancy": False},
                            headers=admin_headers)
        assert res.status_code == 200, f"Verification failed: {res.text}"
        data = res.json()
        assert data.get("verified_by"), f"No verifier info in response: {data}"
        assert "method" in data, f"No method in response: {data}"
        assert data["status"] == "clean", f"Expected status=clean, got: {data}"
        print(f"PASS: PO verified by {data['verified_by']} via {data['method']}")

    def test_verify_po_shows_verified_badge(self, admin_headers, first_po_id):
        """After verification, PO should show verified=True in data."""
        if not first_po_id:
            pytest.skip("No purchase orders available to test")
        # Fetch the PO detail to check verified status
        # First, get PO list to find the specific PO
        res = requests.get(f"{BASE_URL}/api/purchase-orders", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        pos = data.get("purchase_orders", data if isinstance(data, list) else [])
        verified_po = next((p for p in pos if p.get("id") == first_po_id), None)
        if verified_po:
            assert verified_po.get("verified") is True, f"PO should be verified, got: {verified_po.get('verified')}"
            assert verified_po.get("verified_by_name"), "Should have verifier name"
            print(f"PASS: PO shows verified=True, by: {verified_po.get('verified_by_name')}")
        else:
            print("INFO: PO not found in list (may be filtered by branch) — skipping badge check")

    def test_verify_with_discrepancy(self, admin_headers, first_expense_id):
        """Verify with discrepancy flag creates a discrepancy log entry."""
        if not first_expense_id:
            pytest.skip("No expenses available to test")
        res = requests.post(f"{BASE_URL}/api/verify/expense/{first_expense_id}",
                            json={
                                "pin": ADMIN_PIN,
                                "has_discrepancy": True,
                                "discrepancy_note": "TEST: Physical receipt shows different amount",
                                "item_description": "Office supplies TEST",
                                "expected_qty": 10.0,
                                "found_qty": 8.0,
                                "unit": "pcs",
                                "unit_cost": 100.0,
                            },
                            headers=admin_headers)
        assert res.status_code == 200, f"Verification with discrepancy failed: {res.text}"
        data = res.json()
        assert data.get("status") == "discrepancy", f"Expected discrepancy status, got: {data}"
        print(f"PASS: Expense verified with discrepancy: {data}")

    def test_unverify_requires_admin(self, cashier_headers, first_po_id):
        """Non-admin should not be able to unverify a transaction."""
        if not first_po_id:
            pytest.skip("No purchase orders available to test")
        res = requests.delete(f"{BASE_URL}/api/verify/purchase_order/{first_po_id}",
                              headers=cashier_headers)
        assert res.status_code == 403
        print("PASS: Non-admin blocked from unverify")

    def test_unverify_purchase_order(self, admin_headers, first_po_id):
        """Admin can remove verification from a PO."""
        if not first_po_id:
            pytest.skip("No purchase orders available to test")
        res = requests.delete(f"{BASE_URL}/api/verify/purchase_order/{first_po_id}",
                              headers=admin_headers)
        assert res.status_code == 200, f"Unverify failed: {res.text}"
        data = res.json()
        assert "removed" in data["message"].lower() or "verification" in data["message"].lower()
        print(f"PASS: PO unverified: {data['message']}")


# ─────────────────────────────────────────────────────────────────────────────
#  3. Discrepancies
# ─────────────────────────────────────────────────────────────────────────────

class TestDiscrepancies:
    """Tests for the discrepancy log endpoints."""

    def test_list_discrepancies_requires_auth(self):
        """Unauthenticated request should fail."""
        res = requests.get(f"{BASE_URL}/api/verify/discrepancies")
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("PASS: Unauthenticated discrepancy list blocked")

    def test_list_discrepancies_admin(self, admin_headers):
        """Admin can list discrepancies."""
        res = requests.get(f"{BASE_URL}/api/verify/discrepancies", headers=admin_headers)
        assert res.status_code == 200, f"List discrepancies failed: {res.text}"
        data = res.json()
        assert "discrepancies" in data
        assert "total" in data
        assert isinstance(data["discrepancies"], list)
        print(f"PASS: Discrepancies list returned {data['total']} entries")

    def test_list_discrepancies_filter_resolved(self, admin_headers):
        """Filtering by resolved=false should work."""
        res = requests.get(f"{BASE_URL}/api/verify/discrepancies?resolved=false",
                           headers=admin_headers)
        assert res.status_code == 200, f"Filter failed: {res.text}"
        data = res.json()
        # All returned entries should not be resolved
        for d in data["discrepancies"]:
            assert d.get("resolved") is False, f"Expected unresolved, got: {d}"
        print(f"PASS: Filtered discrepancies (unresolved): {data['total']} entries")

    def test_list_discrepancies_cashier(self, cashier_headers):
        """Cashier can also list discrepancies (filtered to their branch)."""
        res = requests.get(f"{BASE_URL}/api/verify/discrepancies", headers=cashier_headers)
        assert res.status_code == 200, f"Cashier discrepancy list failed: {res.text}"
        data = res.json()
        assert "discrepancies" in data
        print(f"PASS: Cashier can view discrepancies: {data['total']} entries")

    def test_resolve_nonexistent_discrepancy(self, admin_headers):
        """Resolving a non-existent discrepancy returns 404."""
        res = requests.post(f"{BASE_URL}/api/verify/discrepancies/NONEXISTENT_9999/resolve",
                            json={"action": "dismiss", "justification": "test"},
                            headers=admin_headers)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"
        print("PASS: Non-existent discrepancy resolve returns 404")

    def test_resolve_existing_discrepancy_if_any(self, admin_headers):
        """If any unresolved discrepancies exist, try to resolve one."""
        res = requests.get(f"{BASE_URL}/api/verify/discrepancies?resolved=false",
                           headers=admin_headers)
        assert res.status_code == 200
        discs = res.json().get("discrepancies", [])
        if not discs:
            print("INFO: No unresolved discrepancies to resolve, skipping")
            return

        disc_id = discs[0]["id"]
        resolve_res = requests.post(
            f"{BASE_URL}/api/verify/discrepancies/{disc_id}/resolve",
            json={"action": "dismiss", "justification": "TEST: Verified during testing"},
            headers=admin_headers,
        )
        assert resolve_res.status_code == 200, f"Resolve failed: {resolve_res.text}"
        data = resolve_res.json()
        assert "message" in data
        assert "dismiss" in data["message"].lower()
        print(f"PASS: Discrepancy {disc_id} resolved: {data['message']}")


# ─────────────────────────────────────────────────────────────────────────────
#  4. Audit Offline Package
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditOfflinePackage:
    """Tests for /api/audit/offline-package endpoint."""

    def test_offline_package_requires_auth(self):
        """Unauthenticated request should fail."""
        res = requests.get(f"{BASE_URL}/api/audit/offline-package")
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("PASS: Unauthenticated offline package blocked")

    def test_offline_package_admin(self, admin_headers, first_branch_id):
        """Admin can fetch the offline package."""
        params = {}
        if first_branch_id:
            params["branch_id"] = first_branch_id
        res = requests.get(f"{BASE_URL}/api/audit/offline-package",
                           headers=admin_headers, params=params)
        assert res.status_code == 200, f"Offline package failed: {res.text}"
        data = res.json()

        # Check required fields
        assert "purchase_orders" in data, "Missing purchase_orders"
        assert "expenses" in data, "Missing expenses"
        assert "branch_transfers" in data, "Missing branch_transfers"
        assert "totals" in data, "Missing totals"
        assert "uploads_map" in data, "Missing uploads_map"
        assert "file_urls" in data, "Missing file_urls"

        # Check totals structure
        totals = data["totals"]
        assert "purchase_orders" in totals
        assert "expenses" in totals
        assert "branch_transfers" in totals
        assert "total_files" in totals

        # Check that lists are actually lists
        assert isinstance(data["purchase_orders"], list)
        assert isinstance(data["expenses"], list)
        assert isinstance(data["branch_transfers"], list)

        print(f"PASS: Offline package OK. "
              f"POs={totals['purchase_orders']}, "
              f"Expenses={totals['expenses']}, "
              f"Transfers={totals['branch_transfers']}, "
              f"Files={totals['total_files']}")

    def test_offline_package_with_period(self, admin_headers, first_branch_id):
        """Offline package respects date period filters."""
        params = {"period_from": "2025-01-01", "period_to": "2025-12-31"}
        if first_branch_id:
            params["branch_id"] = first_branch_id
        res = requests.get(f"{BASE_URL}/api/audit/offline-package",
                           headers=admin_headers, params=params)
        assert res.status_code == 200, f"Offline package with period failed: {res.text}"
        data = res.json()
        assert data.get("period_from") == "2025-01-01"
        assert data.get("period_to") == "2025-12-31"
        print("PASS: Offline package respects period parameters")


# ─────────────────────────────────────────────────────────────────────────────
#  5. Upload View Token (generate-view-token + view-session)
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadViewToken:
    """Tests for the view-only QR token endpoints."""

    def test_generate_view_token_requires_record_type(self, admin_headers):
        """Missing record_type/record_id should return 400."""
        res = requests.post(f"{BASE_URL}/api/uploads/generate-view-token",
                            json={}, headers=admin_headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        print("PASS: Missing record_type/record_id returns 400")

    def test_generate_view_token_success(self, admin_headers, first_po_id):
        """Generating a view token for a PO returns a valid token."""
        if not first_po_id:
            pytest.skip("No purchase orders available")
        res = requests.post(f"{BASE_URL}/api/uploads/generate-view-token",
                            json={"record_type": "purchase_order", "record_id": first_po_id},
                            headers=admin_headers)
        assert res.status_code == 200, f"Generate view token failed: {res.text}"
        data = res.json()
        assert "token" in data, f"No token in response: {data}"
        assert "expires_at" in data
        assert len(data["token"]) > 10
        print(f"PASS: View token generated: {data['token'][:20]}...")
        return data["token"]

    def test_view_session_with_valid_token(self, admin_headers, first_po_id):
        """A valid view token returns session data with record info."""
        if not first_po_id:
            pytest.skip("No purchase orders available")
        # Generate a fresh token
        gen_res = requests.post(f"{BASE_URL}/api/uploads/generate-view-token",
                                json={"record_type": "purchase_order", "record_id": first_po_id},
                                headers=admin_headers)
        assert gen_res.status_code == 200
        token = gen_res.json()["token"]

        # Access the view session (no auth needed)
        view_res = requests.get(f"{BASE_URL}/api/uploads/view-session/{token}")
        assert view_res.status_code == 200, f"View session failed: {view_res.text}"
        data = view_res.json()
        assert "record_summary" in data
        assert "record_type" in data
        assert data["record_type"] == "purchase_order"
        assert "sessions" in data
        assert "total_files" in data
        assert "verification" in data
        print(f"PASS: View session returned OK. Files: {data['total_files']}, "
              f"record_type: {data['record_type']}")

    def test_view_session_with_invalid_token(self):
        """Invalid/expired token returns 404."""
        res = requests.get(f"{BASE_URL}/api/uploads/view-session/invalid_token_xyz_12345")
        assert res.status_code == 404, f"Expected 404 for invalid token, got {res.status_code}: {res.text}"
        print("PASS: Invalid view token returns 404")

    def test_view_session_shows_verification_status(self, admin_headers, first_po_id):
        """View session includes verification field."""
        if not first_po_id:
            pytest.skip("No purchase orders available")
        gen_res = requests.post(f"{BASE_URL}/api/uploads/generate-view-token",
                                json={"record_type": "purchase_order", "record_id": first_po_id},
                                headers=admin_headers)
        assert gen_res.status_code == 200
        token = gen_res.json()["token"]
        view_res = requests.get(f"{BASE_URL}/api/uploads/view-session/{token}")
        assert view_res.status_code == 200
        data = view_res.json()
        assert "verification" in data, "view-session must include verification field"
        # verification can be empty dict or have verified key
        assert isinstance(data["verification"], dict)
        print(f"PASS: view-session includes verification: {data['verification']}")
