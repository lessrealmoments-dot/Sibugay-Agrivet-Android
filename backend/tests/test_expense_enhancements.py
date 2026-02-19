"""
Tests for Enhanced Expense Management Features
- Preset expense categories
- Payment method tracking
- Reference number tracking
- Notes field
- Edit expense capability  
- Filter by category, date range, search
- Farm Expense workflow that creates invoice
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExpenseEnhancements:
    """Test enhanced expense management features"""
    
    auth_token = None
    created_expense_id = None
    created_farm_expense_id = None
    test_customer_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        """Setup authentication before each test"""
        if not TestExpenseEnhancements.auth_token:
            response = api_client.post(f"{BASE_URL}/api/auth/login", json={
                "username": "admin",
                "password": "admin123"
            })
            assert response.status_code == 200, f"Login failed: {response.text}"
            TestExpenseEnhancements.auth_token = response.json()["token"]
        api_client.headers.update({"Authorization": f"Bearer {TestExpenseEnhancements.auth_token}"})
    
    # =====================
    # EXPENSE CATEGORIES
    # =====================
    
    def test_get_expense_categories(self, api_client):
        """Test GET /expenses/categories returns preset categories"""
        response = api_client.get(f"{BASE_URL}/api/expenses/categories")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        categories = response.json()
        assert isinstance(categories, list), "Categories should be a list"
        assert len(categories) > 0, "Should have preset categories"
        
        # Verify expected categories are present
        expected_categories = ["Utilities", "Rent", "Supplies", "Transportation", 
                              "Farm Expense", "Repairs & Maintenance", "Miscellaneous"]
        for cat in expected_categories:
            assert cat in categories, f"Expected category '{cat}' not found"
        
        print(f"✓ Found {len(categories)} preset categories")
    
    # =====================
    # CREATE EXPENSE
    # =====================
    
    def test_create_expense_with_all_fields(self, api_client):
        """Test POST /expenses with all enhanced fields"""
        expense_data = {
            "branch_id": "main",
            "category": "Utilities",
            "description": "TEST_Electric bill payment",
            "notes": "Monthly electricity for office",
            "amount": 1500.00,
            "payment_method": "Bank Transfer",
            "reference_number": "EL-2026-001",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses", json=expense_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        expense = response.json()
        TestExpenseEnhancements.created_expense_id = expense["id"]
        
        # Verify all fields are saved
        assert expense["category"] == "Utilities", "Category not saved"
        assert expense["description"] == "TEST_Electric bill payment", "Description not saved"
        assert expense["notes"] == "Monthly electricity for office", "Notes not saved"
        assert expense["amount"] == 1500.00, "Amount not correct"
        assert expense["payment_method"] == "Bank Transfer", "Payment method not saved"
        assert expense["reference_number"] == "EL-2026-001", "Reference number not saved"
        
        print(f"✓ Created expense with ID: {expense['id']}")
    
    def test_create_expense_with_gcash_payment(self, api_client):
        """Test creating expense with GCash payment method"""
        expense_data = {
            "branch_id": "main",
            "category": "Transportation",
            "description": "TEST_Delivery fee payment",
            "amount": 250.00,
            "payment_method": "GCash",
            "reference_number": "GCASH-12345",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses", json=expense_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        expense = response.json()
        assert expense["payment_method"] == "GCash", "GCash payment method not saved"
        print(f"✓ Created expense with GCash payment method")
    
    # =====================
    # EDIT EXPENSE
    # =====================
    
    def test_update_expense(self, api_client):
        """Test PUT /expenses/{id} to update expense"""
        if not TestExpenseEnhancements.created_expense_id:
            pytest.skip("No expense created to update")
        
        update_data = {
            "category": "Supplies",
            "description": "TEST_Updated electric bill",
            "notes": "Updated notes - corrected amount",
            "amount": 1600.00,
            "payment_method": "Cash",
            "reference_number": "EL-2026-001-REV"
        }
        
        expense_id = TestExpenseEnhancements.created_expense_id
        response = api_client.put(f"{BASE_URL}/api/expenses/{expense_id}", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        updated = response.json()
        assert updated["category"] == "Supplies", "Category not updated"
        assert updated["description"] == "TEST_Updated electric bill", "Description not updated"
        assert updated["notes"] == "Updated notes - corrected amount", "Notes not updated"
        assert updated["amount"] == 1600.00, "Amount not updated"
        assert updated["payment_method"] == "Cash", "Payment method not updated"
        assert updated["reference_number"] == "EL-2026-001-REV", "Reference number not updated"
        
        # Verify with GET
        get_response = api_client.get(f"{BASE_URL}/api/expenses", params={"search": "Updated electric bill"})
        assert get_response.status_code == 200
        expenses = get_response.json()["expenses"]
        found = [e for e in expenses if e["id"] == expense_id]
        assert len(found) == 1, "Updated expense not found"
        assert found[0]["amount"] == 1600.00, "Amount not persisted"
        
        print(f"✓ Successfully updated expense {expense_id}")
    
    # =====================
    # FILTERS
    # =====================
    
    def test_filter_by_category(self, api_client):
        """Test GET /expenses with category filter"""
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"category": "Supplies"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        expenses = data["expenses"]
        
        # All returned expenses should have the filtered category
        for expense in expenses:
            assert expense.get("category") == "Supplies", f"Got expense with wrong category: {expense.get('category')}"
        
        print(f"✓ Filter by category works - found {len(expenses)} Supplies expenses")
    
    def test_filter_by_payment_method(self, api_client):
        """Test GET /expenses with payment_method filter"""
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"payment_method": "Cash"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        expenses = data["expenses"]
        
        for expense in expenses:
            assert expense.get("payment_method") == "Cash", f"Got expense with wrong payment method: {expense.get('payment_method')}"
        
        print(f"✓ Filter by payment method works - found {len(expenses)} Cash expenses")
    
    def test_filter_by_date_range(self, api_client):
        """Test GET /expenses with date_from and date_to filters"""
        today = datetime.now()
        date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
        
        response = api_client.get(f"{BASE_URL}/api/expenses", params={
            "date_from": date_from,
            "date_to": date_to
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        expenses = data["expenses"]
        
        # All returned expenses should be within date range
        for expense in expenses:
            exp_date = expense.get("date", "")
            if exp_date:
                assert exp_date >= date_from, f"Expense date {exp_date} before date_from {date_from}"
                assert exp_date <= date_to, f"Expense date {exp_date} after date_to {date_to}"
        
        print(f"✓ Filter by date range works - found {len(expenses)} expenses in range")
    
    def test_search_by_description_or_reference(self, api_client):
        """Test GET /expenses with search filter"""
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"search": "TEST_"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        expenses = data["expenses"]
        
        # All returned expenses should match search
        for expense in expenses:
            desc = expense.get("description", "").lower()
            ref = expense.get("reference_number", "").lower()
            notes = expense.get("notes", "").lower()
            assert "test_" in desc or "test_" in ref or "test_" in notes, \
                f"Expense doesn't match search: {expense.get('description')}"
        
        print(f"✓ Search filter works - found {len(expenses)} matching expenses")
    
    # =====================
    # FARM EXPENSE WITH INVOICE
    # =====================
    
    def test_get_customers_for_farm_expense(self, api_client):
        """Verify customers endpoint works for farm expense dropdown"""
        response = api_client.get(f"{BASE_URL}/api/customers", params={"limit": 100})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        customers = data.get("customers", [])
        
        if len(customers) > 0:
            TestExpenseEnhancements.test_customer_id = customers[0]["id"]
            print(f"✓ Found {len(customers)} customers for farm expense dropdown")
        else:
            # Create a test customer
            customer_response = api_client.post(f"{BASE_URL}/api/customers", json={
                "name": "TEST_FarmExpenseCustomer",
                "phone": "09171234567",
                "email": "test@farm.com"
            })
            if customer_response.status_code == 200:
                TestExpenseEnhancements.test_customer_id = customer_response.json()["id"]
                print(f"✓ Created test customer for farm expense")
            else:
                pytest.skip("Could not get or create customer for farm expense test")
    
    def test_create_farm_expense_with_invoice(self, api_client):
        """Test POST /expenses/farm creates expense and auto-generates invoice"""
        if not TestExpenseEnhancements.test_customer_id:
            pytest.skip("No customer available for farm expense test")
        
        farm_expense_data = {
            "branch_id": "main",
            "description": "TEST_Tilling and plowing service",
            "notes": "3 hours tilling + 10L gas + 2 workers",
            "amount": 2500.00,
            "customer_id": TestExpenseEnhancements.test_customer_id,
            "payment_method": "Cash",
            "reference_number": "FARM-001",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "terms": "Net 30"
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses/farm", json=farm_expense_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        result = response.json()
        
        # Verify expense was created
        assert "expense" in result, "No expense in response"
        expense = result["expense"]
        TestExpenseEnhancements.created_farm_expense_id = expense["id"]
        
        assert expense["category"] == "Farm Expense", "Category should be Farm Expense"
        assert expense["description"] == "TEST_Tilling and plowing service", "Description mismatch"
        assert expense["customer_id"] == TestExpenseEnhancements.test_customer_id, "Customer ID mismatch"
        assert "linked_invoice_number" in expense, "Should have linked invoice number"
        
        # Verify invoice was created
        assert "invoice" in result, "No invoice in response"
        invoice = result["invoice"]
        assert invoice["invoice_number"], "Invoice number should be present"
        assert invoice["total"] == 2500.00, "Invoice total should match expense amount"
        
        assert "message" in result, "Should have success message"
        
        print(f"✓ Farm expense created with ID: {expense['id']}")
        print(f"✓ Auto-generated Invoice: {invoice['invoice_number']}")
    
    def test_farm_expense_requires_customer(self, api_client):
        """Test POST /expenses/farm fails without customer_id"""
        farm_expense_data = {
            "branch_id": "main",
            "description": "TEST_Service without customer",
            "amount": 1000.00,
            "payment_method": "Cash"
            # Missing customer_id
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses/farm", json=farm_expense_data)
        assert response.status_code == 400, f"Expected 400, got: {response.status_code}"
        
        error = response.json()
        assert "customer" in error.get("detail", "").lower(), "Error should mention customer"
        
        print(f"✓ Farm expense correctly requires customer")
    
    def test_farm_expense_shows_in_expense_list_with_invoice_link(self, api_client):
        """Verify farm expense shows linked invoice in expense list"""
        if not TestExpenseEnhancements.created_farm_expense_id:
            pytest.skip("No farm expense created to verify")
        
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"category": "Farm Expense"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        expenses = response.json()["expenses"]
        farm_expense = next((e for e in expenses if e["id"] == TestExpenseEnhancements.created_farm_expense_id), None)
        
        assert farm_expense is not None, "Farm expense not found in list"
        assert "linked_invoice_number" in farm_expense, "Should have linked invoice number"
        assert farm_expense["linked_invoice_number"], "Linked invoice number should not be empty"
        assert farm_expense.get("customer_name"), "Should have customer name"
        
        print(f"✓ Farm expense shows invoice link: {farm_expense['linked_invoice_number']}")
    
    # =====================
    # DELETE EXPENSE
    # =====================
    
    def test_delete_expense(self, api_client):
        """Test DELETE /expenses/{id} removes expense"""
        if not TestExpenseEnhancements.created_expense_id:
            pytest.skip("No expense to delete")
        
        expense_id = TestExpenseEnhancements.created_expense_id
        response = api_client.delete(f"{BASE_URL}/api/expenses/{expense_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify expense is deleted
        get_response = api_client.get(f"{BASE_URL}/api/expenses", params={"limit": 500})
        expenses = get_response.json()["expenses"]
        found = [e for e in expenses if e["id"] == expense_id]
        assert len(found) == 0, "Deleted expense should not be found"
        
        print(f"✓ Successfully deleted expense {expense_id}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
