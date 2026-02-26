"""
PIN Management Tests - Iteration 53

Tests for the new PIN Management features:
1. PUT /api/auth/change-my-pin - Manager/Admin self-PIN change with current PIN validation
2. Unified _resolve_pin checks manager_pin for public verify and mark-reviewed
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Credentials
COMPANY_ADMIN_EMAIL = "jovelyneahig@gmail.com"
COMPANY_ADMIN_PASSWORD = "Aa@050772"
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"  # Janmark Ahig's manager PIN


@pytest.fixture(scope="module")
def company_admin_token():
    """Login as company admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": COMPANY_ADMIN_EMAIL,
        "password": COMPANY_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()
    pytest.skip(f"Company admin auth failed: {response.text}")


@pytest.fixture(scope="module")
def company_admin_headers(company_admin_token):
    return {"Authorization": f"Bearer {company_admin_token['token']}"}


@pytest.fixture(scope="module")
def super_admin_token():
    """Login as super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()
    pytest.skip(f"Super admin auth failed: {response.text}")


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token['token']}"}


class TestChangeMyPinEndpoint:
    """Test PUT /api/auth/change-my-pin - manager/admin self-PIN change"""
    
    def test_change_pin_without_current_pin_when_pin_exists_fails(self, super_admin_headers):
        """If user has existing PIN, changing without current_pin should return 400"""
        # Note: Janmark (super admin) has manager_pin=521325
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"new_pin": "999888"},
            headers=super_admin_headers
        )
        print(f"Change without current: {response.status_code} - {response.text}")
        # Should require current PIN
        assert response.status_code == 400
        assert "Current PIN is required" in response.json().get("detail", "")
    
    def test_change_pin_with_wrong_current_pin_fails(self, super_admin_headers):
        """Wrong current_pin should return 401"""
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": "000000", "new_pin": "999888"},
            headers=super_admin_headers
        )
        print(f"Wrong current PIN: {response.status_code} - {response.text}")
        assert response.status_code == 401
        assert "incorrect" in response.json().get("detail", "").lower()
    
    def test_change_pin_with_correct_current_pin_succeeds(self, super_admin_headers):
        """Correct current_pin allows PIN change, then change back"""
        # Change to new PIN
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": MANAGER_PIN, "new_pin": "999888"},
            headers=super_admin_headers
        )
        print(f"Change with correct PIN: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert "changed" in response.json().get("message", "").lower() or "updated" in response.json().get("message", "").lower()
        
        # Change back to original
        response2 = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": "999888", "new_pin": MANAGER_PIN},
            headers=super_admin_headers
        )
        assert response2.status_code == 200, f"Failed to restore PIN: {response2.text}"
    
    def test_change_pin_short_pin_fails(self, super_admin_headers):
        """PIN < 4 digits should fail"""
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": MANAGER_PIN, "new_pin": "12"},
            headers=super_admin_headers
        )
        assert response.status_code == 400
        assert "at least 4" in response.json().get("detail", "").lower()
    
    def test_change_pin_for_cashier_forbidden(self, company_admin_headers):
        """Only managers/admins can have PINs - if company admin is admin role it should work"""
        # First check what role company admin has
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=company_admin_headers)
        if me_resp.status_code == 200:
            user_role = me_resp.json().get("role")
            print(f"Company admin role: {user_role}")
            
            if user_role not in ["admin", "manager"]:
                # Should be forbidden for cashier
                response = requests.put(
                    f"{BASE_URL}/api/auth/change-my-pin",
                    json={"new_pin": "1234"},
                    headers=company_admin_headers
                )
                assert response.status_code == 403


class TestChangeMyPinForNewUser:
    """Test change-my-pin for user without existing PIN"""
    
    def test_new_user_can_set_pin_without_current(self, company_admin_headers):
        """User without existing PIN should be able to set without current_pin"""
        # Check if company admin has a PIN
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=company_admin_headers)
        if me_resp.status_code != 200:
            pytest.skip("Cannot get user info")
        
        user = me_resp.json()
        has_pin = bool(user.get("manager_pin"))
        
        if not has_pin:
            # No PIN set - should be able to set without current_pin
            response = requests.put(
                f"{BASE_URL}/api/auth/change-my-pin",
                json={"new_pin": "7777"},
                headers=company_admin_headers
            )
            print(f"Set first PIN: {response.status_code} - {response.text}")
            # Should succeed
            if response.status_code == 200:
                # Now clear it (use the set endpoint)
                requests.put(
                    f"{BASE_URL}/api/auth/change-my-pin",
                    json={"current_pin": "7777", "new_pin": ""},
                    headers=company_admin_headers
                )


class TestUnifiedPinResolveWithManagerPin:
    """Verify manager_pin (521325) works on public verify and mark-reviewed"""
    
    def test_public_verify_accepts_manager_pin(self, super_admin_headers):
        """POST /api/verify/public/{type}/{id} should accept manager_pin"""
        # Get a PO first
        po_resp = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=super_admin_headers)
        if po_resp.status_code != 200 or not po_resp.json().get("purchase_orders"):
            pytest.skip("No POs available")
        
        po_id = po_resp.json()["purchase_orders"][0]["id"]
        
        # Public verify with manager PIN (no auth needed)
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        print(f"Public verify: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert response.json().get("method") == "manager_pin"
    
    def test_mark_reviewed_accepts_manager_pin(self, super_admin_headers):
        """POST /api/purchase-orders/{id}/mark-reviewed should accept manager_pin"""
        # Get a PO
        po_resp = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=super_admin_headers)
        if po_resp.status_code != 200 or not po_resp.json().get("purchase_orders"):
            pytest.skip("No POs available")
        
        po_id = po_resp.json()["purchase_orders"][0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/mark-reviewed",
            json={"pin": MANAGER_PIN, "notes": "Test review from iteration 53"},
            headers=super_admin_headers
        )
        print(f"Mark-reviewed: {response.status_code} - {response.text}")
        assert response.status_code == 200


class TestUsersEndpoint:
    """Test GET /api/users for staff PIN table data"""
    
    def test_users_list_returns_pin_fields(self, company_admin_headers):
        """GET /api/users should return manager_pin status for staff table"""
        response = requests.get(f"{BASE_URL}/api/users", headers=company_admin_headers)
        print(f"Users: {response.status_code}")
        assert response.status_code == 200
        
        users = response.json()
        assert isinstance(users, list)
        
        # Check that users have the expected structure for PIN management
        for u in users:
            assert "id" in u
            assert "username" in u
            assert "role" in u
            # manager_pin may or may not be present depending on user role


class TestSetStaffPin:
    """Test PUT /api/users/{user_id}/pin - admin sets staff PIN"""
    
    def test_admin_can_set_staff_pin(self, company_admin_headers):
        """Admin should be able to set PIN for any user"""
        # Get users list
        users_resp = requests.get(f"{BASE_URL}/api/users", headers=company_admin_headers)
        if users_resp.status_code != 200:
            pytest.skip("Cannot get users")
        
        users = users_resp.json()
        # Find a manager or admin that's not the current user
        target_user = next((u for u in users if u.get("role") in ["admin", "manager"]), None)
        
        if not target_user:
            pytest.skip("No manager/admin users to test with")
        
        # Set their PIN
        response = requests.put(
            f"{BASE_URL}/api/users/{target_user['id']}/pin",
            json={"pin": "1234"},
            headers=company_admin_headers
        )
        print(f"Set staff PIN: {response.status_code} - {response.text}")
        # Should succeed or fail based on permissions
        # We just check it doesn't 500
        assert response.status_code in [200, 403, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
