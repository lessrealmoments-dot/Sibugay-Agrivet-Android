"""
Tests for AgriBooks fixes - Iteration 129:
1. Branch Transfer bugs (Confirm Receipt, Verify button, branch guard)
2. QR Payment Receive (Phase 3)
3. QR Transfer Receive (Phase 4)
4. verify_pin now works for branch_transfer doc type
5. PO Bug Fix (sourceType useState declarations)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

# ── Test data from review_request ───────────────────────────────────────────
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASS = "Aa@58798546521325"
MANAGER_PIN = "521325"
TRANSFER_DOC_CODE = "RVR4G857"  # BTO-20260313-0096, Branch 1 → Branch 2, status: sent
INVOICE_DOC_CODE = "RY5T64S2"   # SVC-20260302-0016, Balance: 90.0
TRANSFER_ID = "4c338b7f-d51e-4dfc-a1c1-e7568d665c29"
TRANSFER_FROM_BRANCH = "c435277f-9fc7-4d83-83e7-38be5b4423ac"  # Branch 1
TRANSFER_TO_BRANCH = "18c02daa-bce0-45de-860a-70ccc6ed6c6d"    # Branch 2


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASS})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── Section 1: QR Actions — verify_pin for branch_transfer ──────────────────

class TestVerifyPinBranchTransfer:
    """verify_pin endpoint should work for branch_transfer doc type (not just invoice)."""

    def test_verify_pin_branch_transfer_valid(self):
        """verify_pin with valid manager PIN on branch_transfer code → 200 valid:true."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/verify_pin",
            json={"pin": MANAGER_PIN}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("valid") is True
        assert "verifier_name" in data
        print(f"PASS: verify_pin branch_transfer → verifier: {data['verifier_name']}, method: {data.get('method')}")

    def test_verify_pin_branch_transfer_invalid_pin(self):
        """verify_pin with wrong PIN on branch_transfer → 403."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/verify_pin",
            json={"pin": "000000"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid PIN on branch_transfer verify_pin correctly returns 403")

    def test_verify_pin_branch_transfer_no_pin(self):
        """verify_pin with empty PIN → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/verify_pin",
            json={"pin": ""}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Empty PIN returns 400")


# ── Section 2: QR Payment Receive ───────────────────────────────────────────

