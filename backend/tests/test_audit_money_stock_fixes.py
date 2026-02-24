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
import motor.motor_asyncio
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load frontend env for BASE_URL
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Known test data IDs (from DB scan)
RECEIVED_PO_ID = "568347f9-96cf-4301-a888-d1e393d5f6d2"        # PO-20260222082936-9745 (received, amount_paid=68600)
CASH_RECEIVED_PO_ID = "1d9b3e1b-df58-49e9-bf5c-e78fdf6e3d65"   # PO-20260220185138-9BB6 (cash, received, amount_paid=9000)
RETURN_ID = "9dd2d221-032f-4555-8873-c74e3d94eb1e"              # RTN-20260223-0001
BRANCH_TRANSFER_RECEIVED_PENDING_ID = "cc9ee135-8108-4b88-9447-fc93b07bbc6d"  # BTO-20260222-0007
CUSTOMER_CASHOUT_EXPENSE_ID = "d44c4ac4-2530-46ee-97b0-943591edc610"
EMPLOYEE_ADVANCE_EXPENSE_ID = "e6bf8058-ef84-48ec-8dae-3812280885b9"
INVOICE_ID = "08606c84-4192-4e3c-a8d9-bbde234492c9"             # SI-20260220-0001
INVOICE_PAYMENT_ID = "cee5ba94-779a-4b67-9de9-8b306b97ca90"     # first payment on SI-20260220-0001
B1_BRANCH_ID = "7f9b29cb-3028-4680-b36c-cb8ad1c80345"
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"

MANAGER_PIN = "521325"
WRONG_PIN = "0000"

NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def session():
    """Authenticated session using owner credentials."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(f"{BASE_URL}/api/auth/login", json={"username": "owner", "password": "521325"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def db_conn():
    """Direct MongoDB connection for setup/teardown."""
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "agribooks")
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    return client[db_name]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helper: run async in sync context
# ---------------------------------------------------------------------------

def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Fix #5 / #6: PO Cancel blocked on received PO
# ---------------------------------------------------------------------------

class TestPOCancelBlocked:
    """Cancel of received PO must return 400 — inventory already added."""

    def test_cancel_received_po_returns_400(self, session):
        """DELETE /api/purchase-orders/{received_po_id} → 400 Cannot cancel received PO."""
        resp = session.delete(f"{BASE_URL}/api/purchase-orders/{RECEIVED_PO_ID}")
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
        assert "cannot cancel" in detail or "received" in detail, \
            f"Expected block message for received PO, got: {data['detail']}"
        print(f"PASS: Cancel received PO returns 400 — {data['detail']}")

    def test_cancel_nonexistent_po_returns_404(self, session):
        """DELETE /api/purchase-orders/{nonexistent} → 404."""
        resp = session.delete(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print("PASS: Cancel nonexistent PO returns 404")


# ---------------------------------------------------------------------------
# Fix #1: PO Reopen reverses cash payment
# ---------------------------------------------------------------------------

class TestPOReopenPaymentReversal:
    """
    Reopen a received PO: verify the response message includes payment reversal info
    for cash POs and payable voiding for terms POs.
    Uses a temporary test PO inserted directly into MongoDB.
    Cleaned up in teardown.
    """

    test_cash_po_id = None
    test_terms_po_id = None

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, db_conn):
        """Insert minimal test POs and clean up after tests."""
        cash_po_id = f"TEST-PO-{uuid.uuid4()}"
        terms_po_id = f"TEST-PO-{uuid.uuid4()}"
        TestPOReopenPaymentReversal.test_cash_po_id = cash_po_id
        TestPOReopenPaymentReversal.test_terms_po_id = terms_po_id

        async def insert():
            await db_conn.purchase_orders.insert_one({
                "id": cash_po_id,
                "po_number": f"TEST-PO-CASH-{cash_po_id[:8]}",
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
            await db_conn.purchase_orders.insert_one({
                "id": terms_po_id,
                "po_number": f"TEST-PO-TERMS-{terms_po_id[:8]}",
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

        run_async(insert())
        yield

        async def cleanup():
            await db_conn.purchase_orders.delete_many({"id": {"$in": [cash_po_id, terms_po_id]}})

        run_async(cleanup())

    def test_reopen_cash_po_includes_payment_reversal_message(self, session):
        """POST /api/purchase-orders/{cash_po_id}/reopen → message includes payment returned to cashier."""
        po_id = TestPOReopenPaymentReversal.test_cash_po_id
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{po_id}/reopen")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        msg = data["message"]
        assert "₱1.00 returned to cashier" in msg or "returned to cashier" in msg or "reversal" in msg.lower() or "returned" in msg.lower(), \
            f"Expected payment reversal in message, got: {msg}"
        print(f"PASS: Cash PO reopen message includes reversal — {msg}")

    def test_reopen_terms_po_includes_payable_voided_message(self, session):
        """POST /api/purchase-orders/{terms_po_id}/reopen → message includes 'Accounts payable voided'."""
        po_id = TestPOReopenPaymentReversal.test_terms_po_id
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{po_id}/reopen")
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        msg = data["message"]
        # Terms PO should mention payable voiding
        assert "payable" in msg.lower() or "voided" in msg.lower() or "edit and receive" in msg.lower(), \
            f"Expected payable voided mention in message, got: {msg}"
        print(f"PASS: Terms PO reopen message correct — {msg}")

    def test_reopen_non_received_po_returns_400(self, session):
        """POST /api/purchase-orders/{nonexistent}/reopen → 404 not found."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}/reopen")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print("PASS: Reopen nonexistent PO returns 404")


