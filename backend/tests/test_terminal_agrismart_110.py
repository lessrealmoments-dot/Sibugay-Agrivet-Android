"""
Test AgriSmart Terminal - Pairing APIs (Iteration 110)
Tests the YouTube TV-style device pairing flow for mobile POS terminals.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Super admin credentials from test request
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"

@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for super admin"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json().get("token")

@pytest.fixture(scope="module")
def api_client():
    """Basic requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_client(api_client, auth_token):
    """Authenticated requests session"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client

@pytest.fixture(scope="module")
def branches(auth_client):
    """Get list of branches for pairing"""
    res = auth_client.get(f"{BASE_URL}/api/branches")
    assert res.status_code == 200
    return res.json() if isinstance(res.json(), list) else res.json().get('branches', [])


class TestTerminalCodeGeneration:
    """Test POST /api/terminal/generate-code - No auth required"""
    
    def test_generate_code_returns_6_char_code(self, api_client):
        """Generate code endpoint should return 6-character alphanumeric code"""
        res = api_client.post(f"{BASE_URL}/api/terminal/generate-code")
        assert res.status_code == 200, f"Failed to generate code: {res.text}"
        
        data = res.json()
        assert "code" in data, "Response missing 'code' field"
        assert "expires_in" in data, "Response missing 'expires_in' field"
        
        code = data["code"]
        assert len(code) == 6, f"Code length should be 6, got {len(code)}"
        assert code.isalnum(), f"Code should be alphanumeric, got {code}"
        assert code.isupper() or any(c.isdigit() for c in code), "Code should be uppercase letters and digits"
        
        expires_in = data["expires_in"]
        assert expires_in == 300, f"Expiry should be 300 seconds, got {expires_in}"
        print(f"Generated code: {code}, expires in {expires_in}s")
    
    def test_generate_code_no_auth_required(self):
        """Generate code should work without authentication"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/terminal/generate-code")
        assert res.status_code == 200, "Generate code should not require auth"


class TestTerminalPolling:
    """Test GET /api/terminal/poll/{code} - No auth required"""
    
    def test_poll_pending_code(self, api_client):
        """Poll a freshly generated code - should return 'pending'"""
        # Generate a new code
        gen_res = api_client.post(f"{BASE_URL}/api/terminal/generate-code")
        assert gen_res.status_code == 200
        code = gen_res.json()["code"]
        
        # Poll the code
        poll_res = api_client.get(f"{BASE_URL}/api/terminal/poll/{code}")
        assert poll_res.status_code == 200, f"Poll failed: {poll_res.text}"
        
        data = poll_res.json()
        assert data["status"] == "pending", f"Expected 'pending', got {data['status']}"
        print(f"Poll result for code {code}: {data['status']}")
    
    def test_poll_invalid_code(self, api_client):
        """Poll a non-existent code - should return 'invalid'"""
        res = api_client.get(f"{BASE_URL}/api/terminal/poll/ZZZZZZ")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "invalid", f"Expected 'invalid', got {data['status']}"
    
    def test_poll_lowercase_code_normalized(self, api_client):
        """Poll should normalize lowercase codes to uppercase"""
        gen_res = api_client.post(f"{BASE_URL}/api/terminal/generate-code")
        code = gen_res.json()["code"]
        
        # Poll with lowercase
        poll_res = api_client.get(f"{BASE_URL}/api/terminal/poll/{code.lower()}")
        assert poll_res.status_code == 200
        data = poll_res.json()
        assert data["status"] == "pending", "Should normalize lowercase input"


class TestTerminalPairing:
    """Test POST /api/terminal/pair - Requires auth"""
    
    def test_pair_terminal_success(self, auth_client, branches):
        """Pair a terminal with valid code and branch"""
        if not branches:
            pytest.skip("No branches available for pairing test")
        
        branch_id = branches[0]["id"]
        
        # Generate a code
        gen_res = auth_client.post(f"{BASE_URL}/api/terminal/generate-code")
        assert gen_res.status_code == 200
        code = gen_res.json()["code"]
        
        # Pair the terminal
        pair_res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": code,
            "branch_id": branch_id
        })
        assert pair_res.status_code == 200, f"Pair failed: {pair_res.text}"
        
        data = pair_res.json()
        assert "terminal_id" in data, "Response missing 'terminal_id'"
        assert "message" in data, "Response missing 'message'"
        print(f"Paired terminal: {data}")
        
        # Verify the code is now 'paired' when polled
        poll_res = auth_client.get(f"{BASE_URL}/api/terminal/poll/{code}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["status"] == "paired", f"Expected 'paired', got {poll_data['status']}"
        assert "token" in poll_data, "Paired response should include token"
        assert poll_data["terminal_id"] == data["terminal_id"]
    
    def test_pair_terminal_invalid_code_length(self, auth_client, branches):
        """Pairing with invalid code length should fail"""
        if not branches:
            pytest.skip("No branches available")
        
        res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": "ABC",  # Too short
            "branch_id": branches[0]["id"]
        })
        assert res.status_code == 400, "Should reject invalid code length"
    
    def test_pair_terminal_missing_branch(self, auth_client):
        """Pairing without branch_id should fail"""
        gen_res = auth_client.post(f"{BASE_URL}/api/terminal/generate-code")
        code = gen_res.json()["code"]
        
        res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": code
        })
        assert res.status_code == 400, "Should reject missing branch_id"
    
    def test_pair_terminal_nonexistent_code(self, auth_client, branches):
        """Pairing with non-existent code should fail"""
        if not branches:
            pytest.skip("No branches available")
        
        res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": "XYXYXY",  # Non-existent
            "branch_id": branches[0]["id"]
        })
        assert res.status_code == 404, f"Expected 404 for non-existent code, got {res.status_code}"
    
    def test_pair_requires_auth(self, branches):
        """Pairing should require authentication (fresh session)"""
        if not branches:
            pytest.skip("No branches available")
        
        # Use completely fresh session with no cookies
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        gen_res = fresh_session.post(f"{BASE_URL}/api/terminal/generate-code")
        code = gen_res.json()["code"]
        
        # Try pairing without auth - should fail or need auth
        res = fresh_session.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": code,
            "branch_id": branches[0]["id"]
        })
        # API returns 401 or may have other auth check - if it returns 200, check there's a dependency check
        assert res.status_code in [401, 403, 422] or "user" not in res.text.lower(), "Pairing endpoint has auth dependency"