class TestQRPaymentReceive:
    """POST /api/qr-actions/{code}/receive_payment"""

    def test_receive_payment_invalid_pin(self):
        """Invalid PIN → 403."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"pin": "000000", "amount": 50, "method": "Cash"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid PIN → 403")

    def test_receive_payment_no_pin(self):
        """No PIN → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"amount": 50, "method": "Cash"}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: No PIN → 400")

    def test_receive_payment_zero_amount(self):
        """Zero amount → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"pin": MANAGER_PIN, "amount": 0, "method": "Cash"}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Zero amount → 400")

    def test_receive_payment_over_balance(self):
        """Amount exceeding balance → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"pin": MANAGER_PIN, "amount": 99999, "method": "Cash"}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: Over-balance amount → 400")

    def test_receive_payment_valid_cash(self):
        """Valid PIN + Cash method → 200 with updated balance."""
        # First get current balance
        pre_resp = requests.get(f"{BASE_URL}/api/doc/view/{INVOICE_DOC_CODE}")
        assert pre_resp.status_code == 200
        pre_balance = float(pre_resp.json().get("balance", 0))
        if pre_balance <= 0:
            pytest.skip(f"Invoice {INVOICE_DOC_CODE} has no remaining balance ({pre_balance}), skipping payment test")

        partial_amount = min(10, pre_balance)
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"pin": MANAGER_PIN, "amount": partial_amount, "method": "Cash"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        assert data.get("amount_received") == partial_amount
        assert data.get("new_balance") == pytest.approx(pre_balance - partial_amount, abs=0.01)
        assert "authorized_by" in data
        print(f"PASS: Cash payment received. New balance: {data['new_balance']}, authorized by: {data['authorized_by']}")

    def test_receive_payment_gcash_method(self):
        """Valid PIN + GCash method should route to digital wallet."""
        # Check current balance
        pre_resp = requests.get(f"{BASE_URL}/api/doc/view/{INVOICE_DOC_CODE}")
        assert pre_resp.status_code == 200
        pre_balance = float(pre_resp.json().get("balance", 0))
        if pre_balance <= 0:
            pytest.skip(f"Invoice {INVOICE_DOC_CODE} fully paid, skipping GCash test")

        partial_amount = min(5, pre_balance)
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/receive_payment",
            json={"pin": MANAGER_PIN, "amount": partial_amount, "method": "GCash", "reference": "GCX-TEST-123"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        # Payment object should have fund_source=digital for GCash
        payment = data.get("payment", {})
        assert payment.get("fund_source") == "digital", f"Expected digital fund_source, got {payment.get('fund_source')}"
        assert payment.get("method") == "GCash"
        print(f"PASS: GCash payment recorded with digital fund_source. New balance: {data['new_balance']}")

    def test_receive_payment_wrong_doc_type(self):
        """Using a branch_transfer doc code for receive_payment → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/receive_payment",
            json={"pin": MANAGER_PIN, "amount": 100, "method": "Cash"}
        )
        assert resp.status_code == 400, f"Expected 400 (wrong doc type), got {resp.status_code}: {resp.text}"
        print(f"PASS: Using transfer doc for receive_payment → 400")


# ── Section 3: QR Transfer Receive ──────────────────────────────────────────

class TestQRTransferReceive:
    """POST /api/qr-actions/{code}/transfer_receive"""

    def test_transfer_receive_invalid_pin(self):
        """Invalid PIN → 403."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/transfer_receive",
            json={"pin": "000000", "items": [{"product_id": "test-product-phase3-1773389476715829274", "qty_received": 3}]}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid PIN on transfer_receive → 403")

    def test_transfer_receive_no_items(self):
        """No items → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/transfer_receive",
            json={"pin": MANAGER_PIN, "items": []}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"PASS: No items → 400")

    def test_transfer_receive_wrong_doc_type(self):
        """Using invoice doc code for transfer_receive → 400."""
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/transfer_receive",
            json={"pin": MANAGER_PIN, "items": [{"product_id": "test-id", "qty_received": 1}]}
        )
        assert resp.status_code == 400, f"Expected 400 (wrong doc type), got {resp.status_code}: {resp.text}"
        print(f"PASS: Invoice doc code for transfer_receive → 400")

    def test_transfer_receive_valid_pin_reaches_inventory_check(self):
        """
        Valid PIN on sent transfer → reaches inventory check.
        Per review_request: will fail with 'Insufficient stock' because test product
        has 0 inventory at source — this is CORRECT behavior (not a 404 or 500).
        """
        resp = requests.post(
            f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/transfer_receive",
            json={
                "pin": MANAGER_PIN,
                "items": [{"product_id": "test-product-phase3-1773389476715829274", "qty_received": 3}],
                "notes": "Test receive via QR"
            }
        )
        # Should either succeed (200) or fail at inventory level (400/422), NOT 403/404/500
        assert resp.status_code not in [403, 404, 500], \
            f"Got unexpected status {resp.status_code}: {resp.text}"
        print(f"PASS: Valid PIN on transfer_receive reaches inventory check. Status: {resp.status_code}, Response: {resp.text[:200]}")


# ── Section 4: Branch Transfer receive_transfer backend branch guard ─────────

class TestBranchTransferBranchGuard:
    """Backend /api/branch-transfers/{id}/receive should reject wrong-branch non-admin."""

    def test_receive_transfer_no_auth(self):
        """No auth token → 401 or 403."""
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TRANSFER_ID}/receive",
            json={"items": [], "skip_receipt_check": True}
        )
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}: {resp.text}"
        print(f"PASS: No auth → {resp.status_code}")

    def test_receive_transfer_admin_can_receive(self, auth_headers):
        """Admin should be able to receive (may fail for other reasons like receipt requirement, not 403)."""
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TRANSFER_ID}/receive",
            headers=auth_headers,
            json={"items": [], "skip_receipt_check": False}
        )
        # Admin should NOT get 403 (branch guard should let admin through)
        assert resp.status_code != 403, f"Admin should not be blocked by branch guard. Got 403: {resp.text}"
        print(f"PASS: Admin not blocked by branch guard. Status: {resp.status_code}")

    def test_transfer_doc_context_has_transfer_receive_action(self):
        """doc/view endpoint should return 'transfer_receive' in available_actions for sent transfer."""
        resp = requests.get(f"{BASE_URL}/api/doc/view/{TRANSFER_DOC_CODE}")
        assert resp.status_code == 200
        data = resp.json()
        assert "transfer_receive" in data.get("available_actions", []), \
            f"Expected 'transfer_receive' in available_actions, got: {data.get('available_actions')}"
        # Verify items include product_id (doc_lookup.py fix)
        items = data.get("items", [])
        assert len(items) > 0, "Transfer should have items"
        for item in items:
            assert "product_id" in item, f"Item missing product_id: {item}"
        print(f"PASS: Transfer doc has transfer_receive action and items include product_id: {items}")


# ── Section 5: Doc Lookup — product_id in transfer items ─────────────────────

class TestDocLookupTransferItems:
    """doc_lookup.py should include product_id in branch transfer items."""

    def test_transfer_items_include_product_id(self):
        """GET /api/doc/view/{code} for branch transfer should return product_id in items."""
        resp = requests.get(f"{BASE_URL}/api/doc/view/{TRANSFER_DOC_CODE}")
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        assert len(items) > 0
        for item in items:
            assert "product_id" in item, f"Item missing product_id: {item}"
            assert item["product_id"] != "", f"product_id is empty for item: {item}"
        print(f"PASS: All transfer items include product_id: {[i['product_id'] for i in items]}")

    def test_transfer_doc_has_to_branch_id(self):
        """GET /api/doc/view/{code} for branch transfer should return to_branch_id."""
        resp = requests.get(f"{BASE_URL}/api/doc/view/{TRANSFER_DOC_CODE}")
        assert resp.status_code == 200
        data = resp.json()
        assert "to_branch_id" in data, "Missing to_branch_id in transfer doc view"
        assert data["to_branch_id"] == TRANSFER_TO_BRANCH
        print(f"PASS: to_branch_id correctly returned: {data['to_branch_id']}")


# ── Section 6: QR Context endpoint ──────────────────────────────────────────

class TestQRContext:
    """GET /api/qr-actions/{code}/context should return doc info + available_actions."""

    def test_qr_context_invoice(self):
        """Invoice context returns receive_payment in available_actions if balance > 0."""
        resp = requests.get(f"{BASE_URL}/api/qr-actions/{INVOICE_DOC_CODE}/context")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("doc_type") == "invoice"
        print(f"PASS: Invoice QR context — available_actions: {data.get('available_actions')}")

    def test_qr_context_branch_transfer(self):
        """Branch transfer context returns transfer_receive for sent transfer."""
        resp = requests.get(f"{BASE_URL}/api/qr-actions/{TRANSFER_DOC_CODE}/context")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("doc_type") == "branch_transfer"
        assert "transfer_receive" in data.get("available_actions", []), \
            f"Expected transfer_receive in available_actions: {data.get('available_actions')}"
        print(f"PASS: Transfer QR context — available_actions: {data.get('available_actions')}")

    def test_qr_context_invalid_code(self):
        """Invalid code → 404."""
        resp = requests.get(f"{BASE_URL}/api/qr-actions/INVALID999/context")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Invalid code → 404")
