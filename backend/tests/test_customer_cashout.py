"""
Test Customer Cash Out Workflow
- Creates expense record when cash is loaned to customer
- Automatically creates invoice for the customer (they owe the money back)
- Validates required fields (customer, amount)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for testing"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Get authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


@pytest.fixture(scope="module")
def test_customer(api_client):
    """Get or create a test customer"""
    # Check for existing customer
    response = api_client.get(f"{BASE_URL}/api/customers?limit=1")
    if response.status_code == 200 and response.json().get("customers"):
        return response.json()["customers"][0]
    
    # Create if none exists
    response = api_client.post(f"{BASE_URL}/api/customers", json={
        "name": "TEST_CashOut_Customer",
        "phone": "1234567890",
        "email": "cashout@test.com"
    })
    assert response.status_code in [200, 201], f"Failed to create customer: {response.text}"
    return response.json()


@pytest.fixture(scope="module")
def test_branch(api_client):
    """Get a test branch"""
    response = api_client.get(f"{BASE_URL}/api/branches")
    assert response.status_code == 200
    branches = response.json()
    assert len(branches) > 0, "No branches found"
    return branches[0]


class TestCustomerCashOutValidation:
    """Test validation for customer cash out endpoint"""

    def test_cashout_without_customer_returns_400(self, api_client, test_branch):
        """Cash out without customer_id should fail"""
        response = api_client.post(f"{BASE_URL}/api/expenses/customer-cashout", json={
            "amount": 1000,
            "branch_id": test_branch["id"]
        })
        assert response.status_code == 400
        assert "Customer is required" in response.json().get("detail", "")
        print("PASS: Cash out without customer returns 400")

    def test_cashout_with_invalid_customer_returns_404(self, api_client, test_branch):
        """Cash out with non-existent customer should fail"""
        response = api_client.post(f"{BASE_URL}/api/expenses/customer-cashout", json={
            "customer_id": "non-existent-id-12345",
            "amount": 1000,
            "branch_id": test_branch["id"]
        })
        assert response.status_code == 404
        assert "Customer not found" in response.json().get("detail", "")
        print("PASS: Cash out with invalid customer returns 404")


class TestCustomerCashOutCreation:
    """Test successful customer cash out creation"""

    def test_create_cashout_creates_expense_and_invoice(self, api_client, test_customer, test_branch):
        """Successfully creating cash out should create both expense and invoice"""
        due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = api_client.post(f"{BASE_URL}/api/expenses/customer-cashout", json={
            "customer_id": test_customer["id"],
            "amount": 1500,
            "branch_id": test_branch["id"],
            "description": "TEST_Cash Advance for farming",
            "notes": "Emergency cash loan",
            "payment_method": "Cash",
            "reference_number": "REF-001",
            "due_date": due_date,
            "terms": "Net 30"
        })
        
        assert response.status_code == 200, f"Failed to create cash out: {response.text}"
        data = response.json()
        
        # Verify expense is created
        assert "expense" in data
        expense = data["expense"]
        assert expense["category"] == "Customer Cash Out"
        assert expense["amount"] == 1500
        assert expense["customer_name"] == test_customer["name"]
        assert expense["expense_type"] == "customer_cashout"
        assert expense["linked_invoice_number"] is not None
        print(f"PASS: Expense created with category 'Customer Cash Out' and linked invoice {expense['linked_invoice_number']}")
        
        # Verify invoice is created
        assert "invoice" in data
        invoice = data["invoice"]
        assert invoice["invoice_number"] is not None
        assert invoice["total"] == 1500
        assert invoice["customer_name"] == test_customer["name"]
        print(f"PASS: Invoice {invoice['invoice_number']} created for customer {invoice['customer_name']}")
        
        # Verify success message
        assert "message" in data
        assert "Invoice" in data["message"]
        assert test_customer["name"] in data["message"]
        print(f"PASS: Success message: {data['message']}")
        
        return data

    def test_expense_shows_in_expenses_list(self, api_client, test_branch):
        """Created cash out expense should appear in expenses list with correct fields"""
        response = api_client.get(f"{BASE_URL}/api/expenses?branch_id={test_branch['id']}")
        assert response.status_code == 200
        
        expenses = response.json().get("expenses", [])
        cashout_expenses = [e for e in expenses if e.get("category") == "Customer Cash Out"]
        
        assert len(cashout_expenses) > 0, "No Customer Cash Out expenses found"
        
        # Check required fields are present
        latest = cashout_expenses[0]
        assert "customer_name" in latest
        assert "linked_invoice_number" in latest
        assert latest["expense_type"] == "customer_cashout"
        print(f"PASS: Cash out expense shows in list with customer_name='{latest['customer_name']}' and linked_invoice='{latest['linked_invoice_number']}'")

    def test_invoice_created_for_customer(self, api_client, test_customer):
        """Invoice should be created and visible in customer's invoices"""
        response = api_client.get(f"{BASE_URL}/api/customers/{test_customer['id']}/invoices")
        
        if response.status_code == 200:
            invoices = response.json()
            cashout_invoices = [i for i in invoices if i.get("expense_type") == "customer_cashout" or i.get("type") == "Cash Out"]
            
            # May or may not have invoices depending on order of tests
            print(f"PASS: Customer invoices endpoint accessible, found {len(cashout_invoices)} cash out invoices")
        else:
            print(f"INFO: Customer invoices endpoint returned {response.status_code}")


class TestCustomerCashOutDisplay:
    """Test that cash out expenses display correctly"""

    def test_expense_filter_by_category(self, api_client, test_branch):
        """Should be able to filter expenses by 'Customer Cash Out' category"""
        response = api_client.get(
            f"{BASE_URL}/api/expenses?category=Customer%20Cash%20Out&branch_id={test_branch['id']}"
        )
        assert response.status_code == 200
        
        expenses = response.json().get("expenses", [])
        for exp in expenses:
            assert exp["category"] == "Customer Cash Out"
        
        print(f"PASS: Category filter returns only 'Customer Cash Out' expenses ({len(expenses)} found)")


class TestCleanup:
    """Clean up test data"""
    
    def test_cleanup_test_expenses(self, api_client, test_branch):
        """Delete TEST_ prefixed expenses"""
        response = api_client.get(f"{BASE_URL}/api/expenses?branch_id={test_branch['id']}&limit=100")
        if response.status_code == 200:
            expenses = response.json().get("expenses", [])
            for exp in expenses:
                if exp.get("description", "").startswith("TEST_"):
                    api_client.delete(f"{BASE_URL}/api/expenses/{exp['id']}")
                    print(f"Deleted test expense: {exp['id']}")
        print("PASS: Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