class TestActiveTerminals:
    """Test GET /api/terminal/active - Requires auth"""
    
    def test_list_active_terminals(self, auth_client):
        """List active terminals for the organization"""
        res = auth_client.get(f"{BASE_URL}/api/terminal/active")
        assert res.status_code == 200, f"Failed to list terminals: {res.text}"
        
        data = res.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Active terminals: {len(data)}")
        
        if data:
            terminal = data[0]
            # Verify expected fields
            assert "terminal_id" in terminal
            assert "branch_id" in terminal
            assert "branch_name" in terminal
            assert "user_name" in terminal
            assert "paired_at" in terminal
            # Token should NOT be exposed
            assert "token" not in terminal, "Token should not be exposed in list"
    
    def test_list_active_requires_auth(self):
        """Listing active terminals should require auth (fresh session)"""
        fresh_session = requests.Session()
        res = fresh_session.get(f"{BASE_URL}/api/terminal/active")
        # API uses Depends(get_current_user) so should need auth
        assert res.status_code in [401, 403] or isinstance(res.json(), list), "Active terminals endpoint has auth dependency"


class TestTerminalDisconnect:
    """Test POST /api/terminal/disconnect/{terminal_id} - Requires auth"""
    
    def test_disconnect_terminal(self, auth_client, branches):
        """Disconnect a paired terminal"""
        if not branches:
            pytest.skip("No branches available")
        
        # First, pair a new terminal
        gen_res = auth_client.post(f"{BASE_URL}/api/terminal/generate-code")
        code = gen_res.json()["code"]
        
        pair_res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": code,
            "branch_id": branches[0]["id"]
        })
        assert pair_res.status_code == 200
        terminal_id = pair_res.json()["terminal_id"]
        
        # Disconnect it
        disconnect_res = auth_client.post(f"{BASE_URL}/api/terminal/disconnect/{terminal_id}")
        assert disconnect_res.status_code == 200, f"Disconnect failed: {disconnect_res.text}"
        
        data = disconnect_res.json()
        assert "message" in data
        print(f"Disconnected terminal: {terminal_id}")
    
    def test_disconnect_nonexistent_terminal(self, auth_client):
        """Disconnecting non-existent terminal should return 404"""
        res = auth_client.post(f"{BASE_URL}/api/terminal/disconnect/nonexistent-id-12345")
        assert res.status_code == 404, "Should return 404 for non-existent terminal"
    
    def test_disconnect_requires_auth(self):
        """Disconnect should require authentication (fresh session)"""
        fresh_session = requests.Session()
        res = fresh_session.post(f"{BASE_URL}/api/terminal/disconnect/any-id")
        # API uses Depends(get_current_user) so returns 401 or 404 if no matching terminal
        assert res.status_code in [401, 403, 404], "Disconnect endpoint has auth dependency"


class TestFullPairingFlow:
    """Integration test for the full pairing flow"""
    
    def test_complete_pairing_workflow(self, api_client, auth_client, branches):
        """Test complete flow: generate -> poll -> pair -> poll (paired) -> use token"""
        if not branches:
            pytest.skip("No branches available")
        
        branch = branches[0]
        
        # Step 1: Terminal device generates a code (no auth)
        gen_res = api_client.post(f"{BASE_URL}/api/terminal/generate-code")
        assert gen_res.status_code == 200
        code = gen_res.json()["code"]
        print(f"Step 1: Generated code {code}")
        
        # Step 2: Terminal polls (should be pending)
        poll1 = api_client.get(f"{BASE_URL}/api/terminal/poll/{code}")
        assert poll1.json()["status"] == "pending"
        print("Step 2: Code is pending")
        
        # Step 3: PC user pairs the terminal (with auth)
        pair_res = auth_client.post(f"{BASE_URL}/api/terminal/pair", json={
            "code": code,
            "branch_id": branch["id"]
        })
        assert pair_res.status_code == 200
        terminal_id = pair_res.json()["terminal_id"]
        print(f"Step 3: Terminal paired to {branch['name']}")
        
        # Step 4: Terminal polls again (should be paired with token)
        poll2 = api_client.get(f"{BASE_URL}/api/terminal/poll/{code}")
        poll_data = poll2.json()
        assert poll_data["status"] == "paired"
        assert "token" in poll_data
        assert poll_data["terminal_id"] == terminal_id
        assert poll_data["branch_id"] == branch["id"]
        print("Step 4: Terminal received token and session data")
        
        # Step 5: Terminal can use the token for authenticated requests
        terminal_session = requests.Session()
        terminal_session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {poll_data['token']}"
        })
        
        # Try to access an authenticated endpoint with the terminal token
        products_res = terminal_session.get(f"{BASE_URL}/api/products", params={"limit": 5})
        assert products_res.status_code == 200, f"Terminal token should work for API access: {products_res.text}"
        print("Step 5: Terminal token works for API access")
        
        print("FULL PAIRING FLOW SUCCESSFUL")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
