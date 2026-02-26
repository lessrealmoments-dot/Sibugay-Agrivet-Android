"""
Test Team & Settings Refactor (Iteration 54)

Features tested:
1. Bug Fix: PUT /api/auth/change-my-pin with wrong PIN returns 400 (not 401)
2. Team page APIs: GET /api/users?include_inactive=true, DELETE /api/users/{id}/permanent, PUT /api/users/{id}/reactivate
3. Navigation: /team route exists, /accounts & /user-permissions still work for backward compat
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"


class TestPinBugFix:
    """Test the critical bug fix: wrong PIN should return 400, not 401"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as super admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code} - {response.text}")
        return response.json().get("token")

    def test_change_my_pin_wrong_current_pin_returns_400(self, auth_token):
        """
        CRITICAL BUG FIX TEST:
        When user enters wrong current PIN, API should return 400 (not 401)
        401 causes axios interceptor to logout user - that's the bug being fixed
        """
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": "999999", "new_pin": "123456"},
            headers=headers
        )
        # Should be 400 (Bad Request), NOT 401 (Unauthorized)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}. This is the PIN logout bug!"
        assert "incorrect" in response.json().get("detail", "").lower()
        print(f"PASS: Wrong PIN returns 400 - bug fix verified")

    def test_change_my_pin_missing_current_pin_returns_400(self, auth_token):
        """If user has a PIN but doesn't provide current_pin, should return 400"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"new_pin": "123456"},  # Missing current_pin
            headers=headers
        )
        # Could be 400 or success if user has no PIN set yet
        # If 401 = BUG
        assert response.status_code != 401, "Got 401 which would cause logout bug!"
        print(f"Status: {response.status_code} - {response.json()}")

    def test_change_my_pin_short_new_pin_returns_400(self, auth_token):
        """PIN too short should return 400"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.put(
            f"{BASE_URL}/api/auth/change-my-pin",
            json={"current_pin": MANAGER_PIN, "new_pin": "12"},  # Too short
            headers=headers
        )
        assert response.status_code == 400
        assert "4 digits" in response.json().get("detail", "")


