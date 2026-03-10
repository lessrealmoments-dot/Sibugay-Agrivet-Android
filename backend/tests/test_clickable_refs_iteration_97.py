"""
Test Suite: Clickable Transaction References - Iteration 97
Tests backend endpoints that support clickable references across the application:
- GET /api/audit/compute - returns audit data with expense reference_number fields
- GET /api/invoices/by-number/{number} - works for PO numbers (returns _collection=purchase_orders)
- GET /api/expenses/{expense_id} - returns expense data for modal display
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"


class TestAuth:
    """Authentication for test suite"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def api_client(self, auth_token):
        """Create authenticated session"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        })
        return session


class TestAuditCompute(TestAuth):
    """Test /api/audit/compute endpoint for clickable references"""
    
    def test_audit_compute_returns_data(self, api_client):
        """Test that audit compute returns valid response"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200, f"Audit compute failed: {response.text}"
        data = response.json()
        assert "cash" in data, "Missing 'cash' section in audit"
        assert "sales" in data, "Missing 'sales' section in audit"
        assert "unverified" in data, "Missing 'unverified' section in audit"
    
    def test_audit_cash_section_has_expenses(self, api_client):
        """Test cash section includes expenses with reference_number"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200
        data = response.json()
        cash = data.get("cash", {})
        expenses = cash.get("expenses", [])
        # If there are expenses, check they have the reference_number field
        if expenses:
            # At least check the structure is correct
            first_expense = expenses[0]
            assert "id" in first_expense, "Expense missing 'id'"
            assert "amount" in first_expense, "Expense missing 'amount'"
            # reference_number should be present (may be empty string)
            assert "reference_number" in first_expense, "Expense missing 'reference_number' field"
    
    def test_audit_unverified_section_has_expenses(self, api_client):
        """Test unverified section includes expenses with proper fields"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200
        data = response.json()
        unverified = data.get("unverified", {})
        expenses = unverified.get("expenses", [])
        # Check structure if expenses exist
        if expenses:
            first_expense = expenses[0]
            assert "id" in first_expense, "Unverified expense missing 'id'"
            assert "description" in first_expense, "Unverified expense missing 'description'"
            # reference_number should be present for clickable links
            assert "reference_number" in first_expense, "Unverified expense missing 'reference_number'"


class TestInvoiceByNumber(TestAuth):
    """Test /api/invoices/by-number/{number} endpoint for clickable references"""
    
    def test_get_invoice_by_invoice_number(self, api_client):
        """Test fetching an invoice by its invoice_number"""
        # First get a list of invoices to find a valid invoice number
        response = api_client.get(f"{BASE_URL}/api/invoices", params={"limit": 1})
        if response.status_code == 200:
            data = response.json()
            invoices = data.get("invoices", data if isinstance(data, list) else [])
            if invoices:
                inv_number = invoices[0].get("invoice_number")
                if inv_number:
                    # Now test the by-number endpoint
                    response = api_client.get(f"{BASE_URL}/api/invoices/by-number/{inv_number}")
                    assert response.status_code == 200, f"Failed to get invoice by number: {response.text}"
                    result = response.json()
                    assert result.get("_collection") == "invoices", "Expected _collection to be 'invoices'"
                    assert result.get("invoice_number") == inv_number, "Invoice number mismatch"
    
    def test_get_po_by_po_number(self, api_client):
        """Test fetching a PO by its po_number via by-number endpoint"""
        # Get a PO number from purchase orders
        response = api_client.get(f"{BASE_URL}/api/purchase-orders", params={"limit": 1})
        if response.status_code == 200:
            data = response.json()
            pos = data.get("orders", data if isinstance(data, list) else [])
            if pos:
                po_number = pos[0].get("po_number")
                if po_number:
                    # Test the by-number endpoint returns PO with _collection=purchase_orders
                    response = api_client.get(f"{BASE_URL}/api/invoices/by-number/{po_number}")
                    assert response.status_code == 200, f"Failed to get PO by number: {response.text}"
                    result = response.json()
                    assert result.get("_collection") == "purchase_orders", f"Expected _collection to be 'purchase_orders', got {result.get('_collection')}"
                    assert result.get("po_number") == po_number, "PO number mismatch"
    
    def test_invalid_number_returns_404(self, api_client):
        """Test that an invalid/nonexistent number returns 404"""
        response = api_client.get(f"{BASE_URL}/api/invoices/by-number/NONEXISTENT-12345-XYZ")
        assert response.status_code == 404, "Expected 404 for nonexistent number"


class TestExpenseEndpoint(TestAuth):
    """Test /api/expenses/{expense_id} endpoint for clickable references"""
    
    def test_get_expense_by_id(self, api_client):
        """Test fetching an expense by its ID"""
        # First get a list of expenses
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"limit": 1})
        if response.status_code == 200:
            data = response.json()
            expenses = data.get("expenses", [])
            if expenses:
                expense_id = expenses[0].get("id")
                if expense_id:
                    # Test getting the expense by ID
                    response = api_client.get(f"{BASE_URL}/api/expenses/{expense_id}")
                    assert response.status_code == 200, f"Failed to get expense: {response.text}"
                    result = response.json()
                    assert result.get("id") == expense_id, "Expense ID mismatch"
                    # Check required fields for InvoiceDetailModal
                    assert "amount" in result, "Expense missing 'amount'"
                    assert "category" in result or "description" in result, "Expense missing category/description"
    
    def test_invalid_expense_id_returns_404(self, api_client):
        """Test that an invalid expense ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/expenses/invalid-expense-id-xyz")
        assert response.status_code == 404, "Expected 404 for invalid expense ID"


class TestAuditPriorityActions(TestAuth):
    """Test that audit data contains fields needed for Priority Actions card"""
    
    def test_audit_payables_has_overdue_fields(self, api_client):
        """Test payables section has overdue_count and overdue_value"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200
        data = response.json()
        payables = data.get("payables", {})
        assert "overdue_count" in payables, "Missing 'overdue_count' in payables"
        assert "overdue_value" in payables, "Missing 'overdue_value' in payables"
    
    def test_audit_ar_has_aging_fields(self, api_client):
        """Test AR section has aging bucket fields"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200
        data = response.json()
        ar = data.get("ar", {})
        aging = ar.get("aging", {})
        # Check for 90+ days bucket
        assert "b90plus" in aging or "over_90" in aging, "Missing 90+ days aging bucket"
    
    def test_audit_transfers_has_shortage_fields(self, api_client):
        """Test transfers section has shortage fields"""
        response = api_client.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code == 200
        data = response.json()
        transfers = data.get("transfers", {})
        assert "with_shortage" in transfers, "Missing 'with_shortage' in transfers"


class TestAPIStatus(TestAuth):
    """Basic API status tests"""
    
    def test_auth_endpoint(self, api_client):
        """Test auth is working"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
    
    def test_protected_endpoint_requires_auth(self):
        """Test that protected endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/audit/compute")
        assert response.status_code in [401, 403], "Protected endpoint should require auth"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