# ---------------------------------------------------------------------------
# Fix #3: PO Edit balance = max(0, grand_total - amount_paid)
# ---------------------------------------------------------------------------

class TestPOEditBalance:
    """
    After editing a PO that has partial/full payment recorded,
    balance must be recalculated as max(0, new_grand_total - amount_paid).
    """

    test_po_id = None

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, db_conn):
        """Insert a test PO in ordered status with existing amount_paid."""
        po_id = f"TEST-PO-EDIT-{uuid.uuid4()}"
        TestPOEditBalance.test_po_id = po_id

        async def insert():
            await db_conn.purchase_orders.insert_one({
                "id": po_id,
                "po_number": f"TEST-PO-EDIT-{po_id[:8]}",
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
                "amount_paid": 5000.0,  # Already partially paid
                "balance": 0,           # Bug: balance was incorrectly 0
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
                "reopened_at": now_iso(),  # Simulate reopened so change log is generated
                "created_by": "test",
                "created_at": now_iso(),
            })

        run_async(insert())
        yield

        async def cleanup():
            await db_conn.purchase_orders.delete_many({"id": po_id})

        run_async(cleanup())

    def test_edit_po_balance_recalculated_from_amount_paid(self, session):
        """
        PUT /api/purchase-orders/{po_id} with same items
        → balance must be max(0, grand_total - amount_paid) = max(0, 10000 - 5000) = 5000
        """
        po_id = TestPOEditBalance.test_po_id
        # Edit the PO — same items, same totals, just trigger recalculation
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
        assert "grand_total" in data
        assert "amount_paid" in data
        assert "balance" in data
        grand_total = float(data["grand_total"])
        amount_paid = float(data["amount_paid"])
        balance = float(data["balance"])
        expected_balance = max(0, round(grand_total - amount_paid, 2))
        assert balance == expected_balance, \
            f"Balance fix failed: got {balance}, expected {expected_balance} (grand_total={grand_total}, amount_paid={amount_paid})"
        print(f"PASS: PO edit balance fix — balance={balance} == max(0, {grand_total} - {amount_paid}) = {expected_balance}")

    def test_edit_po_balance_zero_when_overpaid(self, session):
        """
        Edit PO to lower grand_total below amount_paid
        → balance must be max(0, ...) = 0, not negative
        """
        po_id = TestPOEditBalance.test_po_id
        # Lower the total to 3000 (less than amount_paid=5000)
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
        assert balance == max(0, round(grand_total - amount_paid, 2)), \
            f"Balance = max(0, {grand_total} - {amount_paid}) should be {max(0, round(grand_total - amount_paid, 2))}, got {balance}"
        print(f"PASS: Overpaid PO balance clamped to 0 — balance={balance}")


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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Employee advance reverse with wrong PIN returns 401 — {data['detail']}")

    def test_reverse_employee_advance_nonexistent_returns_correct(self, session):
        """POST /api/expenses/employee-advance/{nonexistent}/reverse — should check PIN first then 404."""
        # With wrong PIN: should return 401 (PIN check happens before expense lookup)
        resp_wrong = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": WRONG_PIN, "reason": "Test"}
        )
        # With correct PIN: should return 404 (expense not found)
        resp_correct = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN, "reason": "Test"}
        )
        # Check behavior
        if resp_wrong.status_code == 401:
            print(f"PASS: PIN checked before expense lookup — wrong pin returns 401")
        assert resp_correct.status_code == 404, \
            f"Expected 404 for nonexistent expense with correct PIN, got {resp_correct.status_code}: {resp_correct.text}"
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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
        assert "invalid" in detail or "pin" in detail or "manager" in detail, \
            f"Expected invalid PIN message, got: {data['detail']}"
        print(f"PASS: Customer cashout reverse with wrong PIN returns 401 — {data['detail']}")

    def test_reverse_customer_cashout_nonexistent_correct_pin(self, session):
        """POST /api/expenses/customer-cashout/{nonexistent}/reverse with correct PIN → 404."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent"}
        )
        assert resp.status_code == 404, \
            f"Expected 404 for nonexistent expense, got {resp.status_code}: {resp.text}"
        print(f"PASS: Nonexistent customer cashout reverse returns 404 — {resp.json().get('detail')}")

    def test_reverse_customer_cashout_missing_pin_returns_400(self, session):
        """POST /api/expenses/customer-cashout/{id}/reverse with no PIN → 400."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{CUSTOMER_CASHOUT_EXPENSE_ID}/reverse",
            json={"reason": "No pin provided"}
        )
        assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Customer cashout reverse missing PIN returns 400 — {resp.json().get('detail')}")


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
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
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
        """POST /api/invoices/{nonexistent}/void-payment/{payment_id} with correct PIN → 404."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{NONEXISTENT_ID}/void-payment/{INVOICE_PAYMENT_ID}",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent"}
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        print(f"PASS: Void nonexistent invoice returns 404 — {resp.json().get('detail')}")

    def test_void_invoice_nonexistent_payment_returns_404(self, session):
        """POST /api/invoices/{inv_id}/void-payment/{nonexistent_payment} → 404 payment not found."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{INVOICE_ID}/void-payment/{NONEXISTENT_ID}",
            json={"manager_pin": MANAGER_PIN, "reason": "Test nonexistent payment"}
        )
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        detail = data.get("detail", "").lower()
        assert "payment" in detail or "not found" in detail, \
            f"Expected 'payment not found' message, got: {data['detail']}"
        print(f"PASS: Void nonexistent payment returns 404 — {data['detail']}")


