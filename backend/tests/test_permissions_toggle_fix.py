"""
Backend tests for User Permissions system.
Tests: PUT /users/{user_id}/permissions, permission persistence, check_perm,
       count_sheets module, modules list, presets.
Focus: Verifying the toggle-save-persist flow works correctly.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

CASHIER_USER_ID = "f57de378-c8e2-4ba0-971a-dc69f0f8a993"  # testcashier_ui

@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner",
        "password": "521325"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]

@pytest.fixture(scope="module")
def admin_session(admin_token):
    """Requests session with admin auth."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    })
    return s


class TestPermissionModules:
    """GET /permissions/modules - all modules and actions"""

    def test_modules_returns_dict(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/permissions/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "Modules should be a dict"
        print(f"✓ Modules returned: {list(data.keys())}")

    def test_expected_modules_present(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/permissions/modules")
        modules = resp.json()
        expected = [
            "dashboard", "branches", "products", "inventory", "sales",
            "purchase_orders", "suppliers", "customers", "accounting",
            "price_schemes", "reports", "settings", "count_sheets"
        ]
        for mod in expected:
            assert mod in modules, f"Module '{mod}' missing from /permissions/modules"
        print(f"✓ All {len(expected)} expected modules present including count_sheets")

    def test_count_sheets_module_has_correct_actions(self, admin_session):
        """count_sheets module must exist with correct actions."""
        resp = admin_session.get(f"{BASE_URL}/api/permissions/modules")
        modules = resp.json()
        assert "count_sheets" in modules, "count_sheets module missing"
        actions = modules["count_sheets"]["actions"]
        for act in ["view", "create", "count", "complete", "cancel", "adjust"]:
            assert act in actions, f"count_sheets missing action '{act}'"
        print(f"✓ count_sheets module: label={modules['count_sheets']['label']}, actions={list(actions.keys())}")

    def test_each_module_has_label_and_actions(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/permissions/modules")
        modules = resp.json()
        for key, mod in modules.items():
            assert "label" in mod, f"Module '{key}' missing 'label'"
            assert "actions" in mod, f"Module '{key}' missing 'actions'"
            assert len(mod["actions"]) > 0, f"Module '{key}' has no actions"
        print(f"✓ All {len(modules)} modules have label and actions")


class TestPermissionPresets:
    """GET /permissions/presets - role presets"""

    def test_presets_return_expected_roles(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/permissions/presets")
        assert resp.status_code == 200
        presets = resp.json()
        for preset in ["admin", "manager", "cashier", "inventory_clerk"]:
            assert preset in presets, f"Preset '{preset}' missing"
        print(f"✓ Presets: {list(presets.keys())}")

    def test_cashier_preset_limited_permissions(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/permissions/presets/cashier")
        assert resp.status_code == 200
        preset = resp.json()
        sales = preset["permissions"].get("sales", {})
        assert sales.get("view") == True, "cashier should have sales.view"
        assert sales.get("create") == True, "cashier should have sales.create"
        assert sales.get("void") == False, "cashier should NOT have sales.void"
        print("✓ Cashier preset has correct limited permissions")


class TestPutUserPermissions:
    """PUT /users/{user_id}/permissions - core toggle-save-persist flow"""

    def test_put_permissions_returns_200(self, admin_session):
        """PUT permissions should return 200 with message."""
        # Get current permissions first
        get_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        assert get_resp.status_code == 200
        current_perms = get_resp.json()["permissions"]

        resp = admin_session.put(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions",
            json={"permissions": current_perms}
        )
        assert resp.status_code == 200, f"PUT permissions returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data or "user_id" in data, "Response should have message or user_id"
        print(f"✓ PUT permissions returned 200: {data}")

    def test_toggle_permission_on_saves_correctly(self, admin_session):
        """Toggle inventory.adjust from False to True - should persist."""
        # Step 1: Get current state
        get_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        assert get_resp.status_code == 200
        perms = get_resp.json()["permissions"]
        original_value = perms.get("inventory", {}).get("adjust", False)
        print(f"  Original inventory.adjust = {original_value}")

        # Step 2: Toggle to True (ON)
        new_perms = {k: dict(v) for k, v in perms.items()}  # deep copy
        if "inventory" not in new_perms:
            new_perms["inventory"] = {}
        new_perms["inventory"]["adjust"] = True

        put_resp = admin_session.put(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions",
            json={"permissions": new_perms}
        )
        assert put_resp.status_code == 200, f"PUT failed: {put_resp.text}"

        # Step 3: GET again to verify persistence
        verify_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        assert verify_resp.status_code == 200
        saved_perms = verify_resp.json()["permissions"]
        assert saved_perms.get("inventory", {}).get("adjust") == True, \
            "inventory.adjust should be True after saving"
        print("✓ inventory.adjust toggled ON and persisted correctly")

    def test_toggle_permission_off_saves_correctly(self, admin_session):
        """Toggle inventory.adjust back to False - should persist."""
        # First verify it's ON (from previous test)
        get_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        perms = get_resp.json()["permissions"]

        # Toggle OFF
        new_perms = {k: dict(v) for k, v in perms.items()}
        new_perms["inventory"]["adjust"] = False

        put_resp = admin_session.put(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions",
            json={"permissions": new_perms}
        )
        assert put_resp.status_code == 200

        # Verify persistence
        verify_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        saved_perms = verify_resp.json()["permissions"]
        assert saved_perms.get("inventory", {}).get("adjust") == False, \
            "inventory.adjust should be False after toggling OFF"
        print("✓ inventory.adjust toggled OFF and persisted correctly")

    def test_permission_preset_set_to_custom_after_put(self, admin_session):
        """After PUT /permissions, permission_preset should be 'custom'."""
        get_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        perms = get_resp.json()["permissions"]

        put_resp = admin_session.put(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions",
            json={"permissions": perms}
        )
        assert put_resp.status_code == 200

        verify_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        data = verify_resp.json()
        assert data.get("permission_preset") == "custom", \
            f"permission_preset should be 'custom' after PUT, got: {data.get('permission_preset')}"
        print(f"✓ permission_preset = 'custom' after PUT")

    def test_multiple_module_permissions_saved_atomically(self, admin_session):
        """Save multiple module permissions in one PUT call."""
        get_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        perms = get_resp.json()["permissions"]

        # Modify multiple modules
        new_perms = {k: dict(v) for k, v in perms.items()}
        new_perms.setdefault("sales", {})["void"] = True
        new_perms.setdefault("customers", {})["manage_credit"] = True

        put_resp = admin_session.put(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions",
            json={"permissions": new_perms}
        )
        assert put_resp.status_code == 200

        # Verify both changes
        verify_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        saved = verify_resp.json()["permissions"]
        assert saved.get("sales", {}).get("void") == True, "sales.void should be True"
        assert saved.get("customers", {}).get("manage_credit") == True, "customers.manage_credit should be True"
        print("✓ Multiple module permissions saved atomically")

        # Cleanup - revert
        new_perms["sales"]["void"] = False
        new_perms["customers"]["manage_credit"] = False
        admin_session.put(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions", json={"permissions": new_perms})
        print("  ✓ Reverted multi-module changes")


class TestGetUserPermissions:
    """GET /users/{user_id}/permissions - correct structure and data"""

    def test_get_permissions_structure(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "username" in data
        assert "permissions" in data
        assert isinstance(data["permissions"], dict)
        print(f"✓ GET permissions structure correct for {data['username']}")

    def test_users_list_endpoint(self, admin_session):
        resp = admin_session.get(f"{BASE_URL}/api/users")
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 2, "Should have at least 2 users (owner + testcashier_ui)"
        usernames = [u["username"] for u in users]
        assert "owner" in usernames, "owner should be in users list"
        assert "testcashier_ui" in usernames, "testcashier_ui should be in users list"
        print(f"✓ Users list: {usernames}")

    def test_unauthenticated_access_denied(self):
        """Without token, permissions endpoint should return 403 or 401."""
        resp = requests.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        assert resp.status_code in [401, 403, 422], \
            f"Unauthenticated request should be denied, got {resp.status_code}"
        print(f"✓ Unauthenticated access returns {resp.status_code}")


class TestApplyPreset:
    """POST /users/{user_id}/apply-preset - apply full preset"""

    def test_apply_manager_preset_and_verify(self, admin_session):
        """Apply manager preset and verify permissions are set correctly."""
        # Get manager preset permissions
        preset_resp = admin_session.get(f"{BASE_URL}/api/permissions/presets/manager")
        assert preset_resp.status_code == 200
        manager_permissions = preset_resp.json()["permissions"]

        # Apply manager preset to testcashier_ui
        resp = admin_session.post(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/apply-preset",
            json={"preset": "manager"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("permission_preset") == "manager", \
            f"permission_preset should be 'manager', got: {data.get('permission_preset')}"
        print(f"✓ Manager preset applied, permission_preset={data.get('permission_preset')}")

        # Verify permissions match manager preset
        verify_resp = admin_session.get(f"{BASE_URL}/api/users/{CASHIER_USER_ID}/permissions")
        saved_perms = verify_resp.json()["permissions"]
        # Check a few manager-specific permissions
        for mod, acts in manager_permissions.items():
            if mod in saved_perms:
                for act, val in acts.items():
                    assert saved_perms[mod].get(act) == val, \
                        f"After applying manager preset: {mod}.{act} should be {val}, got {saved_perms[mod].get(act)}"
        print("✓ Manager preset permissions persisted and match expected values")

    def test_revert_to_cashier_preset(self, admin_session):
        """Revert testcashier_ui back to cashier preset."""
        resp = admin_session.post(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/apply-preset",
            json={"preset": "cashier"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("permission_preset") == "cashier"
        print(f"✓ Reverted to cashier preset")

    def test_invalid_preset_returns_400(self, admin_session):
        resp = admin_session.post(
            f"{BASE_URL}/api/users/{CASHIER_USER_ID}/apply-preset",
            json={"preset": "nonexistent_role"}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ Invalid preset returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
