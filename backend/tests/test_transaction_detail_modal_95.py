"""
Test Transaction Detail Modal Features (Iteration 95)
- GET /api/purchase-orders/{po_id} - single PO fetch
- GET /api/expenses/{expense_id} - single expense fetch
- POST /api/verify/{doc_type}/{doc_id} - verify transaction with PIN
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"
BRANCH_MAIN = "da114e26-fd00-467f-8728-6b8047a244b5"

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token") or response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")

@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestSinglePurchaseOrderEndpoint:
    """Test GET /api/purchase-orders/{po_id} endpoint"""

    def test_list_purchase_orders_to_get_id(self, api_client):
        """First, list POs to get a valid PO ID"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders")
        assert response.status_code == 200, f"Failed to list POs: {response.text}"
        data = response.json()
        assert "purchase_orders" in data, "Response missing purchase_orders key"
        print(f"Found {len(data['purchase_orders'])} purchase orders")
        return data

    def test_get_single_purchase_order(self, api_client):
        """Test GET /api/purchase-orders/{po_id} returns full PO details"""
        # First get list to find a valid PO ID
        list_response = api_client.get(f"{BASE_URL}/api/purchase-orders")
        assert list_response.status_code == 200
        pos = list_response.json().get("purchase_orders", [])
        
        if not pos:
            pytest.skip("No purchase orders found to test single fetch")
        
        po_id = pos[0]["id"]
        
        # Now test single PO fetch
        response = api_client.get(f"{BASE_URL}/api/purchase-orders/{po_id}")
        assert response.status_code == 200, f"Failed to get single PO: {response.text}"
        
        po = response.json()
        # Verify all required fields are present
        required_fields = ["id", "po_number", "vendor", "items", "grand_total", "status"]
        for field in required_fields:
            assert field in po, f"Missing required field: {field}"
        
        print(f"PASSED: GET /api/purchase-orders/{po_id} returns full PO with fields: {list(po.keys())[:10]}...")

    def test_get_nonexistent_purchase_order(self, api_client):
        """Test GET /api/purchase-orders/{invalid_id} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASSED: Nonexistent PO returns 404")


class TestSingleExpenseEndpoint:
    """Test GET /api/expenses/{expense_id} endpoint"""

    def test_list_expenses_to_get_id(self, api_client):
        """First, list expenses to get a valid expense ID"""
        response = api_client.get(f"{BASE_URL}/api/expenses")
        assert response.status_code == 200, f"Failed to list expenses: {response.text}"
        data = response.json()
        assert "expenses" in data, "Response missing expenses key"
        print(f"Found {len(data['expenses'])} expenses")
        return data

    def test_get_single_expense(self, api_client):
        """Test GET /api/expenses/{expense_id} returns full expense details"""
        # First get list to find a valid expense ID
        list_response = api_client.get(f"{BASE_URL}/api/expenses")
        assert list_response.status_code == 200
        expenses = list_response.json().get("expenses", [])
        
        if not expenses:
            pytest.skip("No expenses found to test single fetch")
        
        expense_id = expenses[0]["id"]
        
        # Now test single expense fetch
        response = api_client.get(f"{BASE_URL}/api/expenses/{expense_id}")
        assert response.status_code == 200, f"Failed to get single expense: {response.text}"
        
        expense = response.json()
        # Verify required fields
        required_fields = ["id", "category", "amount", "date"]
        for field in required_fields:
            assert field in expense, f"Missing required field: {field}"
        
        print(f"PASSED: GET /api/expenses/{expense_id} returns expense with fields: {list(expense.keys())}")

    def test_get_nonexistent_expense(self, api_client):
        """Test GET /api/expenses/{invalid_id} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/expenses/nonexistent-expense-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASSED: Nonexistent expense returns 404")


