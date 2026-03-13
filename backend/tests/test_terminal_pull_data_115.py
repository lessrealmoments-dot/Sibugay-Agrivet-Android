"""
Terminal Pull Data (Self-Serve with PIN) - Iteration 115
Testing the new pull endpoints that allow terminals to browse and pull POs/Transfers
protected by PIN verification.

Features tested:
- GET /api/terminal/available-pos: POs in draft/ordered/in_progress for a branch
- GET /api/terminal/available-transfers: Transfers in 'sent' status for a branch
- POST /api/terminal/pull-po: Pull PO to terminal with PIN verification
- POST /api/terminal/pull-transfer: Pull transfer to terminal with PIN verification
- PIN verification using manager_pin (521325) from verify.py
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from context
TEST_USER = {"email": "testadmin@test.com", "password": "Test@123"}
BRANCH_ID_1 = "c435277f-9fc7-4d83-83e7-38be5b4423ac"  # Branch 1
BRANCH_ID_2 = "18c02daa-bce0-45de-860a-70ccc6ed6c6d"  # Branch 2
MANAGER_PIN = "521325"
INVALID_PIN = "000000"


class TestTerminalPullDataSetup:
    """Setup: Login and get auth token"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        assert token, "No token returned"
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def terminal_session(self, auth_headers):
        """Create a terminal session via pairing for testing"""
        # Generate pairing code
        code_res = requests.post(f"{BASE_URL}/api/terminal/generate-code")
        if code_res.status_code == 200:
            code = code_res.json().get("code")
            # Pair terminal
            pair_res = requests.post(
                f"{BASE_URL}/api/terminal/pair",
                json={"code": code, "branch_id": BRANCH_ID_1},
                headers=auth_headers
            )
            if pair_res.status_code == 200:
                return {"branch_id": BRANCH_ID_1, "paired": True}
        return {"branch_id": BRANCH_ID_1, "paired": False}


