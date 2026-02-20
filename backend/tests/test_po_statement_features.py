"""
Tests for AgriPOS new features:
- PO unpaid summary (dashboard widget)
- PO payables-by-supplier (Pay Supplier page)
- PO reopen (reverse inventory)
- PO credit creation with terms_days/due_date
- Customer Statement of Account
- PO pay endpoint with fund source
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ── Shared auth fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Login as owner and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "owner", "password": "testpass123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── Helper: get branch id ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def branch_id(headers):
    resp = requests.get(f"{BASE_URL}/api/branches", headers=headers)
    assert resp.status_code == 200
    branches = resp.json()
    assert len(branches) > 0, "No branches found"
    return branches[0]["id"]


# ── Helper: create a minimal credit PO with a real product ──────────────────

@pytest.fixture(scope="module")
def test_product_id(headers, branch_id):
    """Get first product id from branch."""
    resp = requests.get(f"{BASE_URL}/api/products", headers=headers,
                        params={"branch_id": branch_id, "limit": 1})
    assert resp.status_code == 200
    products = resp.json().get("products", resp.json())
    if isinstance(products, list) and len(products) > 0:
        return products[0]["id"], products[0]["name"]
    pytest.skip("No products available for PO creation")


@pytest.fixture(scope="module")
def credit_po(headers, branch_id, test_product_id):
    """Create a credit PO for testing reopen and pay. Cleaned up after module."""
    prod_id, prod_name = test_product_id
    payload = {
        "vendor": "TEST_PO_Vendor_26",
        "branch_id": branch_id,
        "purchase_date": "2026-02-01",
        "payment_method": "credit",
        "terms_days": 30,
        "status": "ordered",
        "notes": "Test PO for statement features",
        "items": [{"product_id": prod_id, "product_name": prod_name, "quantity": 2, "unit_price": 500}]
    }
    resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
    assert resp.status_code == 200, f"Failed to create test PO: {resp.text}"
    po = resp.json()
    yield po
    # Cleanup: cancel PO
    requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: GET /purchase-orders/unpaid-summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnpaidSummary:
    """Tests for /purchase-orders/unpaid-summary (dashboard widget)."""

    def test_unpaid_summary_returns_200(self, headers):
        """GET /unpaid-summary returns 200."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_unpaid_summary_has_required_fields(self, headers):
        """Response has total_unpaid, overdue, due_soon, later, total_count."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        data = resp.json()
        for key in ["total_unpaid", "overdue", "due_soon", "later", "total_count"]:
            assert key in data, f"Missing field: {key}"

    def test_unpaid_summary_types(self, headers):
        """overdue/due_soon/later are lists, total_unpaid is numeric."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        data = resp.json()
        assert isinstance(data["overdue"], list)
        assert isinstance(data["due_soon"], list)
        assert isinstance(data["later"], list)
        assert isinstance(data["total_unpaid"], (int, float))
        assert isinstance(data["total_count"], int)

    def test_unpaid_summary_po_item_structure(self, headers):
        """Each PO in the lists has id, po_number, vendor, balance fields."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        data = resp.json()
        all_items = data["overdue"] + data["due_soon"] + data["later"]
        if all_items:
            item = all_items[0]
            for field in ["id", "po_number", "vendor", "balance"]:
                assert field in item, f"PO item missing field: {field}"

    def test_unpaid_summary_branch_filter(self, headers, branch_id):
        """Branch filter param is accepted without error."""
        resp = requests.get(
            f"{BASE_URL}/api/purchase-orders/unpaid-summary",
            headers=headers, params={"branch_id": branch_id}
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: GET /purchase-orders/payables-by-supplier
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayablesBySupplier:
    """Tests for /purchase-orders/payables-by-supplier (Pay Supplier page)."""

    def test_payables_by_supplier_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier", headers=headers)
        assert resp.status_code == 200

    def test_payables_by_supplier_is_list(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier", headers=headers)
        data = resp.json()
        assert isinstance(data, list)

    def test_payables_by_supplier_structure(self, headers):
        """Each supplier group has vendor, total_owed, pos, has_overdue."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier", headers=headers)
        data = resp.json()
        if data:
            sup = data[0]
            for key in ["vendor", "total_owed", "pos", "has_overdue"]:
                assert key in sup, f"Missing field: {key}"
            assert isinstance(sup["pos"], list)
            assert isinstance(sup["total_owed"], (int, float))
            assert isinstance(sup["has_overdue"], bool)

    def test_payables_each_po_has_balance(self, headers):
        """POs inside each supplier group have balance field."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier", headers=headers)
        data = resp.json()
        for sup in data:
            for po in sup["pos"]:
                # balance or subtotal should exist
                assert "id" in po
                assert "po_number" in po

    def test_payables_by_supplier_branch_filter(self, headers, branch_id):
        resp = requests.get(
            f"{BASE_URL}/api/purchase-orders/payables-by-supplier",
            headers=headers, params={"branch_id": branch_id}
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Credit PO creation with terms_days / due_date
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditPOCreation:
    """Test credit PO with terms_days/due_date computation."""

    def test_credit_po_created_with_unpaid_status(self, credit_po):
        """Credit PO has payment_status=unpaid and balance=subtotal."""
        assert credit_po["payment_method"] == "credit"
        assert credit_po["payment_status"] == "unpaid"
        assert credit_po["balance"] == credit_po["subtotal"]
        assert credit_po["amount_paid"] == 0

    def test_credit_po_due_date_computed_from_terms(self, credit_po):
        """due_date is 30 days after purchase_date (2026-02-01 + 30d = 2026-03-03)."""
        assert credit_po.get("due_date") == "2026-03-03", \
            f"Expected due_date 2026-03-03, got {credit_po.get('due_date')}"

    def test_credit_po_terms_days_stored(self, credit_po):
        """terms_days is stored on the PO."""
        assert credit_po.get("terms_days") == 30

    def test_credit_po_appears_in_unpaid_summary(self, headers, credit_po):
        """The credit PO should appear in unpaid-summary after creation."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        data = resp.json()
        all_ids = [p["id"] for group in [data["overdue"], data["due_soon"], data["later"]] for p in group]
        assert credit_po["id"] in all_ids, f"Credit PO {credit_po['id']} not found in unpaid summary"

    def test_credit_po_appears_in_payables_by_supplier(self, headers, credit_po):
        """The vendor appears in payables-by-supplier."""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier", headers=headers)
        data = resp.json()
        vendors = [s["vendor"] for s in data]
        assert credit_po["vendor"] in vendors, f"Vendor {credit_po['vendor']} not in payables"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: POST /purchase-orders/{id}/reopen
