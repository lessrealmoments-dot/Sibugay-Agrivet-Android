"""
Test suite for AgriBooks Audit Money+Stock Movement fixes (Iteration 39).
Tests 10 bug fixes:
  1. PO Reopen reverses cash payment + includes reversal message
  2. PO Cancel blocked on received POs (400)
  3. PO Edit balance = max(0, grand_total - amount_paid)
  4. Branch Transfer cancel blocked for received_pending/disputed status (400)
  5. Returns void endpoint with invalid manager PIN returns 401
  6. Returns void endpoint with nonexistent ID returns 404
  7. Employee advance reverse endpoint with wrong PIN returns 401
  8. Customer cashout reverse endpoint with wrong PIN returns 401
  9. Invoice payment void endpoint with wrong PIN returns 401
  10. Delete nonexistent expense returns 404
"""

import pytest
import requests
import os
import uuid
import pymongo
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "agribooks")

# Known test data IDs (from DB scan)
RECEIVED_PO_ID = "568347f9-96cf-4301-a888-d1e393d5f6d2"       # PO-20260222082936-9745 (received)
RETURN_ID = "9dd2d221-032f-4555-8873-c74e3d94eb1e"             # RTN-20260223-0001
BRANCH_TRANSFER_RECEIVED_PENDING_ID = "cc9ee135-8108-4b88-9447-fc93b07bbc6d"  # BTO-20260222-0007
CUSTOMER_CASHOUT_EXPENSE_ID = "d44c4ac4-2530-46ee-97b0-943591edc610"
EMPLOYEE_ADVANCE_EXPENSE_ID = "e6bf8058-ef84-48ec-8dae-3812280885b9"
INVOICE_ID = "08606c84-4192-4e3c-a8d9-bbde234492c9"            # SI-20260220-0001
INVOICE_PAYMENT_ID = "cee5ba94-779a-4b67-9de9-8b306b97ca90"   # first payment on SI-20260220-0001
B1_BRANCH_ID = "7f9b29cb-3028-4680-b36c-cb8ad1c80345"
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"

MANAGER_PIN = "521325"
WRONG_PIN = "0000"
NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    """Direct synchronous MongoDB connection for setup/teardown."""
    client = pymongo.MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def session():
    """Authenticated requests session (owner)."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(f"{BASE_URL}/api/auth/login", json={"username": "owner", "password": "521325"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------------------------------------------------------------------------
# Fix #5/#6: PO Cancel blocked on received PO
# ---------------------------------------------------------------------------

class TestPOCancelBlocked:
    """Cancel of received PO must return 400 — inventory already added."""

    def test_cancel_received_po_returns_400(self, session):
        """DELETE /api/purchase-orders/{received_po_id} → 400 Cannot cancel received PO."""
        resp = session.delete(f"{BASE_URL}/api/purchase-orders/{RECEIVED_PO_ID}")
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "cannot cancel" in detail or "received" in detail, \
            f"Expected block message for received PO, got: {data['detail']}"
        print(f"PASS: Cancel received PO returns 400 — {data['detail']}")

    def test_cancel_nonexistent_po_returns_404(self, session):
        """DELETE /api/purchase-orders/{nonexistent} → 404."""
        resp = session.delete(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print("PASS: Cancel nonexistent PO returns 404")


# ---------------------------------------------------------------------------
# Fix #1: PO Reopen reverses cash payment + message includes reversal
# ---------------------------------------------------------------------------

class TestPOReopenPaymentReversal:
    """
    Reopen a received PO: verify the response message includes payment reversal info.
    Uses temp test POs inserted directly into MongoDB.
    """

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, db, request):
        """Insert minimal test POs and clean up after tests."""
        self._cash_po_id = f"TEST-PO-CASH-{uuid.uuid4()}"
        self._terms_po_id = f"TEST-PO-TERMS-{uuid.uuid4()}"

        db.purchase_orders.insert_one({
            "id": self._cash_po_id,
            "po_number": f"TEST-CASH-{self._cash_po_id[:8]}",
            "vendor": "TEST VENDOR",
            "branch_id": B1_BRANCH_ID,
            "items": [],
            "status": "received",
            "payment_method": "cash",
            "po_type": "cash",
            "payment_status": "paid",
            "amount_paid": 1.0,
            "balance": 0,
            "grand_total": 1.0,
            "subtotal": 1.0,
            "fund_source": "cashier",
            "created_by": "test",
            "created_at": now_iso(),
        })
        db.purchase_orders.insert_one({
            "id": self._terms_po_id,
            "po_number": f"TEST-TERMS-{self._terms_po_id[:8]}",
            "vendor": "TEST VENDOR",
            "branch_id": B1_BRANCH_ID,
            "items": [],
            "status": "received",
            "payment_method": "credit",
            "po_type": "terms",
            "payment_status": "paid",
            "amount_paid": 0,
            "balance": 0,
            "grand_total": 500.0,
            "subtotal": 500.0,
            "fund_source": "cashier",
            "created_by": "test",
            "created_at": now_iso(),
        })

        yield

        # Cleanup test data after the test method
        db.purchase_orders.delete_many({"id": {"$in": [self._cash_po_id, self._terms_po_id]}})

    def test_reopen_cash_po_includes_payment_reversal_message(self, session):
        """POST /api/purchase-orders/{cash_po_id}/reopen → message includes payment returned."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{self._cash_po_id}/reopen")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        msg = data["message"]
        # Must mention funds returned
        assert "returned to" in msg.lower() or "reversal" in msg.lower() or "₱1.00" in msg, \
            f"Expected payment reversal in message, got: {msg}"
        print(f"PASS: Cash PO reopen message includes reversal — {msg}")

    def test_reopen_terms_po_includes_payable_voided_message(self, session):
        """POST /api/purchase-orders/{terms_po_id}/reopen → message includes 'Accounts payable voided'."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{self._terms_po_id}/reopen")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        msg = data["message"]
        assert "payable" in msg.lower() or "voided" in msg.lower(), \
            f"Expected payable voided in message, got: {msg}"
        print(f"PASS: Terms PO reopen message correct — {msg}")

    def test_reopen_nonexistent_po_returns_404(self, session):
        """POST /api/purchase-orders/{nonexistent}/reopen → 404."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}/reopen")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print("PASS: Reopen nonexistent PO returns 404")


