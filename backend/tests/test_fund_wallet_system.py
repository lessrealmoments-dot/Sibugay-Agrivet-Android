"""
Fund Wallet System Tests — 4-wallet branch fund system
Tests:
  - GET /api/fund-wallets returns 4 wallets (cashier, safe, digital, bank)
  - Bank balance hidden from non-admin
  - Fund transfers: cashier_to_safe, safe_to_cashier, safe_to_bank, capital_add
  - Authorization: manager PIN, admin TOTP, admin role
  - Audit log (GET /api/fund-transfers)
  - Branch creation auto-provisions 4 wallets
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Known branch IDs from testing context
B1_BRANCH_ID = "7f9b29cb-3028-4680-b36c-cb8ad1c80345"
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"

OWNER_USER = "owner"
OWNER_PASS = "521325"
MANAGER_PIN = "521325"  # Owner user's manager_pin field (same as password)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Authenticate as owner and return bearer token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": OWNER_USER, "password": OWNER_PASS},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def cashier_token(auth_headers):
    """
    Create a temporary cashier user and return its token.
    Used to test non-admin bank balance hiding.
    """
    username = f"TEST_cashier_{uuid.uuid4().hex[:8]}"
    # Create user
    create_resp = requests.post(
        f"{BASE_URL}/api/users",
        json={
            "username": username,
            "password": "Test@12345",
            "full_name": "TEST Cashier User",
            "role": "cashier",
            "branch_id": B1_BRANCH_ID,
            "active": True,
        },
        headers=auth_headers,
    )
    if create_resp.status_code not in (200, 201):
        pytest.skip(f"Could not create cashier user: {create_resp.text}")

    # Login as cashier
    login_resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": "Test@12345"},
    )
    if login_resp.status_code != 200:
        pytest.skip(f"Cashier login failed: {login_resp.text}")

    data = login_resp.json()
    token = data.get("access_token") or data.get("token")
    user_id = create_resp.json().get("id", "")

    yield token, user_id, username

    # Cleanup: delete the test user
    if user_id:
        requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)


# ─── Fund Wallets Tests ───────────────────────────────────────────────────────

class TestFundWallets:
    """Tests for GET /api/fund-wallets"""

    def test_get_fund_wallets_returns_4_types(self, auth_headers):
        """GET /api/fund-wallets?branch_id=B1 must return 4 wallets: cashier, safe, digital, bank"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        wallets = resp.json()
        assert isinstance(wallets, list), "Response should be a list"

        types_found = {w["type"] for w in wallets}
        required_types = {"cashier", "safe", "digital", "bank"}
        assert required_types.issubset(types_found), (
            f"Missing wallet types: {required_types - types_found}. Found: {types_found}"
        )
        print(f"PASS: Found 4 wallet types — {types_found}")

    def test_get_fund_wallets_ipil_branch_returns_4_types(self, auth_headers):
        """IPIL branch also returns 4 wallet types"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        wallets = resp.json()
        types_found = {w["type"] for w in wallets}
        required = {"cashier", "safe", "digital", "bank"}
        missing = required - types_found
        assert not missing, f"Missing wallet types for IPIL: {missing}"
        print(f"PASS: IPIL branch has 4 wallet types — {types_found}")

    def test_admin_sees_bank_balance(self, auth_headers):
        """Admin (owner) should see bank wallet balance (not hidden)"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        wallets = resp.json()
        bank = next((w for w in wallets if w["type"] == "bank"), None)
        assert bank is not None, "Bank wallet not found"
        assert bank.get("balance_hidden") is not True, "Admin should see bank balance"
        assert bank.get("balance") is not None, "Bank balance should not be None for admin"
        print(f"PASS: Admin sees bank balance = {bank.get('balance')}")

    def test_non_admin_bank_balance_hidden(self, cashier_token, auth_headers):
        """Non-admin (cashier) sees bank wallet with balance=null and balance_hidden=True"""
        token, user_id, username = cashier_token
        cashier_headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=cashier_headers,
        )
        assert resp.status_code == 200
        wallets = resp.json()
        bank = next((w for w in wallets if w["type"] == "bank"), None)
        assert bank is not None, "Bank wallet not found for cashier view"
        assert bank.get("balance_hidden") is True, (
            f"Non-admin should have balance_hidden=True on bank wallet. Got: {bank}"
        )
        assert bank.get("balance") is None, (
            f"Non-admin should see bank balance=null. Got: {bank.get('balance')}"
        )
        print(f"PASS: Non-admin sees bank balance=null, balance_hidden=True")

    def test_wallet_fields_structure(self, auth_headers):
        """Each wallet has required fields: id, type, name, balance, branch_id, active"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        wallets = resp.json()
        required_fields = {"id", "type", "name", "branch_id", "active"}
        for w in wallets:
            missing = required_fields - set(w.keys())
            assert not missing, f"Wallet {w.get('type')} missing fields: {missing}"
        print(f"PASS: All wallets have required fields")


# ─── Fund Transfers Tests ─────────────────────────────────────────────────────

class TestFundTransfers:
    """Tests for POST /api/fund-transfers"""

    def test_capital_add_admin_succeeds(self, auth_headers):
        """capital_add with admin user (no PIN needed) → 200 OK"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "capital_add",
                "amount": 50.00,
                "note": "TEST capital injection for pytest",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "transfer" in data
        assert data["transfer"]["transfer_type"] == "capital_add"
        assert float(data["transfer"]["amount"]) == 50.00
        print(f"PASS: capital_add succeeded — {data['message']}")

    def test_cashier_to_safe_valid_pin(self, auth_headers):
        """cashier_to_safe with valid manager PIN (1234) → 200 OK"""
        # First add capital to ensure cashier has funds
        requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "capital_add",
                "amount": 100.00,
                "note": "Pre-test capital for cashier_to_safe",
            },
            headers=auth_headers,
        )

        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "cashier_to_safe",
                "amount": 10.00,
                "note": "TEST cashier to safe transfer",
                "manager_pin": MANAGER_PIN,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert data["transfer"]["transfer_type"] == "cashier_to_safe"
        assert data["authorized_by"] is not None, "authorized_by should be set after valid PIN"
        print(f"PASS: cashier_to_safe with valid PIN — authorized by {data['authorized_by']}")

    def test_cashier_to_safe_wrong_pin_returns_401(self, auth_headers):
        """cashier_to_safe with wrong PIN → 401 Invalid manager PIN"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "cashier_to_safe",
                "amount": 10.00,
                "note": "TEST wrong PIN transfer",
                "manager_pin": "9999",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "invalid" in detail.lower() or "pin" in detail.lower(), (
            f"Expected invalid PIN error, got: {detail}"
        )
        print(f"PASS: Wrong PIN returns 401 — {detail}")

    def test_cashier_to_safe_missing_pin_returns_400(self, auth_headers):
        """cashier_to_safe with no PIN → 400 Manager PIN required"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "cashier_to_safe",
                "amount": 10.00,
                "note": "TEST missing PIN transfer",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "pin" in detail.lower() or "required" in detail.lower(), (
            f"Expected 'PIN required' error, got: {detail}"
        )
        print(f"PASS: Missing PIN returns 400 — {detail}")

    def test_safe_to_bank_wrong_totp_returns_401(self, auth_headers):
        """safe_to_bank with wrong TOTP → 401"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "safe_to_bank",
                "amount": 10.00,
                "note": "TEST wrong TOTP",
                "totp_code": "000000",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "totp" in detail.lower() or "invalid" in detail.lower() or "code" in detail.lower(), (
            f"Expected TOTP error, got: {detail}"
        )
        print(f"PASS: Wrong TOTP returns 401 — {detail}")

    def test_safe_to_bank_missing_totp_returns_400(self, auth_headers):
        """safe_to_bank with no TOTP → 400"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "safe_to_bank",
                "amount": 10.00,
                "note": "TEST missing TOTP",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "totp" in detail.lower() or "required" in detail.lower(), (
            f"Expected TOTP required error, got: {detail}"
        )
        print(f"PASS: Missing TOTP returns 400 — {detail}")

    def test_capital_add_non_admin_returns_403(self, cashier_token):
        """capital_add with non-admin user → 403 Forbidden"""
        token, user_id, username = cashier_token
        cashier_headers = {"Authorization": f"Bearer {token}"}

        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "capital_add",
                "amount": 100.00,
            },
            headers=cashier_headers,
        )
        # Expect 403 (only admin can add capital) or 401/403 due to permission
        assert resp.status_code in (403, 401), (
            f"Expected 403/401 for non-admin capital_add, got {resp.status_code}: {resp.text}"
        )
        print(f"PASS: Non-admin capital_add blocked — status {resp.status_code}")

    def test_invalid_transfer_type_returns_400(self, auth_headers):
        """Invalid transfer_type → 400"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "invalid_type",
                "amount": 10.00,
                "note": "TEST invalid type",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid transfer_type returns 400")

    def test_zero_amount_returns_400(self, auth_headers):
        """Zero amount → 400"""
        resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "capital_add",
                "amount": 0,
                "note": "TEST zero amount",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Zero amount returns 400")


# ─── Fund Transfer Audit Log Tests ───────────────────────────────────────────

class TestFundTransferAuditLog:
    """Tests for GET /api/fund-transfers"""

    def test_get_fund_transfers_returns_list(self, auth_headers):
        """GET /api/fund-transfers returns a list (audit log)"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-transfers",
            params={"branch_id": B1_BRANCH_ID, "limit": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "fund-transfers should return a list"
        print(f"PASS: GET /api/fund-transfers returned {len(data)} records")

    def test_fund_transfers_contain_expected_fields(self, auth_headers):
        """Each transfer record has required audit fields"""
        resp = requests.get(
            f"{BASE_URL}/api/fund-transfers",
            params={"branch_id": B1_BRANCH_ID, "limit": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        transfers = resp.json()
        if len(transfers) == 0:
            pytest.skip("No transfers to verify fields")
        required = {"id", "branch_id", "transfer_type", "amount", "description", "performed_by_name", "created_at"}
        for t in transfers:
            missing = required - set(t.keys())
            assert not missing, f"Transfer missing fields: {missing}"
        print(f"PASS: All transfer records have required audit fields")

    def test_capital_add_appears_in_audit_log(self, auth_headers):
        """After capital_add, a record appears in GET /api/fund-transfers"""
        # Perform a capital add with unique note
        unique_note = f"AUDIT_TEST_{uuid.uuid4().hex[:8]}"
        add_resp = requests.post(
            f"{BASE_URL}/api/fund-transfers",
            json={
                "branch_id": B1_BRANCH_ID,
                "transfer_type": "capital_add",
                "amount": 1.00,
                "note": unique_note,
            },
            headers=auth_headers,
        )
        assert add_resp.status_code == 200, f"capital_add failed: {add_resp.text}"

        # Fetch audit log
        log_resp = requests.get(
            f"{BASE_URL}/api/fund-transfers",
            params={"branch_id": B1_BRANCH_ID, "limit": 20},
            headers=auth_headers,
        )
        assert log_resp.status_code == 200
        transfers = log_resp.json()
        notes = [t.get("note", "") for t in transfers]
        assert unique_note in notes, (
            f"Expected note '{unique_note}' in audit log, but found: {notes[:5]}"
        )
        print(f"PASS: capital_add appears in audit log with note '{unique_note}'")


# ─── Branch Auto-Provision Tests ──────────────────────────────────────────────

class TestBranchAutoProvision:
    """Branch creation auto-provisions all 4 wallets"""

    def test_new_branch_gets_4_wallets(self, auth_headers):
        """POST /api/branches creates branch + auto-provisions 4 wallets"""
        test_branch_name = f"TEST_Branch_{uuid.uuid4().hex[:6]}"

        # Create branch
        create_resp = requests.post(
            f"{BASE_URL}/api/branches",
            json={"name": test_branch_name, "address": "Test Address", "phone": "09000000000"},
            headers=auth_headers,
        )
        assert create_resp.status_code in (200, 201), (
            f"Branch creation failed: {create_resp.status_code} {create_resp.text}"
        )
        branch = create_resp.json()
        branch_id = branch.get("id")
        assert branch_id, "Branch ID not in response"

        try:
            # Check wallets were provisioned
            wallets_resp = requests.get(
                f"{BASE_URL}/api/fund-wallets",
                params={"branch_id": branch_id},
                headers=auth_headers,
            )
            assert wallets_resp.status_code == 200
            wallets = wallets_resp.json()
            types_found = {w["type"] for w in wallets}
            required = {"cashier", "safe", "digital", "bank"}
            assert required.issubset(types_found), (
                f"New branch missing wallet types: {required - types_found}"
            )
            print(f"PASS: New branch '{test_branch_name}' has 4 wallets: {types_found}")
        finally:
            # Cleanup: deactivate branch
            requests.delete(f"{BASE_URL}/api/branches/{branch_id}", headers=auth_headers)


# ─── Digital Payment Routing Tests ───────────────────────────────────────────

class TestDigitalPaymentRouting:
    """Digital payments route to digital wallet"""

    def test_is_digital_payment_gcash(self, auth_headers):
        """Test that a GCash invoice routes payment to digital wallet"""
        # Get current digital wallet balance
        wallets_before = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=auth_headers,
        ).json()
        digital_before = next((w for w in wallets_before if w["type"] == "digital"), None)
        balance_before = float(digital_before.get("balance", 0)) if digital_before else 0.0

        # Create an invoice with GCash payment
        inv_resp = requests.post(
            f"{BASE_URL}/api/invoices",
            json={
                "branch_id": B1_BRANCH_ID,
                "customer_name": "TEST Digital Customer",
                "payment_method": "GCash",
                "digital_platform": "GCash",
                "digital_ref_number": f"TEST-GC-{uuid.uuid4().hex[:8]}",
                "digital_sender": "TEST Sender",
                "amount_paid": 25.00,
                "items": [{
                    "product_name": "TEST Digital Product",
                    "quantity": 1,
                    "rate": 25.00,
                    "discount_type": "amount",
                    "discount_value": 0,
                    "discount_amount": 0,
                    "total": 25.00,
                }],
                "subtotal": 25.00,
                "freight": 0,
                "overall_discount": 0,
                "grand_total": 25.00,
                "sale_type": "walk_in",
            },
            headers=auth_headers,
        )
        if inv_resp.status_code not in (200, 201):
            pytest.skip(f"Cannot create test invoice: {inv_resp.status_code} {inv_resp.text}")

        invoice = inv_resp.json()
        assert invoice.get("fund_source") == "digital", (
            f"GCash invoice fund_source should be 'digital', got: {invoice.get('fund_source')}"
        )

        # Check digital wallet balance increased
        wallets_after = requests.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": B1_BRANCH_ID},
            headers=auth_headers,
        ).json()
        digital_after = next((w for w in wallets_after if w["type"] == "digital"), None)
        balance_after = float(digital_after.get("balance", 0)) if digital_after else 0.0

        assert balance_after >= balance_before + 25.00, (
            f"Digital wallet balance didn't increase: before={balance_before}, after={balance_after}"
        )
        print(f"PASS: GCash invoice routed to digital wallet. Balance: {balance_before} → {balance_after}")
