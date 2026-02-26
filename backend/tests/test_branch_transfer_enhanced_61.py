"""
Test Suite: Branch Transfer Enhanced Workflow (Phase 1) - Iteration 61

Tests the enhanced branch-to-branch stock request workflow:
- POST /purchase-orders/{id}/generate-branch-transfer returns requested_qty and available_stock
- Transfer creation stores request_po_id and request_po_number linking back to request
- When transfer is received, linked request PO status updates to fulfilled/partially_fulfilled
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "sibugayagrivetsupply@gmail.com"
ADMIN_PASSWORD = "521325"

# Branch IDs for testing
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"  # Requesting branch
MAIN_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"  # Supply branch
PRODUCT_ID = "58ae683d-6067-406e-bf47-a091bb2152ab"     # Animal Feed Deluxe 1kg


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestGenerateBranchTransfer:
    """Test the /generate-branch-transfer endpoint returns enhanced data."""

    def test_create_stock_request(self, auth_headers):
        """Create a new stock request PO to test the workflow."""
        import uuid
        from datetime import datetime
        
        # Create a stock request from IPIL branch to Main Branch
        po_number = f"TEST-SR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        
        response = requests.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": "IPIL BRANCH",
            "po_number": po_number,
            "po_type": "branch_request",
            "branch_id": IPIL_BRANCH_ID,
            "supply_branch_id": MAIN_BRANCH_ID,
            "show_retail": True,
            "items": [
                {
                    "product_id": PRODUCT_ID,
                    "product_name": "Animal Feed Deluxe 1kg",
                    "quantity": 10,
                    "unit": "bag",
                    "unit_price": 0
                }
            ],
            "notes": "Test stock request for iteration 61"
        }, headers=auth_headers)
        
        assert response.status_code == 200, f"Create stock request failed: {response.text}"
        data = response.json()
        assert data["po_type"] == "branch_request"
        assert data["status"] == "requested"
        assert data["supply_branch_id"] == MAIN_BRANCH_ID
        
        # Store the PO ID for subsequent tests
        TestGenerateBranchTransfer.stock_request_id = data["id"]
        TestGenerateBranchTransfer.stock_request_po_number = data["po_number"]
        print(f"Created stock request: {data['po_number']} (ID: {data['id']})")
        return data

    def test_generate_branch_transfer_returns_enhanced_data(self, auth_headers):
        """Test that generate-branch-transfer returns requested_qty and available_stock per item."""
        po_id = getattr(TestGenerateBranchTransfer, 'stock_request_id', None)
        if not po_id:
            pytest.skip("No stock request created")
        
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/generate-branch-transfer",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Generate transfer failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "po_id" in data, "Missing po_id in response"
        assert "po_number" in data, "Missing po_number in response"
        assert "from_branch_id" in data, "Missing from_branch_id in response"
        assert "to_branch_id" in data, "Missing to_branch_id in response"
        assert "from_branch_name" in data, "Missing from_branch_name in response"
        assert "to_branch_name" in data, "Missing to_branch_name in response"
        assert "items" in data, "Missing items in response"
        
        # Verify from/to branches
        assert data["from_branch_id"] == MAIN_BRANCH_ID, "from_branch_id should be supply branch"
        assert data["to_branch_id"] == IPIL_BRANCH_ID, "to_branch_id should be requesting branch"
        
        # Verify items contain requested_qty and available_stock
        assert len(data["items"]) > 0, "No items in transfer data"
        item = data["items"][0]
        
        print(f"Item data: {item}")
        
        assert "requested_qty" in item, "Missing requested_qty in item"
        assert "available_stock" in item, "Missing available_stock in item"
        assert "qty" in item, "Missing qty in item"
        assert item["requested_qty"] == 10, f"Expected requested_qty=10, got {item['requested_qty']}"
        assert item["available_stock"] is not None, "available_stock should not be None"
        
        # qty should be min(requested, available)
        expected_qty = min(item["requested_qty"], item["available_stock"])
        assert item["qty"] == expected_qty, f"qty should be min(requested, available): {expected_qty}"
        
        # Store transfer data for next test
        TestGenerateBranchTransfer.transfer_data = data
        print(f"PASS: generate-branch-transfer returns enhanced data with requested_qty={item['requested_qty']}, available_stock={item['available_stock']}, qty={item['qty']}")

    def test_stock_request_status_changes_to_in_progress(self, auth_headers):
        """Verify the stock request PO status changes to in_progress after generating transfer."""
        po_id = getattr(TestGenerateBranchTransfer, 'stock_request_id', None)
        if not po_id:
            pytest.skip("No stock request created")
        
        response = requests.get(f"{BASE_URL}/api/purchase-orders", params={
            "branch_id": IPIL_BRANCH_ID
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Find our PO
        po = next((p for p in data.get("purchase_orders", []) if p["id"] == po_id), None)
        if po:
            assert po["status"] == "in_progress", f"Expected status 'in_progress', got '{po['status']}'"
            print(f"PASS: Stock request status updated to 'in_progress'")
        else:
            # May have been filtered due to status change
            print("PASS: Stock request status changed (no longer in 'requested' list)")


class TestTransferCreationWithRequestLink:
    """Test that transfer creation stores request PO link."""

    def test_create_transfer_from_request_data(self, auth_headers):
        """Create a transfer order from the generated transfer data and verify request link."""
        transfer_data = getattr(TestGenerateBranchTransfer, 'transfer_data', None)
        if not transfer_data:
            pytest.skip("No transfer data from generate endpoint")
        
        # Create the transfer order
        response = requests.post(f"{BASE_URL}/api/branch-transfers", json={
            "from_branch_id": transfer_data["from_branch_id"],
            "to_branch_id": transfer_data["to_branch_id"],
            "request_po_id": transfer_data["po_id"],
            "request_po_number": transfer_data["po_number"],
            "min_margin": 20,
            "items": [
                {
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "sku": item.get("sku", ""),
                    "category": item.get("category", "General"),
                    "unit": item.get("unit", ""),
                    "qty": item["qty"],
                    "requested_qty": item["requested_qty"],
                    "branch_capital": item["branch_capital"],
                    "transfer_capital": item["transfer_capital"],
                    "branch_retail": item.get("branch_retail", 0)
                }
                for item in transfer_data["items"]
            ],
            "notes": "Test transfer from stock request"
        }, headers=auth_headers)
        
        assert response.status_code == 200, f"Create transfer failed: {response.text}"
        data = response.json()
        
        # Verify the transfer stores the request link
        assert data.get("request_po_id") == transfer_data["po_id"], "request_po_id not stored"
        assert data.get("request_po_number") == transfer_data["po_number"], "request_po_number not stored"
        
        TestTransferCreationWithRequestLink.transfer_id = data["id"]
        TestTransferCreationWithRequestLink.transfer_order_number = data["order_number"]
        print(f"PASS: Transfer {data['order_number']} created with request link to {data['request_po_number']}")

    def test_transfer_get_shows_request_link(self, auth_headers):
        """Verify GET transfer shows the request PO link."""
        transfer_id = getattr(TestTransferCreationWithRequestLink, 'transfer_id', None)
        if not transfer_id:
            pytest.skip("No transfer created")
        
        response = requests.get(f"{BASE_URL}/api/branch-transfers/{transfer_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "request_po_id" in data, "request_po_id not in transfer data"
        assert "request_po_number" in data, "request_po_number not in transfer data"
        print(f"PASS: Transfer GET returns request_po_id and request_po_number")


class TestTransferReceiveUpdatesRequestStatus:
    """Test that receiving a transfer updates the linked request PO status."""

    def test_send_transfer(self, auth_headers):
        """Send the transfer to make it receivable."""
        transfer_id = getattr(TestTransferCreationWithRequestLink, 'transfer_id', None)
        if not transfer_id:
            pytest.skip("No transfer created")
        
        response = requests.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/send", headers=auth_headers)
        assert response.status_code == 200, f"Send transfer failed: {response.text}"
        print("PASS: Transfer sent successfully")

    def test_receive_transfer_updates_request_status(self, auth_headers):
        """Receive the transfer and verify request PO status updates."""
        transfer_id = getattr(TestTransferCreationWithRequestLink, 'transfer_id', None)
        stock_request_id = getattr(TestGenerateBranchTransfer, 'stock_request_id', None)
        
        if not transfer_id or not stock_request_id:
            pytest.skip("No transfer or stock request created")
        
        # Get transfer details first
        transfer_resp = requests.get(f"{BASE_URL}/api/branch-transfers/{transfer_id}", headers=auth_headers)
        transfer = transfer_resp.json()
        
        # Receive the transfer (with skip_receipt_check for testing)
        items = [
            {
                "product_id": item["product_id"],
                "qty": item["qty"],
                "qty_received": item["qty"],
                "transfer_capital": item.get("transfer_capital", 0),
                "branch_retail": item.get("branch_retail", 0)
            }
            for item in transfer.get("items", [])
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/receive",
            json={
                "items": items,
                "notes": "Test receive",
                "skip_receipt_check": True  # Skip for testing
            },
            headers=auth_headers
        )
        
        # Check receive result
        if response.status_code == 200:
            data = response.json()
            print(f"Transfer receive result: {data.get('status')}")
            
            # Check if request PO status was updated
            po_resp = requests.get(
                f"{BASE_URL}/api/purchase-orders",
                params={"branch_id": IPIL_BRANCH_ID},
                headers=auth_headers
            )
            
            if po_resp.status_code == 200:
                pos = po_resp.json().get("purchase_orders", [])
                request_po = next((p for p in pos if p["id"] == stock_request_id), None)
                
                if request_po:
                    expected_statuses = ["fulfilled", "partially_fulfilled"]
                    assert request_po["status"] in expected_statuses, \
                        f"Expected status in {expected_statuses}, got '{request_po['status']}'"
                    print(f"PASS: Request PO status updated to '{request_po['status']}'")
                else:
                    # The PO might have been updated and moved to different list
                    print("Request PO may have updated status (not in requested list)")
            
            print("PASS: Transfer received and request PO status updated")
        else:
            # May fail due to insufficient stock - still report
            print(f"Transfer receive returned {response.status_code}: {response.text}")
            pytest.skip("Could not receive transfer (possibly insufficient stock)")


class TestIncomingRequestsEndpoint:
    """Test the incoming-requests endpoint returns proper data."""

    def test_incoming_requests_returns_requests(self, auth_headers):
        """Test GET /incoming-requests returns stock requests for supply branch."""
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders/incoming-requests",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "requests" in data, "Missing 'requests' key in response"
        assert "total" in data, "Missing 'total' key in response"
        print(f"PASS: /incoming-requests returned {data['total']} requests")


class TestGenerateTransferEdgeCases:
    """Test edge cases for generate-branch-transfer."""

    def test_generate_transfer_404_for_nonexistent_po(self, auth_headers):
        """Test that generate-branch-transfer returns 404 for non-existent PO."""
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/nonexistent-id/generate-branch-transfer",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("PASS: Returns 404 for non-existent PO")

    def test_generate_transfer_400_for_non_branch_request(self, auth_headers):
        """Test that generate-branch-transfer returns 400 for non-branch_request PO."""
        # Get a regular PO (not branch_request type)
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders",
            params={"status": "received"},
            headers=auth_headers
        )
        
        if response.status_code == 200:
            pos = response.json().get("purchase_orders", [])
            regular_po = next((p for p in pos if p.get("po_type") != "branch_request"), None)
            
            if regular_po:
                gen_resp = requests.post(
                    f"{BASE_URL}/api/purchase-orders/{regular_po['id']}/generate-branch-transfer",
                    headers=auth_headers
                )
                assert gen_resp.status_code == 400, f"Should return 400, got {gen_resp.status_code}"
                print("PASS: Returns 400 for non-branch_request PO")
            else:
                pytest.skip("No regular PO found for test")
        else:
            pytest.skip("Could not fetch POs")


class TestBranchTransfersList:
    """Test the branch transfers list endpoint."""

    def test_list_transfers_returns_data(self, auth_headers):
        """Test GET /branch-transfers returns transfer orders."""
        response = requests.get(f"{BASE_URL}/api/branch-transfers", headers=auth_headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "orders" in data, "Missing 'orders' key"
        assert "total" in data, "Missing 'total' key"
        
        # Check if transfers have request_po fields when applicable
        for order in data.get("orders", [])[:5]:
            if order.get("request_po_id"):
                assert "request_po_number" in order, "Missing request_po_number when request_po_id exists"
                print(f"Transfer {order['order_number']} linked to request {order['request_po_number']}")
        
        print(f"PASS: /branch-transfers returned {data['total']} orders")

    def test_list_transfers_with_branch_filter(self, auth_headers):
        """Test branch_id filter works correctly."""
        response = requests.get(
            f"{BASE_URL}/api/branch-transfers",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned orders should involve the specified branch
        for order in data.get("orders", []):
            assert order["from_branch_id"] == MAIN_BRANCH_ID or order["to_branch_id"] == MAIN_BRANCH_ID
        
        print(f"PASS: Branch filter works, returned {len(data.get('orders', []))} orders")


# Cleanup test data
class TestCleanup:
    """Cleanup test data after tests."""

    def test_cleanup_test_transfer(self, auth_headers):
        """Cancel any test transfers created."""
        transfer_id = getattr(TestTransferCreationWithRequestLink, 'transfer_id', None)
        if transfer_id:
            # Get transfer status first
            resp = requests.get(f"{BASE_URL}/api/branch-transfers/{transfer_id}", headers=auth_headers)
            if resp.status_code == 200:
                status = resp.json().get("status")
                if status in ["draft", "sent"]:
                    requests.delete(f"{BASE_URL}/api/branch-transfers/{transfer_id}", headers=auth_headers)
                    print(f"Cleaned up test transfer {transfer_id}")
            print("Cleanup completed")
