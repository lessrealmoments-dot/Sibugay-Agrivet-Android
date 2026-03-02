"""
Test Employee Cash Advance Features - Iteration 86
Tests:
1. Employee Cash Advance quick action endpoint returns {expense, message}
2. Employee name shown in expense responses
3. Farm Expense with optional receipt upload
4. Backend endpoints return proper format
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmployeeAdvanceFeatures:
    """Test Employee Cash Advance and related features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token, branch_id, employee_id"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        if login_resp.status_code != 200:
            pytest.skip("Login failed")
        
        data = login_resp.json()
        self.token = data["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get first available branch
        branches_resp = self.session.get(f"{BASE_URL}/api/branches")
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches found")
        self.branch_id = branches[0]["id"]
        
        # Get first active employee
        employees_resp = self.session.get(f"{BASE_URL}/api/employees")
        employees = employees_resp.json()
        if not employees:
            pytest.skip("No employees found")
        # Find an active employee
        self.employee = next((e for e in employees if e.get("active", True)), employees[0])
        self.employee_id = self.employee["id"]
        
        # Get first customer for farm expense
        customers_resp = self.session.get(f"{BASE_URL}/api/customers?limit=1")
        customers_data = customers_resp.json()
        customers = customers_data.get("customers", [])
        if customers:
            self.customer_id = customers[0]["id"]
            self.customer_name = customers[0]["name"]
        else:
            self.customer_id = None
    
    def test_employee_advance_returns_expense_and_message(self):
        """Test POST /api/expenses/employee-advance returns {expense, message}"""
        payload = {
            "employee_id": self.employee_id,
            "amount": 50,
            "description": "TEST_86 advance",
            "notes": "Testing API response format",
            "branch_id": self.branch_id,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/employee-advance", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response has both expense and message
        assert "expense" in data, "Response should contain 'expense' key"
        assert "message" in data, "Response should contain 'message' key"
        
        # Verify expense structure
        expense = data["expense"]
        assert expense.get("category") == "Employee Advance"
        assert expense.get("employee_id") == self.employee_id
        assert expense.get("employee_name") is not None, "employee_name should be present"
        assert expense.get("amount") == 50.0
        
        # Verify message contains employee name
        message = data["message"]
        assert self.employee["name"] in message, f"Message should contain employee name: {message}"
        print(f"PASS: Employee advance response: {message}")
    
    def test_expense_list_includes_employee_name(self):
        """Test GET /api/expenses returns employee_name for Employee Advance category"""
        response = self.session.get(f"{BASE_URL}/api/expenses?category=Employee%20Advance&limit=10")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        expenses = data.get("expenses", [])
        
        # Find at least one Employee Advance expense
        employee_advances = [e for e in expenses if e.get("category") == "Employee Advance"]
        
        if not employee_advances:
            pytest.skip("No Employee Advance expenses found to verify")
        
        # Check that employee_name is present
        for expense in employee_advances:
            if expense.get("employee_id"):
                assert "employee_name" in expense, f"Expense {expense['id']} should have employee_name"
                assert expense["employee_name"] is not None, f"employee_name should not be None"
                print(f"PASS: Expense {expense['id']} has employee_name: {expense['employee_name']}")
    
    def test_farm_expense_without_receipt(self):
        """Test POST /api/expenses/farm works without upload_session_ids (skip receipt)"""
        if not self.customer_id:
            pytest.skip("No customer found for farm expense test")
        
        payload = {
            "customer_id": self.customer_id,
            "amount": 75,
            "description": "TEST_86 farm service",
            "notes": "Testing farm expense without receipt",
            "branch_id": self.branch_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_method": "Cash"
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/farm", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "expense" in data, "Response should contain 'expense' key"
        assert "invoice" in data, "Response should contain 'invoice' key"
        assert "message" in data, "Response should contain 'message' key"
        
        expense = data["expense"]
        assert expense.get("category") == "Farm Expense"
        assert expense.get("customer_name") == self.customer_name
        
        message = data["message"]
        assert self.customer_name in message, f"Message should contain customer name: {message}"
        print(f"PASS: Farm expense created: {message}")
    
    def test_farm_expense_with_upload_session(self):
        """Test POST /api/expenses/farm accepts upload_session_ids"""
        if not self.customer_id:
            pytest.skip("No customer found for farm expense test")
        
        # Create with empty upload_session_ids (simulating skip)
        payload = {
            "customer_id": self.customer_id,
            "amount": 100,
            "description": "TEST_86 farm with receipt option",
            "notes": "Testing with upload_session_ids field",
            "branch_id": self.branch_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_method": "Cash",
            "upload_session_ids": []  # Empty - skip receipt
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/farm", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "expense" in data
        print(f"PASS: Farm expense with upload_session_ids created successfully")
    
    def test_employee_advance_validation_no_employee(self):
        """Test POST /api/expenses/employee-advance requires employee_id"""
        payload = {
            "amount": 50,
            "description": "TEST_86 no employee",
            "branch_id": self.branch_id,
            "date": datetime.now().strftime("%Y-%m-%d")
            # Missing employee_id
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/employee-advance", json=payload)
        
        # Should fail with 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Employee advance validation works - requires employee_id")


class TestExpenseListEmployeeName:
    """Test expense listing shows employee names properly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        if login_resp.status_code != 200:
            pytest.skip("Login failed")
        
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_all_expenses_have_proper_employee_data(self):
        """Test all Employee Advance expenses have employee_name"""
        response = self.session.get(f"{BASE_URL}/api/expenses?limit=50")
        
        assert response.status_code == 200
        
        data = response.json()
        expenses = data.get("expenses", [])
        
        employee_advances = [e for e in expenses if e.get("category") == "Employee Advance"]
        
        for expense in employee_advances:
            if expense.get("employee_id"):
                assert "employee_name" in expense, f"Missing employee_name in expense {expense['id']}"
                print(f"Expense {expense['id']}: employee_name = {expense.get('employee_name')}")
        
        print(f"PASS: Checked {len(employee_advances)} Employee Advance expenses")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
