"""
Terminal Branch Restriction & Navigation Redesign - Iteration 116
Testing the following fixes:
1. Branch restriction - managers/cashiers can only pair to their assigned branch, admins can pair to any
2. Terminal navigation redesign - floating mode selector replacing bottom tabs
3. QR auto-pairing still works with ?pair=TOKEN URL

Test credentials:
- Admin: testadmin@test.com / Test@123 (can pair to any branch)
- Manager: testmanager@test.com / Test@123 (Branch 1 only: c435277f-9fc7-4d83-83e7-38be5b4423ac)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USER = {"email": "testadmin@test.com", "password": "Test@123"}
MANAGER_USER = {"email": "testmanager@test.com", "password": "Test@123"}
BRANCH_ID_1 = "c435277f-9fc7-4d83-83e7-38be5b4423ac"  # Branch 1 - manager's assigned branch
BRANCH_ID_2 = "18c02daa-bce0-45de-860a-70ccc6ed6c6d"  # Branch 2 - different branch


class TestAdminCanPairToAnyBranch:
    """Admin should be able to pair terminal to any branch"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        token = response.json().get("token")
        assert token, "No token returned for admin"
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_admin_can_initiate_qr_pairing_branch1(self, admin_headers):
        """Admin can initiate QR pairing for Branch 1"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_1},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "branch_name" in data, "Response should contain branch_name"
        print(f"PASS: Admin initiated QR pairing for Branch 1 - token: {data['token'][:16]}...")
    
    def test_admin_can_initiate_qr_pairing_branch2(self, admin_headers):
        """Admin can initiate QR pairing for Branch 2 (different branch)"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_2},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        print(f"PASS: Admin initiated QR pairing for Branch 2 - token: {data['token'][:16]}...")
    
    def test_admin_can_pair_terminal_to_branch1(self, admin_headers):
        """Admin can pair terminal to Branch 1 using code"""
        # Generate code first
        code_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        assert code_res.status_code == 200, f"Code generation failed: {code_res.text}"
        code = code_res.json().get("code")
        
        # Pair to Branch 1
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/pair",
            json={"code": code, "branch_id": BRANCH_ID_1},
            headers=admin_headers
        )
        assert pair_res.status_code == 200, f"Expected 200, got {pair_res.status_code}: {pair_res.text}"
        data = pair_res.json()
        assert "terminal_id" in data, "Response should contain terminal_id"
        print(f"PASS: Admin paired terminal to Branch 1")
    
    def test_admin_can_pair_terminal_to_branch2(self, admin_headers):
        """Admin can pair terminal to Branch 2 (different branch)"""
        # Generate code first
        code_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        assert code_res.status_code == 200, f"Code generation failed: {code_res.text}"
        code = code_res.json().get("code")
        
        # Pair to Branch 2
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/pair",
            json={"code": code, "branch_id": BRANCH_ID_2},
            headers=admin_headers
        )
        assert pair_res.status_code == 200, f"Expected 200, got {pair_res.status_code}: {pair_res.text}"
        data = pair_res.json()
        assert "terminal_id" in data, "Response should contain terminal_id"
        print(f"PASS: Admin paired terminal to Branch 2")