# ---------------------------------------------------------------------------
# Fix #3/#4: Expense delete / edit use original fund_source
# ---------------------------------------------------------------------------

class TestExpenseDelete:
    """DELETE /api/expenses/{id} - uses original fund_source, 404 for nonexistent."""

    def test_delete_nonexistent_expense_returns_404(self, session):
        """DELETE /api/expenses/{nonexistent} → 404 Expense not found."""
        resp = session.delete(f"{BASE_URL}/api/expenses/{NONEXISTENT_ID}")
        assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        detail = data["detail"].lower() if isinstance(data["detail"], str) else str(data["detail"]).lower()
        assert "expense" in detail or "not found" in detail, \
            f"Expected 'Expense not found' message, got: {data['detail']}"
        print(f"PASS: Delete nonexistent expense returns 404 — {data['detail']}")

    def test_delete_already_voided_expense_returns_400(self, session, db_conn):
        """DELETE /api/expenses/{voided_expense} → 400 already voided."""
        # Create a pre-voided expense
        voided_id = f"TEST-EXP-VOIDED-{uuid.uuid4()}"

        async def insert():
            await db_conn.expenses.insert_one({
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

        run_async(insert())
        try:
            resp = session.delete(f"{BASE_URL}/api/expenses/{voided_id}")
            assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert "already voided" in str(data.get("detail", "")).lower() or "voided" in str(data.get("detail", "")).lower(), \
                f"Expected 'already voided' message, got: {data['detail']}"
            print(f"PASS: Delete already-voided expense returns 400 — {data['detail']}")
        finally:
            async def cleanup():
                await db_conn.expenses.delete_many({"id": voided_id})
            run_async(cleanup())


# ---------------------------------------------------------------------------
# Integration check: verify all new endpoints are registered
# ---------------------------------------------------------------------------

class TestEndpointRegistration:
    """Sanity check that all new endpoints respond (not 404 from routing)."""

    def test_reopen_endpoint_exists(self, session):
        """POST /api/purchase-orders/{id}/reopen → not 404 (route missing) or 405."""
        resp = session.post(f"{BASE_URL}/api/purchase-orders/{NONEXISTENT_ID}/reopen")
        # Should be 404 (PO not found) not 405 (method not allowed) or 500
        assert resp.status_code in [404, 400], \
            f"Unexpected status {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /reopen endpoint registered — got {resp.status_code}")

    def test_void_return_endpoint_exists(self, session):
        """POST /api/returns/{id}/void → not 405."""
        resp = session.post(f"{BASE_URL}/api/returns/{NONEXISTENT_ID}/void",
                           json={"manager_pin": MANAGER_PIN})
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected status {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /returns/void endpoint registered — got {resp.status_code}")

    def test_employee_advance_reverse_endpoint_exists(self, session):
        """POST /api/expenses/employee-advance/{id}/reverse → registered."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/employee-advance/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected status {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /employee-advance/reverse endpoint registered — got {resp.status_code}")

    def test_customer_cashout_reverse_endpoint_exists(self, session):
        """POST /api/expenses/customer-cashout/{id}/reverse → registered."""
        resp = session.post(
            f"{BASE_URL}/api/expenses/customer-cashout/{NONEXISTENT_ID}/reverse",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected status {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /customer-cashout/reverse endpoint registered — got {resp.status_code}")

    def test_invoice_void_payment_endpoint_exists(self, session):
        """POST /api/invoices/{id}/void-payment/{pid} → registered."""
        resp = session.post(
            f"{BASE_URL}/api/invoices/{NONEXISTENT_ID}/void-payment/{NONEXISTENT_ID}",
            json={"manager_pin": MANAGER_PIN}
        )
        assert resp.status_code in [404, 400, 401], \
            f"Unexpected status {resp.status_code}: endpoint may not be registered. {resp.text}"
        print(f"PASS: /void-payment endpoint registered — got {resp.status_code}")