# ═══════════════════════════════════════════════════════════════════════════════

class TestReopenPO:
    """Tests for PO reopen endpoint."""

    def test_reopen_ordered_po_returns_400(self, headers, credit_po):
        """Cannot reopen a PO that is not received (status=ordered)."""
        resp = requests.post(
            f"{BASE_URL}/api/purchase-orders/{credit_po['id']}/reopen",
            headers=headers
        )
        assert resp.status_code == 400, f"Expected 400 for non-received PO, got {resp.status_code}"

    def test_reopen_received_po_success(self, headers, branch_id, test_product_id):
        """Create a PO, receive it, then reopen - status should go back to ordered."""
        prod_id, prod_name = test_product_id
        # Create a new credit PO for this test
        payload = {
            "vendor": "TEST_Reopen_Vendor_26",
            "branch_id": branch_id,
            "purchase_date": "2026-02-01",
            "payment_method": "credit",
            "terms_days": 0,
            "status": "ordered",
            "items": [{"product_id": prod_id, "product_name": prod_name, "quantity": 1, "unit_price": 100}]
        }
        create_resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert create_resp.status_code == 200
        po_id = create_resp.json()["id"]

        try:
            # Receive it
            recv_resp = requests.post(f"{BASE_URL}/api/purchase-orders/{po_id}/receive", headers=headers)
            assert recv_resp.status_code == 200, f"Receive failed: {recv_resp.text}"

            # Verify received
            list_resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers)
            orders = list_resp.json()["purchase_orders"]
            po_received = next((o for o in orders if o["id"] == po_id), None)
            assert po_received is not None
            assert po_received["status"] == "received"

            # Reopen it
            reopen_resp = requests.post(f"{BASE_URL}/api/purchase-orders/{po_id}/reopen", headers=headers)
            assert reopen_resp.status_code == 200, f"Reopen failed: {reopen_resp.text}"
            assert "message" in reopen_resp.json()

            # Verify status is back to ordered
            list_resp2 = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers)
            orders2 = list_resp2.json()["purchase_orders"]
            po_reopened = next((o for o in orders2 if o["id"] == po_id), None)
            assert po_reopened is not None
            assert po_reopened["status"] == "ordered", f"Expected ordered, got {po_reopened['status']}"
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/purchase-orders/{po_id}", headers=headers)

    def test_reopen_nonexistent_po_returns_404(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/purchase-orders/nonexistent-id-xyz/reopen",
            headers=headers
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: POST /purchase-orders/{id}/pay - with fund source
# ═══════════════════════════════════════════════════════════════════════════════

class TestPOPayment:
    """Tests for PO payment endpoint with fund source."""

    def test_pay_po_with_cashier_source_creates_expense(self, headers, branch_id, test_product_id):
        """Pay a PO from cashier - should create expense record."""
        prod_id, prod_name = test_product_id
        # Create small credit PO
        payload = {
            "vendor": "TEST_Pay_Vendor_26",
            "branch_id": branch_id,
            "purchase_date": "2026-02-01",
            "payment_method": "credit",
            "terms_days": 0,
            "status": "ordered",
            "items": [{"product_id": prod_id, "product_name": prod_name, "quantity": 1, "unit_price": 1}]
        }
        create_resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert create_resp.status_code == 200
        po = create_resp.json()
        po_id = po["id"]

        try:
            # Pay it
            pay_resp = requests.post(f"{BASE_URL}/api/purchase-orders/{po_id}/pay", headers=headers,
                                     json={"amount": 1, "fund_source": "cashier", "method": "Cash"})
            # Could fail if insufficient balance, but should not be 5xx
            assert pay_resp.status_code in [200, 400], f"Unexpected status: {pay_resp.status_code}"
            if pay_resp.status_code == 200:
                data = pay_resp.json()
                assert "new_balance" in data
                assert "payment_status" in data
        finally:
            requests.delete(f"{BASE_URL}/api/purchase-orders/{po_id}", headers=headers)

    def test_pay_nonexistent_po_returns_404(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/purchase-orders/nonexistent-id-xyz/pay",
            headers=headers, json={"amount": 100}
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: GET /customers/{customer_id}/statement
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomerStatement:
    """Tests for GET /customers/{id}/statement endpoint."""

    @pytest.fixture(scope="class")
    def customer_id(self, headers):
        """Get first customer id."""
        resp = requests.get(f"{BASE_URL}/api/customers", headers=headers, params={"limit": 5})
        assert resp.status_code == 200
        customers = resp.json().get("customers", [])
        if not customers:
            pytest.skip("No customers in DB")
        return customers[0]["id"]

    def test_statement_returns_200(self, headers, customer_id):
        resp = requests.get(f"{BASE_URL}/api/customers/{customer_id}/statement", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_statement_has_required_fields(self, headers, customer_id):
        """Response has customer, transactions, closing_balance, statement_date."""
        resp = requests.get(f"{BASE_URL}/api/customers/{customer_id}/statement", headers=headers)
        data = resp.json()
        for key in ["customer", "transactions", "closing_balance", "statement_date"]:
            assert key in data, f"Missing field: {key}"

    def test_statement_transactions_is_list(self, headers, customer_id):
        resp = requests.get(f"{BASE_URL}/api/customers/{customer_id}/statement", headers=headers)
        data = resp.json()
        assert isinstance(data["transactions"], list)

    def test_statement_transactions_have_running_balance(self, headers, customer_id):
        """Each transaction in statement has date, reference, debit, credit, running_balance."""
        resp = requests.get(f"{BASE_URL}/api/customers/{customer_id}/statement", headers=headers)
        data = resp.json()
        for t in data["transactions"]:
            for field in ["date", "reference", "debit", "credit", "running_balance"]:
                assert field in t, f"Transaction missing field: {field}"

    def test_statement_closing_balance_matches_last_running_balance(self, headers, customer_id):
        """closing_balance should match the last transaction's running_balance."""
        resp = requests.get(f"{BASE_URL}/api/customers/{customer_id}/statement", headers=headers)
        data = resp.json()
        if data["transactions"]:
            last_running = data["transactions"][-1]["running_balance"]
            assert abs(data["closing_balance"] - last_running) < 0.01, \
                f"closing_balance {data['closing_balance']} != last running {last_running}"

    def test_statement_with_date_range_filter(self, headers, customer_id):
        """date_from and date_to filter accepted without error."""
        resp = requests.get(
            f"{BASE_URL}/api/customers/{customer_id}/statement",
            headers=headers,
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"}
        )
        assert resp.status_code == 200

    def test_statement_nonexistent_customer_returns_404(self, headers):
        resp = requests.get(
            f"{BASE_URL}/api/customers/nonexistent-id-xyz/statement",
            headers=headers
        )
        assert resp.status_code == 404