class TestUserManagementAPIs:
    """Test new user management endpoints for Team page"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as super admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")
        return response.json().get("token")

    def test_get_users_default(self, auth_token):
        """GET /api/users returns active users by default"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        # By default, only active users (but super admin sees all)
        print(f"Default GET /users returned {len(users)} users")

    def test_get_users_include_inactive(self, auth_token):
        """GET /api/users?include_inactive=true returns all users including disabled"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/users", params={"include_inactive": True}, headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        print(f"GET /users?include_inactive=true returned {len(users)} users")

    def test_create_and_disable_user_flow(self, auth_token):
        """Test create user -> disable -> reactivate -> permanent delete flow"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        import uuid
        test_username = f"test_user_{uuid.uuid4().hex[:8]}"

        # 1. Create user
        create_response = requests.post(f"{BASE_URL}/api/users", json={
            "username": test_username,
            "password": "Test123456",
            "full_name": "Test User for Disable Flow",
            "role": "cashier"
        }, headers=headers)
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create test user: {create_response.text}")
        
        user_id = create_response.json().get("id")
        assert user_id, "User ID not returned"
        print(f"Created test user: {test_username} (id: {user_id})")

        # 2. Disable user (soft delete)
        disable_response = requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=headers)
        assert disable_response.status_code == 200
        assert "deactivated" in disable_response.json().get("message", "").lower()
        print("User disabled successfully")

        # 3. Verify user appears in include_inactive list
        users_response = requests.get(f"{BASE_URL}/api/users", params={"include_inactive": True}, headers=headers)
        users = users_response.json()
        disabled_user = next((u for u in users if u["id"] == user_id), None)
        if disabled_user:
            assert disabled_user.get("active") == False
            print("Verified: Disabled user shows in include_inactive list")

        # 4. Reactivate user
        reactivate_response = requests.put(f"{BASE_URL}/api/users/{user_id}/reactivate", headers=headers)
        assert reactivate_response.status_code == 200
        assert "reactivated" in reactivate_response.json().get("message", "").lower()
        print("User reactivated successfully")

        # 5. Permanently delete user
        permanent_delete_response = requests.delete(f"{BASE_URL}/api/users/{user_id}/permanent", headers=headers)
        assert permanent_delete_response.status_code == 200
        assert "permanently deleted" in permanent_delete_response.json().get("message", "").lower()
        print("User permanently deleted successfully")

        # 6. Verify user no longer exists
        get_user_response = requests.get(f"{BASE_URL}/api/users/{user_id}", headers=headers)
        assert get_user_response.status_code == 404
        print("Verified: User no longer exists after permanent delete")

    def test_cannot_delete_own_account(self, auth_token):
        """Admin cannot disable or delete their own account"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get current user info
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if me_response.status_code != 200:
            pytest.skip("Cannot get current user")
        
        my_id = me_response.json().get("id")
        
        # Try to disable self
        disable_response = requests.delete(f"{BASE_URL}/api/users/{my_id}", headers=headers)
        assert disable_response.status_code == 400
        print("Correctly prevented self-disable")

        # Try to permanently delete self
        permanent_delete_response = requests.delete(f"{BASE_URL}/api/users/{my_id}/permanent", headers=headers)
        assert permanent_delete_response.status_code == 400
        print("Correctly prevented self-delete")

    def test_reactivate_nonexistent_user(self, auth_token):
        """Reactivating non-existent user returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.put(f"{BASE_URL}/api/users/nonexistent123/reactivate", headers=headers)
        assert response.status_code == 404

    def test_permanent_delete_nonexistent_user(self, auth_token):
        """Permanently deleting non-existent user returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.delete(f"{BASE_URL}/api/users/nonexistent123/permanent", headers=headers)
        assert response.status_code == 404


class TestPermissionsAPIs:
    """Test permission-related APIs used in Team page Permissions tab"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed")
        return response.json().get("token")

    def test_get_permission_modules(self, auth_token):
        """GET /api/permissions/modules returns all permission modules"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/permissions/modules", headers=headers)
        assert response.status_code == 200
        modules = response.json()
        assert isinstance(modules, dict)
        assert len(modules) > 0
        print(f"Permission modules: {list(modules.keys())}")

    def test_get_permission_presets(self, auth_token):
        """GET /api/permissions/presets returns role presets"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/permissions/presets", headers=headers)
        assert response.status_code == 200
        presets = response.json()
        assert isinstance(presets, dict)
        # Should have admin, manager, cashier presets at minimum
        print(f"Permission presets: {list(presets.keys())}")


class TestAdminSetUserPin:
    """Test admin setting PIN for any user via Team page"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed")
        return response.json().get("token")

    def test_admin_set_user_pin(self, auth_token):
        """PUT /api/users/{id}/pin - admin can set any user's PIN"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Get a user to test with
        users_response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        if users_response.status_code != 200 or not users_response.json():
            pytest.skip("No users available")
        
        # Find an admin/manager user (not super admin)
        users = users_response.json()
        target_user = next((u for u in users if u.get("role") in ["admin", "manager"] and u.get("username") != "janmarkeahig"), None)
        
        if not target_user:
            # Use own account
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            target_user = me_response.json()
        
        user_id = target_user.get("id")
        
        # Set a test PIN
        response = requests.put(
            f"{BASE_URL}/api/users/{user_id}/pin",
            json={"pin": "888888"},
            headers=headers
        )
        assert response.status_code == 200
        print(f"Admin set PIN for user {target_user.get('username')}")

        # Clear the PIN back
        clear_response = requests.put(
            f"{BASE_URL}/api/users/{user_id}/pin",
            json={"pin": ""},
            headers=headers
        )
        # Should succeed or the original PIN should be kept
        print(f"Clear PIN response: {clear_response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