# ---------------------------------------------------------------------------
# Fix #3: PO Edit balance = max(0, grand_total - amount_paid)
# ---------------------------------------------------------------------------

class TestPOEditBalance:
    """After editing a PO with partial payment, balance must be recalculated correctly."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, db):
        """Insert test PO in ordered status with existing amount_paid = 5000."""
        self._po_id = f"TEST-PO-EDIT-{uuid.uuid4()}"

        db.purchase_orders.insert_one({
            "id": self._po_id,
            "po_number": f"TEST-EDIT-{self._po_id[:8]}",
            "vendor": "TEST VENDOR",
            "branch_id": IPIL_BRANCH_ID,
            "items": [
                {
                    "product_id": "fake-product-001",
                    "product_name": "Test Product",
                    "quantity": 10,
                    "unit_price": 1000,
                    "discount_type": "amount",
                    "discount_value": 0,
                    "discount_amount": 0,
                    "total": 10000,
                    "unit": "kg",
                }
            ],
            "status": "ordered",
            "payment_method": "cash",
            "po_type": "cash",
            "payment_status": "partial",
            "amount_paid": 5000.0,
            "balance": 0,          # Old bug: balance was incorrectly 0 when paid partially
            "grand_total": 10000.0,
            "subtotal": 10000.0,
            "line_subtotal": 10000.0,
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "overall_discount_amount": 0,
            "freight": 0,
            "tax_rate": 0,
            "tax_amount": 0,
            "fund_source": "cashier",
            "reopened_at": now_iso(),
            "created_by": "test",
            "created_at": now_iso(),
        })

        yield

        db.purchase_orders.delete_many({"id": self._po_id})

    def test_edit_po_balance_recalculated_from_amount_paid(self, session):
        """
        PUT /api/purchase-orders/{po_id} with same items (10 × 1000 = 10000)
        amount_paid=5000 → balance must be max(0, 10000 - 5000) = 5000
        """
        po_id = self._po_id
        payload = {
            "items": [
                {
                    "product_id": "fake-product-001",
                    "product_name": "Test Product",
                    "quantity": 10,
                    "unit_price": 1000,
                    "discount_type": "amount",
                    "discount_value": 0,
                    "unit": "kg",
                }
            ],
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "edit_reason": "Testing balance fix",
        }
        resp = session.put(f"{BASE_URL}/api/purchase-orders/{po_id}", json=payload)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        grand_total = float(data["grand_total"])
        amount_paid = float(data["amount_paid"])
        balance = float(data["balance"])
        expected_balance = max(0, round(grand_total - amount_paid, 2))
        assert balance == expected_balance, \
            f"Balance fix failed: got {balance}, expected {expected_balance} " \
            f"(grand_total={grand_total}, amount_paid={amount_paid})"
        print(f"PASS: PO edit balance fix — balance={balance} == {expected_balance}")

    def test_edit_po_balance_zero_when_overpaid(self, session):
        """
        Edit PO to lower grand_total (3 × 1000=3000) below amount_paid=5000
        → balance must be max(0, ...) = 0, not negative.
        """
        po_id = self._po_id
        payload = {
            "items": [
                {
                    "product_id": "fake-product-001",
                    "product_name": "Test Product",
                    "quantity": 3,
                    "unit_price": 1000,
                    "discount_type": "amount",
                    "discount_value": 0,
                    "unit": "kg",
                }
            ],
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "edit_reason": "Testing overpaid balance clamped to zero",
        }
        resp = session.put(f"{BASE_URL}/api/purchase-orders/{po_id}", json=payload)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        balance = float(data["balance"])
        grand_total = float(data["grand_total"])
        amount_paid = float(data["amount_paid"])
        assert balance >= 0, f"Balance must not be negative! got {balance}"
        expected = max(0, round(grand_total - amount_paid, 2))
        assert balance == expected, \
            f"Expected {expected} (clamped) but got {balance}"
        print(f"PASS: Overpaid PO balance clamped to {expected} — balance={balance}")


# ---------------------------------------------------------------------------
# Fix #6: Branch Transfer cancel blocked for received_pending/disputed
# ---------------------------------------------------------------------------

class TestBranchTransferCancelBlocked:
    """Cancel of received_pending/disputed transfer must return 400."""

    def test_cancel_received_pending_transfer_returns_400(self, session):
        """DELETE /api/branch-transfers/{received_pending_id} → 400."""
        resp = session.delete(f"{BASE_URL}/api/branch-transfers/{BRANCH_TRANSFER_RECEIVED_PENDING_ID}")
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "cannot cancel" in detail or "received" in detail or "inventory" in detail, \
            f"Expected block message for received_pending transfer, got: {data['detail']}"
        print(f"PASS: Cancel received_pending transfer returns 400 — {data['detail']}")

    def test_cancel_nonexistent_transfer_returns_404(self, session):
        """DELETE /api/branch-transfers/{nonexistent} → 404."""
        resp = session.delete(f"{BASE_URL}/api/branch-transfers/{NONEXISTENT_ID}")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print("PASS: Cancel nonexistent transfer returns 404")


# ---------------------------------------------------------------------------
# Fix #7: Returns void endpoint — manager PIN validation
# ---------------------------------------------------------------------------

class TestReturnsVoid:
    """POST /api/returns/{id}/void — manager PIN required."""

    def test_void_return_with_wrong_pin_returns_401(self, session):
        """POST /api/returns/{return_id}/void with wrong PIN → 401."""
        resp = session.post(
            f"{BASE_URL}/api/returns/{RETURN_ID}/void",
            json={"manager_pin": WRONG_PIN, "reason": "Test wrong pin"}
        )
        assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Void return with wrong PIN returns 401 — {data['detail']}")

    def test_void_return_nonexistent_returns_404(self, session):
        """POST /api/returns/{nonexistent}/void → 404 Return not found."""
        resp = session.post(
            f"{BASE_URL}/api/returns/{NONEXISTENT_ID}/void",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent"}
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "return" in detail or "not found" in detail, \
            f"Expected 'Return not found' message, got: {data['detail']}"
        print(f"PASS: Void nonexistent return returns 404 — {data['detail']}")

    def test_void_return_missing_pin_returns_400(self, session):
        """POST /api/returns/{return_id}/void with no PIN → 400 Manager PIN required."""
        resp = session.post(
            f"{BASE_URL}/api/returns/{RETURN_ID}/void",
            json={"reason": "No pin provided"}
        )
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        print(f"PASS: Void return with missing PIN returns 400 — {data['detail']}")


# ---------------------------------------------------------------------------
# Fix #9: Employee Advance reverse endpoint
# ---------------------------------------------------------------------------

class TestEmployeeAdvanceReverse:
    """POST /api/expenses/employee-advance/{id}/reverse — manager PIN validation."""

    def test_reverse_employee_advance_wrong_pin_returns_401(self, session):
        """POST /api/expenses/employee-advance/{id}/reverse with wrong PIN → 401."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{EMPLOYEE_ADVANCE_EXPENSE_ID}/reverse",
            json={"manager_pin": WRONG_PIN, "reason": "Test wrong pin"}
        )
        assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Employee advance reverse with wrong PIN returns 401 — {data['detail']}")

    def test_reverse_employee_advance_missing_pin_returns_400(self, session):
        """POST /api/expenses/employee-advance/{id}/reverse with no PIN → 400."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{EMPLOYEE_ADVANCE_EXPENSE_ID}/reverse",
            json={"reason": "No pin"}
        )
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Employee advance reverse missing PIN returns 400 — {resp.json().get('detail')}")

    def test_reverse_employee_advance_nonexistent_correct_pin_returns_404(self, session):
        """POST /api/expenses/employee-advance/{nonexistent}/reverse with correct PIN → 404."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN, "reason": "Test"}
        )
        assert resp.status_code == 404, \
            f"Expected 404 for nonexistent expense, got {resp.status_code}: {resp.text}"
        print(f"PASS: Nonexistent employee advance reverse with correct PIN returns 404")


