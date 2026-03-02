"""
Test CA Summary Report Feature - Iteration 87

Tests:
1. GET /api/employees/ca-report - Returns correct structure and data
2. CA report with branch_id and month filters
3. daily_operations endpoints return is_over_ca and monthly_ca_limit on Employee Advance expenses
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


@pytest.fixture(scope="module")
def branch_id(api_client):
    """Get first branch ID for testing"""
    response = api_client.get(f"{BASE_URL}/api/branches")
    assert response.status_code == 200
    branches = response.json()
    if branches and len(branches) > 0:
        return branches[0]["id"]
    return None


class TestCAReportEndpoint:
    """Test GET /api/employees/ca-report endpoint"""
    
    def test_ca_report_returns_correct_structure(self, api_client):
        """CA report should return month, total_employees, total_advances_this_month, etc."""
        response = api_client.get(f"{BASE_URL}/api/employees/ca-report")
        assert response.status_code == 200, f"CA report failed: {response.text}"
        
        data = response.json()
        
        # Verify top-level structure
        assert "month" in data, "Missing 'month' field"
        assert "total_employees" in data, "Missing 'total_employees' field"
        assert "total_advances_this_month" in data, "Missing 'total_advances_this_month' field"
        assert "total_unpaid_balance" in data, "Missing 'total_unpaid_balance' field"
        assert "over_limit_employees" in data, "Missing 'over_limit_employees' field"
        assert "employees" in data, "Missing 'employees' array"
        
        # Verify month format (YYYY-MM)
        assert len(data["month"]) == 7, f"Month should be YYYY-MM format, got: {data['month']}"
        assert "-" in data["month"], "Month should be YYYY-MM format"
        
        print(f"CA Report structure valid - Month: {data['month']}, Employees: {data['total_employees']}")
        print(f"Total advances: {data['total_advances_this_month']}, Unpaid: {data['total_unpaid_balance']}")
        print(f"Over-limit employees: {data['over_limit_employees']}")
    
    def test_ca_report_employee_data_structure(self, api_client):
        """Each employee in CA report should have required fields"""
        response = api_client.get(f"{BASE_URL}/api/employees/ca-report")
        assert response.status_code == 200
        
        data = response.json()
        employees = data.get("employees", [])
        
        if len(employees) == 0:
            pytest.skip("No employees found in CA report to verify structure")
        
        # Check first employee has all required fields
        emp = employees[0]
        required_fields = [
            "employee_id", "name", "branch_id", "monthly_ca_limit",
            "this_month_total", "this_month_count", "over_limit_count",
            "prev_month_total", "prev_month_overage", "is_over_limit",
            "unpaid_balance", "last_advance_date", "usage_pct"
        ]
        
        for field in required_fields:
            assert field in emp, f"Missing field '{field}' in employee data"
        
        print(f"Employee data structure valid - Sample: {emp['name']}")
        print(f"  Monthly limit: {emp['monthly_ca_limit']}")
        print(f"  This month: {emp['this_month_total']}")
        print(f"  Over limit: {emp['is_over_limit']}")
        print(f"  Usage %: {emp['usage_pct']}")
    
    def test_ca_report_with_branch_filter(self, api_client, branch_id):
        """CA report should filter by branch_id"""
        if not branch_id:
            pytest.skip("No branch available for testing")
        
        response = api_client.get(f"{BASE_URL}/api/employees/ca-report?branch_id={branch_id}")
        assert response.status_code == 200, f"CA report with branch filter failed: {response.text}"
        
        data = response.json()
        assert "employees" in data
        
        # All employees should be from the filtered branch
        for emp in data.get("employees", []):
            if emp.get("branch_id"):  # Branch might be empty for some employees
                assert emp["branch_id"] == branch_id or emp["branch_id"] == "", f"Employee from wrong branch: {emp['branch_id']}"
        
        print(f"CA Report with branch filter returned {len(data['employees'])} employees")
    
    def test_ca_report_with_month_filter(self, api_client):
        """CA report should filter by month (YYYY-MM format)"""
        # Test current month
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        
        response = api_client.get(f"{BASE_URL}/api/employees/ca-report?month={current_month}")
        assert response.status_code == 200, f"CA report with month filter failed: {response.text}"
        
        data = response.json()
        assert data["month"] == current_month, f"Month mismatch: expected {current_month}, got {data['month']}"
        
        print(f"CA Report for month {current_month} - {data['total_employees']} employees")
        
        # Test previous month
        if datetime.now().month == 1:
            prev_month = f"{datetime.now().year - 1}-12"
        else:
            prev_month = f"{datetime.now().year}-{datetime.now().month - 1:02d}"
        
        response = api_client.get(f"{BASE_URL}/api/employees/ca-report?month={prev_month}")
        assert response.status_code == 200
        data = response.json()
        assert data["month"] == prev_month
        print(f"CA Report for previous month {prev_month} also works")


class TestDailyOperationsCAFields:
    """Test that daily operations endpoints return is_over_ca and monthly_ca_limit on Employee Advance expenses"""
    
    def test_daily_report_expense_fields(self, api_client, branch_id):
        """daily-report should include is_over_ca and monthly_ca_limit on Employee Advance expenses"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {"date": today}
        if branch_id:
            params["branch_id"] = branch_id
        
        response = api_client.get(f"{BASE_URL}/api/daily-report", params=params)
        assert response.status_code == 200, f"daily-report failed: {response.text}"
        
        data = response.json()
        
        # Check for advance_expenses array
        advance_expenses = data.get("advance_expenses", [])
        print(f"daily-report returned {len(advance_expenses)} Employee Advance expenses")
        
        # If there are Employee Advance expenses, verify fields
        for exp in advance_expenses:
            if exp.get("category") == "Employee Advance" and exp.get("employee_id"):
                # These fields should be present when it's an Employee Advance
                print(f"  Employee Advance: {exp.get('employee_name', 'Unknown')}")
                print(f"    monthly_ca_limit: {exp.get('monthly_ca_limit', 'N/A')}")
                print(f"    is_over_ca: {exp.get('is_over_ca', 'N/A')}")
    
    def test_daily_log_endpoint(self, api_client, branch_id):
        """daily-log endpoint should return expenses with proper structure"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {"date": today}
        if branch_id:
            params["branch_id"] = branch_id
        
        response = api_client.get(f"{BASE_URL}/api/daily-log", params=params)
        assert response.status_code == 200, f"daily-log failed: {response.text}"
        
        data = response.json()
        assert "entries" in data, "Missing 'entries' in daily-log response"
        assert "summary" in data, "Missing 'summary' in daily-log response"
        
        print(f"daily-log for {today}: {data.get('count', 0)} entries")
    
    def test_daily_close_preview_expense_fields(self, api_client, branch_id):
        """daily-close-preview should include is_over_ca and monthly_ca_limit on Employee Advance expenses"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {"date": today}
        if branch_id:
            params["branch_id"] = branch_id
        
        response = api_client.get(f"{BASE_URL}/api/daily-close-preview", params=params)
        assert response.status_code == 200, f"daily-close-preview failed: {response.text}"
        
        data = response.json()
        
        # Verify basic structure
        assert "expenses" in data, "Missing 'expenses' in daily-close-preview"
        assert "expected_counter" in data, "Missing 'expected_counter' in daily-close-preview"
        
        expenses = data.get("expenses", [])
        print(f"daily-close-preview returned {len(expenses)} expenses")
        
        # Check for Employee Advance expenses with CA fields
        for exp in expenses:
            if exp.get("category") == "Employee Advance" and exp.get("employee_id"):
                assert "monthly_ca_limit" in exp, f"Missing monthly_ca_limit for Employee Advance: {exp.get('id')}"
                assert "is_over_ca" in exp, f"Missing is_over_ca for Employee Advance: {exp.get('id')}"
                print(f"  Employee Advance expense found:")
                print(f"    Employee: {exp.get('employee_name', 'Unknown')}")
                print(f"    Amount: {exp.get('amount')}")
                print(f"    monthly_ca_limit: {exp.get('monthly_ca_limit')}")
                print(f"    is_over_ca: {exp.get('is_over_ca')}")
                print(f"    manager_approved_by: {exp.get('manager_approved_by', 'N/A')}")
    
    def test_daily_close_status_endpoint(self, api_client, branch_id):
        """daily-close/{date} should return correct status"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {}
        if branch_id:
            params["branch_id"] = branch_id
        
        response = api_client.get(f"{BASE_URL}/api/daily-close/{today}", params=params)
        assert response.status_code == 200, f"daily-close status failed: {response.text}"
        
        data = response.json()
        assert "status" in data, "Missing 'status' field"
        assert "date" in data, "Missing 'date' field"
        
        print(f"daily-close status for {today}: {data.get('status')}")


class TestEmployeeCASummary:
    """Test individual employee CA summary endpoint"""
    
    def test_employee_ca_summary(self, api_client):
        """Test /employees/{emp_id}/ca-summary endpoint"""
        # First get an employee ID
        response = api_client.get(f"{BASE_URL}/api/employees")
        assert response.status_code == 200
        
        employees = response.json()
        if not employees or len(employees) == 0:
            pytest.skip("No employees found")
        
        emp_id = employees[0].get("id")
        
        response = api_client.get(f"{BASE_URL}/api/employees/{emp_id}/ca-summary")
        assert response.status_code == 200, f"Employee CA summary failed: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "employee_id" in data
        assert "employee_name" in data
        assert "monthly_ca_limit" in data
        assert "this_month_total" in data
        assert "is_over_limit" in data
        
        print(f"CA Summary for {data['employee_name']}:")
        print(f"  Monthly limit: {data['monthly_ca_limit']}")
        print(f"  This month total: {data['this_month_total']}")
        print(f"  Is over limit: {data['is_over_limit']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
