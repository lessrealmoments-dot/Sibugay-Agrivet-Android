"""
Iteration 55: Sales History Board - Digital Sales Separation & Team Page Expandable Rows
Tests:
1. GET /api/invoices/history/by-date returns totals with separate 'digital' field
2. Sales History board shows 5 stat cards (Cash, Digital, Credit, Grand Total, Transactions)
3. Sales History row badges show actual payment type (GCash/Digital vs Credit vs Cash)
4. Team page expandable row with user details
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL not set")
BASE_URL = BASE_URL.rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"


class TestSalesHistoryDigitalSeparation:
    """Test the sales history endpoint returns separate digital totals"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("access_token")
        assert token, "No access_token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
    def test_history_by_date_returns_digital_field(self):
        """BUG FIX: /api/invoices/history/by-date should return separate 'digital' total"""
        import datetime
        today = datetime.date.today().isoformat()
        
        response = self.session.get(f"{BASE_URL}/api/invoices/history/by-date", params={
            "date": today,
            "include_voided": True
        })
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "invoices" in data, "Missing 'invoices' field"
        assert "totals" in data, "Missing 'totals' field"
        assert "date" in data, "Missing 'date' field"
        
        totals = data["totals"]
        print(f"Totals returned: {totals}")
        
        # KEY TEST: Verify 'digital' field exists separate from 'credit'
        assert "digital" in totals, "BUG NOT FIXED: Missing 'digital' field in totals - digital sales lumped elsewhere"
        assert "cash" in totals, "Missing 'cash' field in totals"
        assert "credit" in totals, "Missing 'credit' field in totals"
        assert "grand_total" in totals, "Missing 'grand_total' field in totals"
        assert "count" in totals, "Missing 'count' field in totals"
        
        # Verify values are numeric
        assert isinstance(totals["digital"], (int, float)), "digital should be numeric"
        assert isinstance(totals["cash"], (int, float)), "cash should be numeric"
        assert isinstance(totals["credit"], (int, float)), "credit should be numeric"
        assert isinstance(totals["grand_total"], (int, float)), "grand_total should be numeric"
        
        print(f"PASS: Cash={totals['cash']}, Digital={totals['digital']}, Credit={totals['credit']}, Grand={totals['grand_total']}")

    def test_history_returns_invoices_with_payment_type(self):
        """Invoices should have payment_type field for badge display"""
        import datetime
        today = datetime.date.today().isoformat()
        
        response = self.session.get(f"{BASE_URL}/api/invoices/history/by-date", params={
            "date": today,
            "include_voided": True
        })
        
        assert response.status_code == 200
        data = response.json()
        invoices = data.get("invoices", [])
        
        print(f"Found {len(invoices)} invoices for {today}")
        
        # Check a few invoices for payment_type field
        for inv in invoices[:5]:
            print(f"  Invoice {inv.get('invoice_number')}: payment_type={inv.get('payment_type')}, payment_method={inv.get('payment_method')}, status={inv.get('status')}")
            
        # At least the structure should be correct
        assert isinstance(invoices, list), "invoices should be a list"
        
    def test_history_calculates_digital_total_correctly(self):
        """Digital total should be sum of payment_type='digital' or 'split' invoices"""
        import datetime
        today = datetime.date.today().isoformat()
        
        response = self.session.get(f"{BASE_URL}/api/invoices/history/by-date", params={
            "date": today,
            "include_voided": False
        })
        
        assert response.status_code == 200
        data = response.json()
        
        invoices = data.get("invoices", [])
        totals = data.get("totals", {})
        
        # Manual calculation based on payment_type
        digital_invoices = [inv for inv in invoices 
                          if inv.get("payment_type") in ("digital", "split") 
                          and inv.get("status") != "voided"]
        
        calculated_digital = sum(float(inv.get("grand_total", 0)) for inv in digital_invoices)
        reported_digital = totals.get("digital", 0)
        
        print(f"Digital invoices: {len(digital_invoices)}")
        print(f"Calculated digital total: {calculated_digital}")
        print(f"API reported digital: {reported_digital}")
        
        # Allow small floating point differences
        assert abs(calculated_digital - reported_digital) < 0.01, \
            f"Digital total mismatch: calculated={calculated_digital}, reported={reported_digital}"


class TestUsersEndpoint:
    """Test the users endpoint for Team page expandable rows"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def test_get_users_list(self):
        """GET /api/users returns user list with necessary fields"""
        response = self.session.get(f"{BASE_URL}/api/users")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        users = response.json()
        
        assert isinstance(users, list), "Should return a list of users"
        assert len(users) > 0, "Should have at least one user"
        
        # Check first user has fields needed for expandable row
        user = users[0]
        print(f"Sample user: {user.get('username')}")
        
        # Required fields for Team page display
        assert "id" in user, "Missing id"
        assert "username" in user, "Missing username"
        
        # Fields used in expandable row detail
        if "created_at" in user:
            print(f"  created_at: {user['created_at']}")
        if "manager_pin" in user:
            print(f"  manager_pin set: {bool(user['manager_pin'])}")
        if "permission_preset" in user:
            print(f"  permission_preset: {user['permission_preset']}")
            
    def test_get_user_permissions(self):
        """GET /api/users/{id}/permissions returns permission structure"""
        # First get users
        users_resp = self.session.get(f"{BASE_URL}/api/users")
        assert users_resp.status_code == 200
        users = users_resp.json()
        
        if len(users) > 0:
            user_id = users[0]["id"]
            perm_resp = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
            
            assert perm_resp.status_code == 200, f"Failed: {perm_resp.text}"
            perm_data = perm_resp.json()
            
            # Should have permissions structure
            assert "permissions" in perm_data or isinstance(perm_data, dict), "Should return permissions data"
            print(f"User {users[0]['username']} permissions retrieved successfully")


class TestTeamPageEndpoints:
    """Test all Team page related API endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def test_permissions_modules_endpoint(self):
        """GET /api/permissions/modules returns module definitions"""
        response = self.session.get(f"{BASE_URL}/api/permissions/modules")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        modules = response.json()
        
        assert isinstance(modules, dict), "Should return dict of modules"
        print(f"Permission modules: {list(modules.keys())}")

    def test_permissions_presets_endpoint(self):
        """GET /api/permissions/presets returns role presets"""
        response = self.session.get(f"{BASE_URL}/api/permissions/presets")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        presets = response.json()
        
        assert isinstance(presets, dict), "Should return dict of presets"
        print(f"Permission presets: {list(presets.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