# ---------------------------------------------------------------------------
# Fix #9b: Customer Cashout reverse endpoint
# ---------------------------------------------------------------------------

class TestCustomerCashoutReverse:
    """POST /api/expenses/customer-cashout/{id}/reverse — manager PIN validation."""

    def test_reverse_customer_cashout_wrong_pin_returns_401(self, session):
        """POST /api/expenses/customer-cashout/{id}/reverse with wrong PIN → 401."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{CUSTOMER_CASHOUT_EXPENSE_ID}/reverse",
            json={"manager_pin": WRONG_PIN, "reason": "Test wrong pin"}
        )
        assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Customer cashout reverse with wrong PIN returns 401 — {data['detail']}")

    def test_reverse_customer_cashout_missing_pin_returns_400(self, session):
        """POST /api/expenses/customer-cashout/{id}/reverse with no PIN → 400."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{CUSTOMER_CASHOUT_EXPENSE_ID}/reverse",
            json={"reason": "No pin provided"}
        )
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Customer cashout reverse missing PIN returns 400 — {resp.json().get('detail')}")

    def test_reverse_customer_cashout_nonexistent_correct_pin_returns_404(self, session):
        """POST /api/expenses/customer-cashout/{nonexistent}/reverse with correct PIN → 404."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent"}
        )
        assert resp.status_code == 404, \
            f"Expected 404 for nonexistent expense, got {resp.status_code}: {resp.text}"
        print(f"PASS: Nonexistent customer cashout reverse returns 404 — {resp.json().get('detail')}")


# ---------------------------------------------------------------------------
# Fix #10: Invoice payment void endpoint
# ---------------------------------------------------------------------------

class TestInvoicePaymentVoid:
    """POST /api/invoices/{inv_id}/void-payment/{payment_id} — manager PIN required."""

    def test_void_invoice_payment_wrong_pin_returns_401(self, session):
        """POST /api/invoices/{inv_id}/void-payment/{payment_id} with wrong PIN → 401."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{INVOICE_ID}/void-payment/{INVOICE_PAYMENT_ID}",
            json={"manager_pin": WRONG_PIN, "reason": "Test wrong pin"}
        )
        assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Invoice payment void with wrong PIN returns 401 — {data['detail']}")

    def test_void_invoice_payment_missing_pin_returns_400(self, session):
        """POST /api/invoices/{inv_id}/void-payment/{payment_id} with no PIN → 400."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{INVOICE_ID}/void-payment/{INVOICE_PAYMENT_ID}",
            json={"reason": "No pin provided"}
        )
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Invoice payment void missing PIN returns 400 — {resp.json().get('detail')}")

    def test_void_nonexistent_invoice_returns_404(self, session):
        """POST /api/invoices/{nonexistent}/void-payment/{payment_id} → 404."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{NONEXISTENT_ID}/void-payment/{INVOICE_PAYMENT_ID}",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent invoice"}
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Void nonexistent invoice returns 404 — {resp.json().get('detail')}")

    def test_void_invoice_nonexistent_payment_returns_404(self, session):
        """POST /api/invoices/{inv_id}/void-payment/{nonexistent_payment} → 404."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{INVOICE_ID}/void-payment/{NONEXISTENT_ID}",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent payment"}
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        detail = str(data.get("detail", "")).lower()
        assert "payment" in detail or "not found" in detail, \
            f"Expected 'payment not found' message, got: {data['detail']}"
        print(f"PASS: Void nonexistent payment returns 404 — {data['detail']}")


# ---------------------------------------------------------------------------
# Fix #3/#4: Expense delete — 404 for nonexistent, fund_source behavior
# ---------------------------------------------------------------------------

class TestExpenseDelete:
    """DELETE /api/expenses/{id} - uses original fund_source, 404 for nonexistent."""

    def test_delete_nonexistent_expense_returns_404(self, session):
        """DELETE /api/expenses/{nonexistent} → 404 Expense not found."""
        resp = session.delete(f"{BASE_URL}/api/expenses/{NONEXISTENT_ID}")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = str(data["detail"]).lower()
        assert "expense" in detail or "not found" in detail, \
            f"Expected 'Expense not found' message, got: {data['detail']}"
        print(f"PASS: Delete nonexistent expense returns 404 — {data['detail']}")

    def test_delete_already_voided_expense_returns_400(self, session, db):
        """DELETE /api/expenses/{voided_expense} → 400 already voided."""
        voided_id = f"TEST-EXP-V-{uuid.uuid4()}"
        db.expenses.insert_one({
            "id": voided_id,
            "branch_id": IPIL_BRANCH_ID,
            "category": "Utilities",
            "description": "Test voided expense",
            "amount": 10.0,
            "fund_source": "cashier",
            "voided": True,
            "voided_at": now_iso(),
            "created_by": "test",
            "created_at": now_iso(),
        })
        try:
            resp = session.delete(f"{BASE_URL}/api/expenses/{voided_id}")
            assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
            data = resp.json()
            detail = str(data.get("detail", "")).lower()
            assert "voided" in detail or "already" in detail, \
                f"Expected 'already voided' message, got: {data['detail']}"
            print(f"PASS: Delete already-voided expense returns 400 — {data['detail']}")
        finally:
            db.expenses.delete_many({"id": voided_id})


# ---------------------------------------------------------------------------
# Integration: verify all new endpoints are registered (not 404/405 from routing)
# ---------------------------------------------------------------------------

class TestEndpointRegistration:
    """Sanity check that all new endpoints respond properly (not 405 Method Not Allowed)."""

    def test_reopen_endpoint_exists(self, session):
        """POST /api/purchase-orders/{id}/reopen → must not return 405 (unregistered)."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}/reopen")
        # Should be 404 (PO not found) not 405 (method not allowed)
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /reopen endpoint registered — got {resp.status_code}")

    def test_void_return_endpoint_exists(self, session):
        """POST /api/returns/{id}/void → not 405."""
        resp = session.post(
            f"{BASE_URL}/api/returns/{NONEXISTENT_ID}/void",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /returns/void endpoint registered — got {resp.status_code}")

    def test_employee_advance_reverse_endpoint_exists(self, session):
        """POST /api/expenses/employee-advance/{id}/reverse → registered."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /employee-advance/reverse endpoint registered — got {resp.status_code}")

    def test_customer_cashout_reverse_endpoint_exists(self, session):
        """POST /api/expenses/customer-cashout/{id}/reverse → registered."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /customer-cashout/reverse endpoint registered — got {resp.status_code}")

    def test_invoice_void_payment_endpoint_exists(self, session):
        """POST /api/invoices/{id}/void-payment/{pid} → registered."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{NONEXISTENT_ID}/void-payment/{NONEXISTENT_ID}",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /void-payment endpoint registered — got {resp.status_code}")