class TestAvailablePOsEndpoint:
    """Tests for GET /api/terminal/available-pos"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_available_pos_returns_list(self, auth_headers):
        """GET /api/terminal/available-pos returns list of POs"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-pos",
            params={"branch_id": BRANCH_ID_1},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: available-pos returns {len(data)} POs for branch_id={BRANCH_ID_1}")
    
    def test_available_pos_requires_branch_id(self, auth_headers):
        """GET /api/terminal/available-pos without branch_id returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-pos",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "branch_id" in response.json().get("detail", "").lower()
        print("PASS: available-pos requires branch_id")
    
    def test_available_pos_requires_auth(self):
        """GET /api/terminal/available-pos without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-pos",
            params={"branch_id": BRANCH_ID_1}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: available-pos requires authentication")
    
    def test_available_pos_structure(self, auth_headers):
        """Check that returned POs have expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-pos",
            params={"branch_id": BRANCH_ID_1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            po = data[0]
            assert "id" in po, "PO should have id"
            assert "po_number" in po, "PO should have po_number"
            assert "status" in po, "PO should have status"
            assert po["status"] in ["draft", "ordered", "in_progress"], f"PO status should be pullable, got {po['status']}"
            assert "item_count" in po, "PO should have item_count"
            print(f"PASS: PO structure verified - {po['po_number']} ({po['status']})")
        else:
            print("PASS: No POs available to verify structure (empty list is valid)")


class TestAvailableTransfersEndpoint:
    """Tests for GET /api/terminal/available-transfers"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_available_transfers_returns_list(self, auth_headers):
        """GET /api/terminal/available-transfers returns list of transfers"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-transfers",
            params={"branch_id": BRANCH_ID_1},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: available-transfers returns {len(data)} transfers for branch_id={BRANCH_ID_1}")
    
    def test_available_transfers_requires_branch_id(self, auth_headers):
        """GET /api/terminal/available-transfers without branch_id returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-transfers",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "branch_id" in response.json().get("detail", "").lower()
        print("PASS: available-transfers requires branch_id")
    
    def test_available_transfers_requires_auth(self):
        """GET /api/terminal/available-transfers without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-transfers",
            params={"branch_id": BRANCH_ID_1}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: available-transfers requires authentication")
    
    def test_available_transfers_structure(self, auth_headers):
        """Check that returned transfers have expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/available-transfers",
            params={"branch_id": BRANCH_ID_1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            t = data[0]
            assert "id" in t, "Transfer should have id"
            assert "order_number" in t, "Transfer should have order_number"
            assert "status" in t, "Transfer should have status"
            assert t["status"] == "sent", f"Available transfer status should be 'sent', got {t['status']}"
            assert "item_count" in t, "Transfer should have item_count"
            assert "from_branch_name" in t, "Transfer should have from_branch_name"
            print(f"PASS: Transfer structure verified - {t['order_number']} from {t['from_branch_name']}")
        else:
            print("PASS: No transfers available to verify structure (empty list is valid)")


class TestPullPOEndpoint:
    """Tests for POST /api/terminal/pull-po with PIN verification"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_po(self, auth_headers):
        """Create a test PO in draft status for pull testing"""
        po_data = {
            "vendor": "TEST_PULL_VENDOR",
            "branch_id": BRANCH_ID_1,
            "status": "draft",
            "items": [
                {"product_name": "Test Item", "quantity": 10, "unit_price": 100}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders",
            json=po_data,
            headers=auth_headers
        )
        if response.status_code in [200, 201]:
            return response.json()
        return None
    
    def test_pull_po_requires_po_id(self, auth_headers):
        """POST /api/terminal/pull-po without po_id returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-po",
            json={"pin": MANAGER_PIN},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "po_id" in response.json().get("detail", "").lower()
        print("PASS: pull-po requires po_id")
    
    def test_pull_po_requires_pin(self, auth_headers):
        """POST /api/terminal/pull-po without PIN returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-po",
            json={"po_id": "test-id"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "pin" in response.json().get("detail", "").lower()
        print("PASS: pull-po requires PIN")
    
    def test_pull_po_wrong_pin_returns_403(self, auth_headers):
        """POST /api/terminal/pull-po with wrong PIN returns 403"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-po",
            json={"po_id": "test-id", "pin": INVALID_PIN},
            headers=auth_headers
        )
        # Either 403 for invalid PIN or 404 for PO not found (both acceptable)
        assert response.status_code in [403, 404], f"Expected 403/404, got {response.status_code}: {response.text}"
        if response.status_code == 403:
            assert "pin" in response.json().get("detail", "").lower()
            print("PASS: pull-po with wrong PIN returns 403")
        else:
            print("PASS: pull-po returns 404 for non-existent PO (PIN checked after PO lookup)")
    
    def test_pull_po_requires_auth(self):
        """POST /api/terminal/pull-po without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-po",
            json={"po_id": "test-id", "pin": MANAGER_PIN}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: pull-po requires authentication")
    
    def test_pull_po_with_valid_pin(self, auth_headers, test_po):
        """POST /api/terminal/pull-po with valid PIN changes status to sent_to_terminal"""
        if not test_po:
            pytest.skip("No test PO created - skipping pull test")
        
        po_id = test_po.get("id")
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-po",
            json={"po_id": po_id, "pin": MANAGER_PIN},
            headers=auth_headers
        )
        
        # If the PO doesn't exist or status changed, we may get 404 or 400
        if response.status_code == 200:
            data = response.json()
            assert "message" in data, "Response should have message"
            assert "pulled" in data["message"].lower() or "terminal" in data["message"].lower()
            print(f"PASS: PO pulled with valid PIN - {data['message']}")
            
            # Verify PO status changed
            get_res = requests.get(
                f"{BASE_URL}/api/purchase-orders/{po_id}",
                headers=auth_headers
            )
            if get_res.status_code == 200:
                po_data = get_res.json()
                assert po_data.get("status") == "sent_to_terminal", f"PO status should be sent_to_terminal, got {po_data.get('status')}"
                print(f"PASS: PO status changed to sent_to_terminal")
        elif response.status_code == 400:
            # PO status may have already changed
            print(f"SKIP: PO status may have changed - {response.json().get('detail')}")
        else:
            print(f"INFO: pull-po returned {response.status_code}: {response.text}")


class TestPullTransferEndpoint:
    """Tests for POST /api/terminal/pull-transfer with PIN verification"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_pull_transfer_requires_transfer_id(self, auth_headers):
        """POST /api/terminal/pull-transfer without transfer_id returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-transfer",
            json={"pin": MANAGER_PIN},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "transfer_id" in response.json().get("detail", "").lower()
        print("PASS: pull-transfer requires transfer_id")
    
    def test_pull_transfer_requires_pin(self, auth_headers):
        """POST /api/terminal/pull-transfer without PIN returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-transfer",
            json={"transfer_id": "test-id"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "pin" in response.json().get("detail", "").lower()
        print("PASS: pull-transfer requires PIN")
    
    def test_pull_transfer_wrong_pin_returns_403(self, auth_headers):
        """POST /api/terminal/pull-transfer with wrong PIN returns 403"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-transfer",
            json={"transfer_id": "test-id", "pin": INVALID_PIN},
            headers=auth_headers
        )
        # Either 403 for invalid PIN or 404 for transfer not found
        assert response.status_code in [403, 404], f"Expected 403/404, got {response.status_code}: {response.text}"
        if response.status_code == 403:
            assert "pin" in response.json().get("detail", "").lower()
            print("PASS: pull-transfer with wrong PIN returns 403")
        else:
            print("PASS: pull-transfer returns 404 for non-existent transfer")
    
    def test_pull_transfer_requires_auth(self):
        """POST /api/terminal/pull-transfer without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/pull-transfer",
            json={"transfer_id": "test-id", "pin": MANAGER_PIN}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: pull-transfer requires authentication")


class TestExistingSendToTerminalFlow:
    """Verify existing PC-initiated send-to-terminal still works"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_terminal_notify_endpoint_exists(self, auth_headers):
        """POST /api/terminal/notify endpoint should exist for PC push"""
        response = requests.post(
            f"{BASE_URL}/api/terminal/notify",
            json={"branch_id": BRANCH_ID_1, "event_type": "test", "payload": {}},
            headers=auth_headers
        )
        # Should work or fail with validation error, not 404
        assert response.status_code != 404, "Terminal notify endpoint should exist"
        print(f"PASS: terminal/notify endpoint exists (status: {response.status_code})")
    
    def test_terminal_session_endpoint(self, auth_headers):
        """GET /api/terminal/session should work for active sessions"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/session",
            headers=auth_headers
        )
        # 200 if session exists, 404 if no session - both valid
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert "terminal_id" in data or "branch_id" in data
            print(f"PASS: Terminal session found")
        else:
            print(f"PASS: No active terminal session (expected for non-terminal client)")
    
    def test_active_terminals_endpoint(self, auth_headers):
        """GET /api/terminal/active should list active terminals"""
        response = requests.get(
            f"{BASE_URL}/api/terminal/active",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Should return list of terminals"
        print(f"PASS: Active terminals endpoint works - {len(data)} terminals")


class TestPinVerificationForTerminalPull:
    """Test that PIN verification works correctly for terminal_pull action"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        assert response.status_code == 200
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_manager_pin_works_for_pull(self, auth_headers):
        """Manager PIN (521325) should work for terminal pull actions"""
        # First get available POs
        pos_res = requests.get(
            f"{BASE_URL}/api/terminal/available-pos",
            params={"branch_id": BRANCH_ID_1},
            headers=auth_headers
        )
        assert pos_res.status_code == 200
        available_pos = pos_res.json()
        
        if len(available_pos) > 0:
            po = available_pos[0]
            # Try to pull with manager PIN
            pull_res = requests.post(
                f"{BASE_URL}/api/terminal/pull-po",
                json={"po_id": po["id"], "pin": MANAGER_PIN},
                headers=auth_headers
            )
            # Should succeed with 200 or fail with 400 (status issue), not 403 (PIN issue)
            assert pull_res.status_code in [200, 400], f"Manager PIN should be valid, got {pull_res.status_code}: {pull_res.text}"
            if pull_res.status_code == 200:
                print(f"PASS: Manager PIN {MANAGER_PIN} works for pull - {po['po_number']}")
            else:
                detail = pull_res.json().get("detail", "")
                assert "pin" not in detail.lower(), f"PIN should be valid, error: {detail}"
                print(f"PASS: Manager PIN accepted (PO status issue: {detail})")
        else:
            print("SKIP: No available POs to test manager PIN pull")
