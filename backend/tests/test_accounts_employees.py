"""
Test suite for Accounts (User Management) and Employees features.
Tests: user CRUD, PIN management, employee CRUD, CA summary endpoint.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def login(username, password):
    """Helper to login and return session with auth token."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    res = session.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    token = res.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, res.json().get("user")


@pytest.fixture(scope="module")
def admin_session():
    session, user = login("owner", "secure123")
    return session, user


# ======================= ACCOUNTS / USER MANAGEMENT =======================

class TestAccountsUserManagement:
    """User management endpoint tests (AccountsPage backend)"""

    created_user_id = None

    def test_list_users(self, admin_session):
        """GET /users returns user list"""
        session, _ = admin_session
        res = session.get(f"{BASE_URL}/api/users")
        assert res.status_code == 200, f"List users failed: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Expected list of users"
        assert len(data) > 0, "Expected at least one user"
        # Verify user has expected fields
        first_user = data[0]
        assert "id" in first_user
        assert "username" in first_user
        assert "role" in first_user
        # Ensure password_hash is not exposed
        assert "password_hash" not in first_user
        print(f"PASS: GET /users returned {len(data)} users")

    def test_create_user_cashier(self, admin_session):
        """POST /users creates a cashier user"""
        session, _ = admin_session
        payload = {
            "username": "TEST_cashier_auto2026",
            "full_name": "Test Cashier AutoTest",
            "email": "testcashier@test.com",
            "role": "cashier",
            "branch_id": None,
            "password": "testpass123"
        }
        res = session.post(f"{BASE_URL}/api/users", json=payload)
        assert res.status_code == 200, f"Create user failed: {res.text}"
        data = res.json()
        assert data["username"] == "TEST_cashier_auto2026"
        assert data["role"] == "cashier"
        assert "id" in data
        assert "password_hash" not in data
        TestAccountsUserManagement.created_user_id = data["id"]
        print(f"PASS: Created user ID={data['id']}, role={data['role']}")

    def test_create_user_duplicate_fails(self, admin_session):
        """POST /users with existing username returns 400"""
        session, _ = admin_session
        payload = {
            "username": "TEST_cashier_auto2026",
            "full_name": "Dup User",
            "role": "cashier",
            "password": "testpass123"
        }
        res = session.post(f"{BASE_URL}/api/users", json=payload)
        assert res.status_code == 400, f"Expected 400 for duplicate, got {res.status_code}"
        print("PASS: Duplicate username returns 400")

    def test_get_user_by_id(self, admin_session):
        """GET /users/{id} returns created user"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid, "No user ID from previous test"
        res = session.get(f"{BASE_URL}/api/users/{uid}")
        assert res.status_code == 200, f"Get user failed: {res.text}"
        data = res.json()
        assert data["id"] == uid
        assert data["username"] == "TEST_cashier_auto2026"
        print(f"PASS: GET /users/{uid} returned correct user")

    def test_update_user(self, admin_session):
        """PUT /users/{id} updates user details"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.put(f"{BASE_URL}/api/users/{uid}", json={"full_name": "Updated Cashier Name", "role": "cashier"})
        assert res.status_code == 200, f"Update user failed: {res.text}"
        data = res.json()
        assert data["full_name"] == "Updated Cashier Name"
        print(f"PASS: Updated user full_name")

    def test_set_manager_pin(self, admin_session):
        """PUT /users/{id}/pin sets manager PIN"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.put(f"{BASE_URL}/api/users/{uid}/pin", json={"pin": "1234"})
        assert res.status_code == 200, f"Set PIN failed: {res.text}"
        data = res.json()
        assert "set" in data.get("message", "").lower()
        print(f"PASS: PIN set for user - message: {data['message']}")

    def test_pin_reflected_in_user_details(self, admin_session):
        """After setting PIN, user record shows manager_pin is set"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.get(f"{BASE_URL}/api/users/{uid}")
        assert res.status_code == 200
        data = res.json()
        assert data.get("manager_pin") is not None, "manager_pin should be set after PUT /pin"
        print(f"PASS: manager_pin present in user record after set")

    def test_clear_manager_pin(self, admin_session):
        """PUT /users/{id}/pin with empty pin clears it"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.put(f"{BASE_URL}/api/users/{uid}/pin", json={"pin": ""})
        assert res.status_code == 200
        data = res.json()
        assert "clear" in data.get("message", "").lower()
        print(f"PASS: PIN cleared - message: {data['message']}")

    def test_pin_short_fails(self, admin_session):
        """PUT /users/{id}/pin with < 4 digits returns 400"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.put(f"{BASE_URL}/api/users/{uid}/pin", json={"pin": "12"})
        assert res.status_code == 400, f"Expected 400 for short PIN, got {res.status_code}"
        print("PASS: Short PIN returns 400")

    def test_toggle_user_inactive(self, admin_session):
        """PUT /users/{id} with active=False deactivates user"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        assert uid
        res = session.put(f"{BASE_URL}/api/users/{uid}", json={"active": False})
        assert res.status_code == 200
        data = res.json()
        assert data.get("active") is False
        print("PASS: User deactivated successfully")

    def test_cleanup_test_user(self, admin_session):
        """Cleanup: delete test user"""
        session, _ = admin_session
        uid = TestAccountsUserManagement.created_user_id
        if uid:
            res = session.delete(f"{BASE_URL}/api/users/{uid}")
            assert res.status_code == 200
            print(f"PASS: Deleted test user {uid}")


# ======================= EMPLOYEES =======================

class TestEmployees:
    """Employee management and CA summary tests (EmployeesPage backend)"""

    created_emp_id = None

    def test_list_employees(self, admin_session):
        """GET /employees returns employee list"""
        session, _ = admin_session
        res = session.get(f"{BASE_URL}/api/employees")
        assert res.status_code == 200, f"List employees failed: {res.text}"
        data = res.json()
        assert isinstance(data, list)
        print(f"PASS: GET /employees returned {len(data)} employees")

    def test_create_employee_with_ca_limit(self, admin_session):
        """POST /employees creates employee with monthly_ca_limit=5000"""
        session, _ = admin_session
        payload = {
            "name": "TEST_Employee AutoTest2026",
            "position": "Test Driver",
            "employment_type": "regular",
            "phone": "09171234567",
            "hire_date": "2025-01-15",
            "salary": 15000,
            "daily_rate": 600,
            "monthly_ca_limit": 5000,
            "sss_number": "12-3456789-0",
            "philhealth_number": "0000-1111-2222",
            "pagibig_number": "0000-1111-2222-3333",
            "tin_number": "000-111-222-000",
            "branch_id": ""
        }
        res = session.post(f"{BASE_URL}/api/employees", json=payload)
        assert res.status_code == 200, f"Create employee failed: {res.text}"
        data = res.json()
        assert data["name"] == "TEST_Employee AutoTest2026"
        assert data["monthly_ca_limit"] == 5000.0
        assert data["employment_type"] == "regular"
        assert data["sss_number"] == "12-3456789-0"
        assert "id" in data
        TestEmployees.created_emp_id = data["id"]
        print(f"PASS: Created employee ID={data['id']}, CA limit={data['monthly_ca_limit']}")

    def test_get_employee(self, admin_session):
        """GET /employees/{id} returns created employee"""
        session, _ = admin_session
        eid = TestEmployees.created_emp_id
        assert eid
        res = session.get(f"{BASE_URL}/api/employees/{eid}")
        assert res.status_code == 200, f"Get employee failed: {res.text}"
        data = res.json()
        assert data["id"] == eid
        assert data["monthly_ca_limit"] == 5000.0
        print(f"PASS: GET /employees/{eid} correct")

    def test_update_employee_ca_limit(self, admin_session):
        """PUT /employees/{id} updates monthly_ca_limit"""
        session, _ = admin_session
        eid = TestEmployees.created_emp_id
        assert eid
        res = session.put(f"{BASE_URL}/api/employees/{eid}", json={"monthly_ca_limit": 7500, "name": "TEST_Employee AutoTest2026"})
        assert res.status_code == 200
        data = res.json()
        assert data["monthly_ca_limit"] == 7500.0
        print("PASS: Updated CA limit to 7500")

    def test_ca_summary_endpoint(self, admin_session):
        """GET /employees/{id}/ca-summary returns proper CA data structure"""
        session, _ = admin_session
        eid = TestEmployees.created_emp_id
        assert eid
        res = session.get(f"{BASE_URL}/api/employees/{eid}/ca-summary")
        assert res.status_code == 200, f"CA summary failed: {res.text}"
        data = res.json()
        # Validate required fields
        assert "employee_id" in data
        assert "monthly_ca_limit" in data
        assert "this_month_total" in data
        assert "prev_month_total" in data
        assert "prev_month_overage" in data
        assert "remaining_this_month" in data
        assert "total_advance_balance" in data
        assert "is_over_limit" in data
        assert "recent_advances" in data
        assert data["employee_id"] == eid
        assert data["monthly_ca_limit"] == 7500.0
        print(f"PASS: CA summary: this_month={data['this_month_total']}, limit={data['monthly_ca_limit']}, remaining={data['remaining_this_month']}")

    def test_ca_advances_endpoint(self, admin_session):
        """GET /employees/{id}/advances returns list"""
        session, _ = admin_session
        eid = TestEmployees.created_emp_id
        assert eid
        res = session.get(f"{BASE_URL}/api/employees/{eid}/advances")
        assert res.status_code == 200, f"Advances list failed: {res.text}"
        data = res.json()
        assert isinstance(data, list)
        print(f"PASS: GET /employees/{eid}/advances returned {len(data)} records")

    def test_delete_employee(self, admin_session):
        """Cleanup: soft-delete test employee"""
        session, _ = admin_session
        eid = TestEmployees.created_emp_id
        if eid:
            res = session.delete(f"{BASE_URL}/api/employees/{eid}")
            assert res.status_code == 200
            print(f"PASS: Deleted employee {eid}")


# ======================= AUTH / MANAGER PIN VERIFY =======================

class TestManagerPinVerify:
    """Test manager PIN verification endpoint used in CA over-limit approval"""

    def test_verify_pin_endpoint_exists(self, admin_session):
        """POST /auth/verify-manager-pin exists and handles missing PIN"""
        session, _ = admin_session
        res = session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={"pin": ""})
        # Should not be 404 - endpoint should exist
        assert res.status_code != 404, "Manager PIN verify endpoint does not exist!"
        print(f"PASS: /auth/verify-manager-pin endpoint exists, returned {res.status_code}")

    def test_verify_wrong_pin(self, admin_session):
        """POST /auth/verify-manager-pin with wrong PIN returns invalid"""
        session, _ = admin_session
        res = session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={"pin": "9999"})
        # Could return 200 with valid=false, or 400
        if res.status_code == 200:
            assert res.json().get("valid") is False
            print("PASS: Wrong PIN returns valid=false")
        else:
            print(f"PASS: Wrong PIN returns {res.status_code}")