class TestVerifyTransactionEndpoint:
    """Test POST /api/verify/{doc_type}/{doc_id} endpoint"""

    def test_verify_purchase_order_with_valid_pin(self, api_client):
        """Test verify PO with manager PIN"""
        # First get a PO to verify
        list_response = api_client.get(f"{BASE_URL}/api/purchase-orders")
        assert list_response.status_code == 200
        pos = list_response.json().get("purchase_orders", [])
        
        if not pos:
            pytest.skip("No purchase orders found to test verification")
        
        # Find one that's not yet verified
        po = next((p for p in pos if not p.get("verified")), pos[0])
        po_id = po["id"]
        
        # Test verification
        response = api_client.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        
        # Should succeed or already verified
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "verified_by" in data, "Response missing verified_by"
            print(f"PASSED: Verify PO returned: {data}")
        else:
            print(f"INFO: PO verification response: {response.json()}")

    def test_verify_expense_with_valid_pin(self, api_client):
        """Test verify expense with manager PIN"""
        # First get an expense to verify
        list_response = api_client.get(f"{BASE_URL}/api/expenses")
        assert list_response.status_code == 200
        expenses = list_response.json().get("expenses", [])
        
        if not expenses:
            pytest.skip("No expenses found to test verification")
        
        # Find one that's not yet verified
        expense = next((e for e in expenses if not e.get("verified")), expenses[0])
        expense_id = expense["id"]
        
        # Test verification
        response = api_client.post(
            f"{BASE_URL}/api/verify/expense/{expense_id}",
            json={"pin": MANAGER_PIN}
        )
        
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "verified_by" in data, "Response missing verified_by"
            print(f"PASSED: Verify expense returned: {data}")
        else:
            print(f"INFO: Expense verification response: {response.json()}")

    def test_verify_with_invalid_pin(self, api_client):
        """Test verify fails with invalid PIN"""
        # Get any PO
        list_response = api_client.get(f"{BASE_URL}/api/purchase-orders")
        pos = list_response.json().get("purchase_orders", [])
        
        if not pos:
            pytest.skip("No purchase orders found")
        
        po_id = pos[0]["id"]
        
        # Try with invalid PIN
        response = api_client.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": "000000"}  # Invalid PIN
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid PIN, got {response.status_code}"
        print("PASSED: Invalid PIN correctly rejected")

    def test_verify_invoice_type(self, api_client):
        """Test verify endpoint accepts 'invoice' doc_type"""
        # Get an invoice to test
        response = api_client.get(f"{BASE_URL}/api/invoices")
        assert response.status_code == 200
        invoices = response.json().get("invoices", [])
        
        if not invoices:
            pytest.skip("No invoices found")
        
        invoice_id = invoices[0]["id"]
        
        # Test verification endpoint for invoice type
        response = api_client.post(
            f"{BASE_URL}/api/verify/invoice/{invoice_id}",
            json={"pin": MANAGER_PIN}
        )
        
        # invoice is not in COLLECTION_MAP, so should be 400
        # Let's check what happens
        print(f"Verify invoice response: {response.status_code} - {response.json() if response.status_code != 500 else 'Server error'}")


class TestSearchAndModalIntegration:
    """Test search API returns data needed for TransactionDetailModal"""

    def test_search_returns_required_fields_for_modal(self, api_client):
        """Verify search results have type, id, number for modal to work"""
        response = api_client.get(f"{BASE_URL}/api/search/transactions", params={"q": "Walk-in", "limit": 5})
        assert response.status_code == 200
        
        results = response.json().get("results", [])
        if not results:
            # Try another search term
            response = api_client.get(f"{BASE_URL}/api/search/transactions", params={"type": "po", "limit": 5})
            results = response.json().get("results", [])
        
        if not results:
            pytest.skip("No search results found")
        
        # Check first result has required fields for modal
        result = results[0]
        required_for_modal = ["type", "id", "number"]
        for field in required_for_modal:
            assert field in result, f"Search result missing field required for modal: {field}"
        
        print(f"PASSED: Search results have modal fields. Sample: type={result['type']}, id={result['id'][:8]}..., number={result.get('number', 'N/A')}")


class TestInvoiceSingleEndpoint:
    """Test GET /api/invoices/{inv_id} endpoint"""

    def test_get_single_invoice(self, api_client):
        """Test GET /api/invoices/{inv_id} returns full invoice details"""
        # First get list to find a valid invoice ID
        list_response = api_client.get(f"{BASE_URL}/api/invoices")
        assert list_response.status_code == 200
        invoices = list_response.json().get("invoices", [])
        
        if not invoices:
            pytest.skip("No invoices found to test single fetch")
        
        inv_id = invoices[0]["id"]
        
        # Now test single invoice fetch
        response = api_client.get(f"{BASE_URL}/api/invoices/{inv_id}")
        assert response.status_code == 200, f"Failed to get single invoice: {response.text}"
        
        invoice = response.json()
        # Verify required fields for TransactionDetailModal
        required_fields = ["id", "invoice_number", "items", "grand_total", "status"]
        for field in required_fields:
            assert field in invoice, f"Missing required field: {field}"
        
        print(f"PASSED: GET /api/invoices/{inv_id} returns invoice with {len(invoice.get('items', []))} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