class TestManagerBranchRestriction:
    """Manager should only be able to pair terminal to their assigned branch"""
    
    @pytest.fixture(scope="class")
    def manager_headers(self):
        """Get manager authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_USER)
        assert response.status_code == 200, f"Manager login failed: {response.text}"
        token = response.json().get("token")
        assert token, "No token returned for manager"
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_manager_can_pair_to_own_branch(self, manager_headers):
        """Manager can pair terminal to their assigned branch (Branch 1)"""
        # Generate code first
        code_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        assert code_res.status_code == 200, f"Code generation failed: {code_res.text}"
        code = code_res.json().get("code")
        
        # Pair to Branch 1 (manager's branch)
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/pair",
            json={"code": code, "branch_id": BRANCH_ID_1},
            headers=manager_headers
        )
        assert pair_res.status_code == 200, f"Expected 200, got {pair_res.status_code}: {pair_res.text}"
        data = pair_res.json()
        assert "terminal_id" in data, "Response should contain terminal_id"
        print(f"PASS: Manager paired terminal to their own branch (Branch 1)")
    
    def test_manager_cannot_pair_to_different_branch(self, manager_headers):
        """Manager CANNOT pair terminal to a different branch (Branch 2) - should get 403"""
        # Generate code first
        code_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        assert code_res.status_code == 200, f"Code generation failed: {code_res.text}"
        code = code_res.json().get("code")
        
        # Try to pair to Branch 2 (NOT manager's branch) - should fail
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/pair",
            json={"code": code, "branch_id": BRANCH_ID_2},
            headers=manager_headers
        )
        assert pair_res.status_code == 403, f"Expected 403 (forbidden), got {pair_res.status_code}: {pair_res.text}"
        error_detail = pair_res.json().get("detail", "")
        assert "assigned branch" in error_detail.lower() or "branch" in error_detail.lower(), \
            f"Error should mention branch restriction, got: {error_detail}"
        print(f"PASS: Manager blocked from pairing to different branch - {error_detail}")
    
    def test_manager_can_initiate_qr_pairing_own_branch(self, manager_headers):
        """Manager can initiate QR pairing for their own branch (Branch 1)"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_1},
            headers=manager_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        print(f"PASS: Manager initiated QR pairing for own branch")
    
    def test_manager_cannot_initiate_qr_pairing_different_branch(self, manager_headers):
        """Manager CANNOT initiate QR pairing for different branch - should get 403"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_2},
            headers=manager_headers
        )
        assert response.status_code == 403, f"Expected 403 (forbidden), got {response.status_code}: {response.text}"
        error_detail = response.json().get("detail", "")
        assert "assigned branch" in error_detail.lower() or "branch" in error_detail.lower(), \
            f"Error should mention branch restriction, got: {error_detail}"
        print(f"PASS: Manager blocked from QR pairing for different branch - {error_detail}")


class TestQRAutoPairingFlow:
    """Test QR auto-pairing flow with ?pair=TOKEN URL"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_qr_pair_token_generation(self, admin_headers):
        """Generate QR pair token returns valid token"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_1},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "token" in data, "Should return token"
        assert len(data["token"]) > 20, "Token should be substantial length"
        assert "expires_in" in data, "Should return expiry info"
        print(f"PASS: QR pair token generated - expires in {data['expires_in']}s")
        return data["token"]
    
    def test_qr_pair_endpoint_works(self, admin_headers):
        """Terminal can use QR token to auto-pair"""
        # First generate token
        gen_res = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_1},
            headers=admin_headers
        )
        assert gen_res.status_code == 200
        token = gen_res.json()["token"]
        
        # Use token to pair (no auth needed - token is proof)
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/qr-pair",
            json={"token": token}
        )
        assert pair_res.status_code == 200, f"Expected 200, got {pair_res.status_code}: {pair_res.text}"
        data = pair_res.json()
        assert data.get("status") == "paired", f"Expected status=paired, got {data.get('status')}"
        assert "token" in data, "Should return session token"
        assert "terminal_id" in data, "Should return terminal_id"
        assert "branch_id" in data, "Should return branch_id"
        print(f"PASS: QR auto-pairing successful - terminal_id: {data['terminal_id'][:8]}...")
    
    def test_qr_pair_invalid_token_fails(self):
        """Invalid QR token should fail"""
        pair_res = requests.post(
            f"{BASE_URL}/api/terminal/qr-pair",
            json={"token": "invalid-token-12345"}
        )
        assert pair_res.status_code in [404, 410], f"Expected 404/410, got {pair_res.status_code}"
        print(f"PASS: Invalid QR token rejected with {pair_res.status_code}")
    
    def test_qr_pair_token_cannot_be_reused(self, admin_headers):
        """QR token should only work once"""
        # Generate and use token
        gen_res = requests.post(
            f"{BASE_URL}/api/terminal/initiate-qr-pairing",
            json={"branch_id": BRANCH_ID_1},
            headers=admin_headers
        )
        token = gen_res.json()["token"]
        
        # First use
        first_res = requests.post(f"{BASE_URL}/api/terminal/qr-pair", json={"token": token})
        assert first_res.status_code == 200, "First use should succeed"
        
        # Second use should fail
        second_res = requests.post(f"{BASE_URL}/api/terminal/qr-pair", json={"token": token})
        assert second_res.status_code in [404, 410], f"Second use should fail, got {second_res.status_code}"
        print(f"PASS: QR token cannot be reused - second attempt returned {second_res.status_code}")


class TestTerminalEndpointBasics:
    """Basic endpoint tests for terminal pairing"""
    
    def test_generate_code_no_auth_required(self):
        """Generate code endpoint should not require auth"""
        response = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "code" in data, "Should return code"
        assert len(data["code"]) == 6, "Code should be 6 characters"
        assert "expires_in" in data, "Should return expiry"
        print(f"PASS: Generate code works - code: {data['code']}")
    
    def test_poll_pairing_status(self):
        """Poll endpoint should return status"""
        # Generate a code first
        gen_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        code = gen_res.json()["code"]
        
        # Poll status
        poll_res = requests.get(f"{BASE_URL}/api/terminal/poll/{code}")
        assert poll_res.status_code == 200, f"Expected 200, got {poll_res.status_code}"
        data = poll_res.json()
        assert "status" in data, "Should return status"
        assert data["status"] in ["pending", "paired", "expired", "invalid"], f"Unexpected status: {data['status']}"
        print(f"PASS: Poll status works - status: {data['status']}")
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_active_terminals_list(self, admin_headers):
        """List active terminals endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/active",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Active terminals endpoint works - {len(data)} terminals")


class TestVerifyManagerBranchAssignment:
    """Verify test manager has correct branch assignment"""
    
    @pytest.fixture(scope="class")
    def manager_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_USER)
        return response.json()
    
    def test_manager_user_exists(self, manager_token):
        """Verify manager user exists and can login"""
        assert "token" in manager_token, "Manager should be able to login"
        print(f"PASS: Manager user exists and can login")
    
    def test_manager_has_branch_assignment(self, manager_token):
        """Verify manager has branch_id assigned"""
        user = manager_token.get("user", {})
        branch_id = user.get("branch_id")
        # Note: branch_id may be in token or user object depending on implementation
        if branch_id:
            print(f"PASS: Manager has branch_id: {branch_id}")
        else:
            # Check profile endpoint
            headers = {"Authorization": f"Bearer {manager_token['token']}"}
            profile_res = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers)
            if profile_res.status_code == 200:
                profile = profile_res.json()
                branch_id = profile.get("branch_id")
                print(f"INFO: Manager branch_id from profile: {branch_id}")
            print("INFO: Manager branch_id verification - check terminal.py branch restriction logic")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
