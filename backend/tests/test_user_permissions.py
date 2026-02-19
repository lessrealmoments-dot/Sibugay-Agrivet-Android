"""
Test suite for User Permissions Granular System
Tests permission modules, presets, and user permission management
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUserPermissions:
    """Permission system endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.admin_user = login_response.json().get("user")
        print(f"Logged in as admin: {self.admin_user.get('username')}")
    
    # ============ Module 1: Get Permission Modules ============
    def test_get_permission_modules(self):
        """GET /api/permissions/modules - Should return all available permission modules"""
        response = self.session.get(f"{BASE_URL}/api/permissions/modules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        modules = response.json()
        assert isinstance(modules, dict), "Modules should be a dictionary"
        
        # Check expected modules exist
        expected_modules = ["dashboard", "branches", "products", "inventory", "sales", 
                          "purchase_orders", "suppliers", "customers", "accounting", 
                          "price_schemes", "reports", "settings"]
        for mod in expected_modules:
            assert mod in modules, f"Module '{mod}' should be in response"
            assert "label" in modules[mod], f"Module '{mod}' should have a label"
            assert "actions" in modules[mod], f"Module '{mod}' should have actions"
        
        print(f"✓ Found {len(modules)} permission modules")
        print(f"  Modules: {list(modules.keys())}")
    
    # ============ Module 2: Get Permission Presets ============
    def test_get_permission_presets(self):
        """GET /api/permissions/presets - Should return all role presets"""
        response = self.session.get(f"{BASE_URL}/api/permissions/presets")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        presets = response.json()
        assert isinstance(presets, dict), "Presets should be a dictionary"
        
        # Check expected presets exist
        expected_presets = ["admin", "manager", "cashier", "inventory_clerk"]
        for preset in expected_presets:
            assert preset in presets, f"Preset '{preset}' should exist"
            assert "label" in presets[preset], f"Preset '{preset}' should have a label"
            assert "description" in presets[preset], f"Preset '{preset}' should have description"
            assert "permissions" in presets[preset], f"Preset '{preset}' should have permissions"
        
        print(f"✓ Found {len(presets)} role presets: {list(presets.keys())}")
    
    def test_get_specific_preset(self):
        """GET /api/permissions/presets/{preset_key} - Should return specific preset details"""
        response = self.session.get(f"{BASE_URL}/api/permissions/presets/cashier")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        preset = response.json()
        assert preset.get("label") == "Cashier", "Label should be 'Cashier'"
        assert "permissions" in preset, "Should have permissions object"
        
        # Cashier should have limited sales permissions
        sales_perms = preset["permissions"].get("sales", {})
        assert sales_perms.get("view") == True, "Cashier should have sales.view"
        assert sales_perms.get("create") == True, "Cashier should have sales.create"
        assert sales_perms.get("void") == False, "Cashier should NOT have sales.void"
        
        print("✓ Cashier preset retrieved with correct permissions")
    
    def test_get_invalid_preset(self):
        """GET /api/permissions/presets/{invalid} - Should return 404"""
        response = self.session.get(f"{BASE_URL}/api/permissions/presets/nonexistent")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid preset returns 404")
    
    # ============ Module 3: Get Users List ============
    def test_get_users_list(self):
        """GET /api/users - Should return list of users"""
        response = self.session.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Users should be a list"
        assert len(users) > 0, "Should have at least one user"
        
        # Check user structure
        for user in users:
            assert "id" in user, "User should have id"
            assert "username" in user, "User should have username"
            assert "role" in user, "User should have role"
        
        print(f"✓ Found {len(users)} users")
        for u in users[:5]:  # Print first 5
            print(f"  - {u.get('username')} ({u.get('role')})")
        return users
    
    # ============ Module 4: Get User Permissions ============
    def test_get_user_permissions(self):
        """GET /api/users/{user_id}/permissions - Should return user's permissions"""
        # First get users list
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        
        # Find a non-admin user (cashier) to test
        test_user = None
        for u in users:
            if u.get("role") == "cashier" or u.get("username") == "cashier":
                test_user = u
                break
        
        if not test_user:
            test_user = users[0]  # Fallback to first user
        
        user_id = test_user["id"]
        response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Response should have user_id"
        assert "permissions" in data, "Response should have permissions"
        assert "permission_preset" in data or "role" in data, "Response should have preset or role"
        
        print(f"✓ Got permissions for user: {test_user.get('username')}")
        print(f"  Preset: {data.get('permission_preset', data.get('role'))}")
        return test_user
    
    # ============ Module 5: Update User Permissions ============
    def test_update_user_permissions(self):
        """PUT /api/users/{user_id}/permissions - Should update user's permissions"""
        # Get users list
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        
        # Find cashier user
        test_user = None
        for u in users:
            if u.get("role") == "cashier" or u.get("username") == "cashier":
                test_user = u
                break
        
        if not test_user:
            pytest.skip("No cashier user found to test permission update")
        
        user_id = test_user["id"]
        
        # Get current permissions first
        current_perms_response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        current_perms = current_perms_response.json().get("permissions", {})
        
        # Modify one permission - give cashier void permission
        new_permissions = current_perms.copy()
        if "sales" not in new_permissions:
            new_permissions["sales"] = {}
        new_permissions["sales"]["void"] = True
        
        # Update permissions
        response = self.session.put(f"{BASE_URL}/api/users/{user_id}/permissions", json={
            "permissions": new_permissions
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated_user = response.json()
        assert updated_user.get("permissions", {}).get("sales", {}).get("void") == True, \
            "sales.void should now be True"
        
        print(f"✓ Updated permissions for user: {test_user.get('username')}")
        
        # Revert the change
        new_permissions["sales"]["void"] = False
        revert_response = self.session.put(f"{BASE_URL}/api/users/{user_id}/permissions", json={
            "permissions": new_permissions
        })
        assert revert_response.status_code == 200, "Reverting permissions should succeed"
        print("  ✓ Reverted permissions back")
    
    # ============ Module 6: Apply Preset ============
    def test_apply_preset(self):
        """POST /api/users/{user_id}/apply-preset - Should apply a preset to user"""
        # Get users list
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        
        # Find cashier user
        test_user = None
        for u in users:
            if u.get("role") == "cashier" or u.get("username") == "cashier":
                test_user = u
                break
        
        if not test_user:
            pytest.skip("No cashier user found to test preset application")
        
        user_id = test_user["id"]
        
        # Save original preset/permissions
        original_response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        original_preset = original_response.json().get("permission_preset", "cashier")
        
        # Apply manager preset (temporarily)
        response = self.session.post(f"{BASE_URL}/api/users/{user_id}/apply-preset", json={
            "preset": "manager"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated_user = response.json()
        assert updated_user.get("permission_preset") == "manager" or updated_user.get("role") == "manager", \
            "User should now have manager preset"
        
        print(f"✓ Applied 'manager' preset to user: {test_user.get('username')}")
        
        # Revert to original preset
        revert_response = self.session.post(f"{BASE_URL}/api/users/{user_id}/apply-preset", json={
            "preset": original_preset if original_preset in ["admin", "manager", "cashier", "inventory_clerk"] else "cashier"
        })
        assert revert_response.status_code == 200, "Reverting preset should succeed"
        print(f"  ✓ Reverted back to '{original_preset}' preset")
    
    def test_apply_invalid_preset(self):
        """POST /api/users/{user_id}/apply-preset - Invalid preset should return 400"""
        # Get a user
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        user_id = users[0]["id"]
        
        response = self.session.post(f"{BASE_URL}/api/users/{user_id}/apply-preset", json={
            "preset": "invalid_preset_name"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid preset returns 400")
    
    # ============ Module 7: Update Module Permissions ============
    def test_update_module_permissions(self):
        """PUT /api/users/{user_id}/permissions/module/{module} - Should update specific module"""
        # Get users list
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        
        # Find cashier user
        test_user = None
        for u in users:
            if u.get("role") == "cashier" or u.get("username") == "cashier":
                test_user = u
                break
        
        if not test_user:
            pytest.skip("No cashier user found to test module permission update")
        
        user_id = test_user["id"]
        
        # Get current permissions first
        current_perms_response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        current_inventory_perms = current_perms_response.json().get("permissions", {}).get("inventory", {})
        
        # Update inventory module permissions - give adjust permission
        response = self.session.put(f"{BASE_URL}/api/users/{user_id}/permissions/module/inventory", json={
            "actions": {
                "view": True,
                "adjust": True,  # Usually cashier doesn't have this
                "transfer": False
            }
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated_user = response.json()
        assert updated_user.get("permissions", {}).get("inventory", {}).get("adjust") == True, \
            "inventory.adjust should now be True"
        assert updated_user.get("permission_preset") == "custom", \
            "User should now have 'custom' preset since permissions were modified"
        
        print(f"✓ Updated inventory module permissions for user: {test_user.get('username')}")
        
        # Revert - apply cashier preset back
        revert_response = self.session.post(f"{BASE_URL}/api/users/{user_id}/apply-preset", json={
            "preset": "cashier"
        })
        assert revert_response.status_code == 200
        print("  ✓ Reverted back to cashier preset")
    
    def test_update_invalid_module_permissions(self):
        """PUT /api/users/{user_id}/permissions/module/{invalid} - Should return 400"""
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        user_id = users[0]["id"]
        
        response = self.session.put(f"{BASE_URL}/api/users/{user_id}/permissions/module/invalid_module", json={
            "actions": {"view": True}
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid module returns 400")
    
    # ============ Data Integrity Tests ============
    def test_permission_changes_persist(self):
        """Verify permission changes persist correctly in database"""
        # Get users list
        users_response = self.session.get(f"{BASE_URL}/api/users")
        users = users_response.json()
        
        # Find cashier user
        test_user = None
        for u in users:
            if u.get("role") == "cashier" or u.get("username") == "cashier":
                test_user = u
                break
        
        if not test_user:
            pytest.skip("No cashier user found")
        
        user_id = test_user["id"]
        
        # Save original state
        original_response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        original_data = original_response.json()
        
        # Make a change
        new_perms = original_data.get("permissions", {}).copy()
        if "customers" not in new_perms:
            new_perms["customers"] = {}
        new_perms["customers"]["manage_credit"] = True
        
        # Update
        update_response = self.session.put(f"{BASE_URL}/api/users/{user_id}/permissions", json={
            "permissions": new_perms
        })
        assert update_response.status_code == 200
        
        # Fetch again to verify persistence
        verify_response = self.session.get(f"{BASE_URL}/api/users/{user_id}/permissions")
        verify_data = verify_response.json()
        
        assert verify_data.get("permissions", {}).get("customers", {}).get("manage_credit") == True, \
            "Permission change should persist"
        
        print("✓ Permission changes persist correctly")
        
        # Revert
        revert_response = self.session.post(f"{BASE_URL}/api/users/{user_id}/apply-preset", json={
            "preset": "cashier"
        })
        assert revert_response.status_code == 200
        print("  ✓ Reverted to original state")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
