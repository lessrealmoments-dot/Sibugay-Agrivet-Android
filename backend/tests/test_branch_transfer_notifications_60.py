"""
Test suite for Branch Transfer Notification Workflow (Iteration 60)
Tests:
- GET /incoming-requests endpoint
- POST /{po_id}/generate-branch-transfer endpoint  
- Notification types and navigation routes
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "sibugayagrivetsupply@gmail.com"
ADMIN_PASSWORD = "521325"


class TestIncomingRequestsEndpoint:
    """Test /api/purchase-orders/incoming-requests endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.user = data.get("user", {})
        
    def test_01_incoming_requests_returns_200(self):
        """Test that incoming-requests endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders/incoming-requests",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "requests" in data, "Response should contain 'requests' key"
        print(f"✓ Incoming requests endpoint returned {len(data.get('requests', []))} requests")
        
    def test_02_incoming_requests_structure(self):
        """Test the structure of incoming requests response"""
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders/incoming-requests",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        requests_list = data.get("requests", [])
        if requests_list:
            # Check first request structure
            req = requests_list[0]
            assert "id" in req, "Request should have 'id'"
            assert "po_number" in req, "Request should have 'po_number'"
            assert "po_type" in req, "Request should have 'po_type'"
            assert req["po_type"] == "branch_request", "po_type should be 'branch_request'"
            print(f"✓ Request structure validated: {req.get('po_number')}")
        else:
            pytest.skip("No incoming requests to validate structure")
            
    def test_03_incoming_requests_with_branch_filter(self):
        """Test incoming requests with branch_id filter"""
        # Get a branch_id first
        branches_response = requests.get(
            f"{BASE_URL}/api/branches",
            headers=self.headers
        )
        if branches_response.status_code == 200:
            branches = branches_response.json()
            if branches:
                branch_id = branches[0].get("id")
                response = requests.get(
                    f"{BASE_URL}/api/purchase-orders/incoming-requests",
                    headers=self.headers,
                    params={"branch_id": branch_id}
                )
                assert response.status_code == 200
                print(f"✓ Incoming requests with branch filter works")
        else:
            pytest.skip("Could not get branches")


class TestGenerateBranchTransferEndpoint:
    """Test /api/purchase-orders/{po_id}/generate-branch-transfer endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data.get("access_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_01_generate_transfer_from_valid_request(self):
        """Test generating a transfer from a valid branch request"""
        # First get a branch_request PO
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders/incoming-requests",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        requests_list = data.get("requests", [])
        
        # Find a request with status 'requested' or 'draft'
        valid_request = None
        for req in requests_list:
            if req.get("status") in ("requested", "draft"):
                valid_request = req
                break
                
        if not valid_request:
            pytest.skip("No valid branch request found to test")
            
        # Call generate-branch-transfer
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{valid_request['id']}/generate-branch-transfer",
            headers=self.headers
        )
        
        # Should return 200 with transfer data
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        transfer_data = response.json()
        assert "from_branch_id" in transfer_data, "Should have from_branch_id"
        assert "to_branch_id" in transfer_data, "Should have to_branch_id"
        assert "items" in transfer_data, "Should have items"
        
        if transfer_data.get("items"):
            item = transfer_data["items"][0]
            assert "product_id" in item, "Item should have product_id"
            assert "product_name" in item, "Item should have product_name"
            assert "qty" in item, "Item should have qty"
            assert "branch_capital" in item, "Item should have branch_capital"
            
        print(f"✓ Generated transfer data with {len(transfer_data.get('items', []))} items")
        
    def test_02_generate_transfer_invalid_po_type(self):
        """Test that non-branch_request POs return error"""
        # Get regular POs (not branch_request)
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders",
            headers=self.headers,
            params={"limit": 5}
        )
        
        if response.status_code != 200:
            pytest.skip("Could not get POs")
            
        data = response.json()
        pos = data.get("items", []) or data.get("orders", [])
        
        # Find a non-branch_request PO
        regular_po = None
        for po in pos:
            if po.get("po_type") != "branch_request":
                regular_po = po
                break
                
        if not regular_po:
            pytest.skip("No regular PO found to test")
            
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{regular_po['id']}/generate-branch-transfer",
            headers=self.headers
        )
        
        # Should return 400 error
        assert response.status_code == 400, f"Expected 400 for non-branch_request, got {response.status_code}"
        print("✓ Non-branch_request PO correctly rejected")
        
    def test_03_generate_transfer_not_found(self):
        """Test 404 for non-existent PO"""
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/nonexistent-po-id/generate-branch-transfer",
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent PO correctly returns 404")


class TestNotificationsEndpoint:
    """Test notifications endpoint for transfer-related types"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data.get("access_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_01_notifications_returns_200(self):
        """Test that notifications endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            headers=self.headers,
            params={"limit": 20}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "notifications" in data, "Response should have 'notifications'"
        print(f"✓ Found {len(data.get('notifications', []))} notifications")
        
    def test_02_notification_types_present(self):
        """Verify notification types are present"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            headers=self.headers,
            params={"limit": 50}
        )
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        types_found = set()
        
        for notif in notifications:
            types_found.add(notif.get("type", "unknown"))
            
        print(f"✓ Notification types found: {types_found}")
        
        # Check for expected transfer-related types
        transfer_types = {"branch_stock_request", "transfer_incoming", "transfer_variance_review", "transfer_accepted", "transfer_disputed"}
        found_transfer_types = types_found.intersection(transfer_types)
        
        if found_transfer_types:
            print(f"✓ Transfer-related notification types found: {found_transfer_types}")
        else:
            print("⚠ No transfer-related notifications currently in system")
            
    def test_03_notification_structure(self):
        """Verify notification structure has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            headers=self.headers,
            params={"limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        if notifications:
            notif = notifications[0]
            assert "id" in notif, "Notification should have 'id'"
            assert "type" in notif, "Notification should have 'type'"
            assert "message" in notif, "Notification should have 'message'"
            assert "created_at" in notif, "Notification should have 'created_at'"
            print(f"✓ Notification structure validated")
        else:
            pytest.skip("No notifications to validate")


class TestBranchTransfersEndpoint:
    """Test branch transfers endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data.get("access_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_01_branch_transfers_returns_200(self):
        """Test GET /api/branch-transfers endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/branch-transfers",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "orders" in data, "Response should have 'orders'"
        print(f"✓ Branch transfers endpoint returned {len(data.get('orders', []))} orders")
        
    def test_02_branch_transfers_with_branch_filter(self):
        """Test branch transfers with branch filter"""
        branches_response = requests.get(
            f"{BASE_URL}/api/branches",
            headers=self.headers
        )
        if branches_response.status_code != 200:
            pytest.skip("Could not get branches")
            
        branches = branches_response.json()
        if not branches:
            pytest.skip("No branches available")
            
        branch_id = branches[0].get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/branch-transfers",
            headers=self.headers,
            params={"branch_id": branch_id}
        )
        assert response.status_code == 200
        print(f"✓ Branch transfers with filter works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
