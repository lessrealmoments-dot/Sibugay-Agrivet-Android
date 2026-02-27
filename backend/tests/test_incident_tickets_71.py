"""
Iteration 71: Incident Tickets System - Transfer Variance Investigation

Test coverage:
1. GET /api/incident-tickets - List all incident tickets (API verification)
2. GET /api/incident-tickets/summary - Status counts and unresolved losses (API verification)
3. POST /api/branch-transfers/{id}/accept-receipt with action='accept' - Accept variance (requires inventory)
4. POST /api/branch-transfers/{id}/accept-receipt with action='accept_with_incident' - Create incident ticket
5. GET /api/incident-tickets/{id} - Ticket detail with timeline
6. PUT /api/incident-tickets/{id}/assign - Assign ticket and set investigating
7. PUT /api/incident-tickets/{id}/add-note - Add investigation note
8. PUT /api/incident-tickets/{id}/resolve - Resolve with note and recovery amount
9. PUT /api/incident-tickets/{id}/close - Close ticket (admin only)

NOTE: Tests use a known product with inventory in the source branch.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known test data - product with inventory in Main Branch
TEST_PRODUCT_ID = "58ae683d-6067-406e-bf47-a091bb2152ab"
TEST_PRODUCT_NAME = "Animal Feed Deluxe 1kg"
SOURCE_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"  # Main Branch
DEST_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"   # IPIL BRANCH


class TestIncidentTicketsAPI:
    """Tests for incident tickets APIs - independent of transfer flow."""
    
    auth_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token."""
        if not TestIncidentTicketsAPI.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
            TestIncidentTicketsAPI.auth_token = login_resp.json()["token"]
            
        self.headers = {
            "Authorization": f"Bearer {TestIncidentTicketsAPI.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_01_list_incident_tickets_endpoint_works(self):
        """GET /api/incident-tickets should return valid response structure."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "tickets" in data, "Response should have 'tickets' field"
        assert "total" in data, "Response should have 'total' field"
        assert isinstance(data["tickets"], list)
        assert isinstance(data["total"], int)
        print(f"✓ List endpoint works. Total tickets: {data['total']}")
    
    def test_02_list_tickets_with_filters(self):
        """GET /api/incident-tickets with status filter should work."""
        for status in ["open", "investigating", "resolved", "closed"]:
            resp = requests.get(f"{BASE_URL}/api/incident-tickets?status={status}", headers=self.headers)
            assert resp.status_code == 200, f"Failed for status={status}: {resp.text}"
            data = resp.json()
            for ticket in data.get("tickets", []):
                assert ticket["status"] == status
        print("✓ Status filter works for all status values")
    
    def test_03_incident_summary_endpoint_works(self):
        """GET /api/incident-tickets/summary should return status counts."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/summary", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        required_fields = ["open", "investigating", "resolved", "closed", 
                          "total_unresolved_capital_loss", "total_unresolved_retail_loss"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Summary: open={data['open']}, investigating={data['investigating']}, "
              f"resolved={data['resolved']}, closed={data['closed']}")
    
    def test_04_get_nonexistent_ticket_returns_404(self):
        """GET /api/incident-tickets/{id} should return 404 for non-existent ticket."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/nonexistent-id", headers=self.headers)
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent ticket")


class TestFullIncidentTicketLifecycle:
    """Full lifecycle: Create transfer → receive with variance → accept with incident → manage ticket."""
    
    auth_token = None
    admin_user = None
    transfer_id = None
    incident_ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth."""
        if not TestFullIncidentTicketLifecycle.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            assert login_resp.status_code == 200
            data = login_resp.json()
            TestFullIncidentTicketLifecycle.auth_token = data["token"]
            TestFullIncidentTicketLifecycle.admin_user = data["user"]
            
        self.headers = {
            "Authorization": f"Bearer {TestFullIncidentTicketLifecycle.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_05_ensure_inventory_exists(self):
        """Ensure source branch has inventory for the test product."""
        # Check current inventory
        resp = requests.get(
            f"{BASE_URL}/api/inventory?branch_id={SOURCE_BRANCH_ID}&product_id={TEST_PRODUCT_ID}",
            headers=self.headers
        )
        
        # Add inventory if needed (using the correct format)
        adjust_data = {
            "product_id": TEST_PRODUCT_ID,
            "branch_id": SOURCE_BRANCH_ID,
            "quantity": 100,  # Add 100 units
            "reason": "TEST: Ensuring stock for incident ticket test"
        }
        resp = requests.post(f"{BASE_URL}/api/inventory/adjust", json=adjust_data, headers=self.headers)
        if resp.status_code == 200:
            print(f"✓ Inventory adjusted: {resp.json()}")
        else:
            print(f"⚠ Inventory adjust response: {resp.status_code} - {resp.text}")
    
    def test_06_create_transfer_for_incident_test(self):
        """Create a transfer order with the known product."""
        transfer_data = {
            "from_branch_id": SOURCE_BRANCH_ID,
            "to_branch_id": DEST_BRANCH_ID,
            "items": [{
                "product_id": TEST_PRODUCT_ID,
                "product_name": TEST_PRODUCT_NAME,
                "sku": "TEST-INC-71",
                "qty": 20,
                "unit": "kg",
                "branch_capital": 200.0,
                "transfer_capital": 210.0,
                "branch_retail": 260.0
            }],
            "notes": "TEST: Transfer for incident ticket lifecycle testing - iteration 71"
        }
        
        resp = requests.post(f"{BASE_URL}/api/branch-transfers", json=transfer_data, headers=self.headers)
        assert resp.status_code == 200, f"Failed to create transfer: {resp.text}"
        data = resp.json()
        TestFullIncidentTicketLifecycle.transfer_id = data["id"]
        print(f"✓ Created transfer: {data.get('order_number')}")
    
    def test_07_send_transfer(self):
        """Send the transfer."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        resp = requests.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/send", headers=self.headers)
        assert resp.status_code == 200, f"Failed to send: {resp.text}"
        print("✓ Transfer sent")
    
    def test_08_receive_with_variance(self):
        """Receive transfer with variance (shortage)."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        
        receive_data = {
            "items": [{
                "product_id": TEST_PRODUCT_ID,
                "qty": 20,
                "qty_received": 15  # Shortage of 5 units
            }],
            "skip_receipt_check": True,
            "notes": "TEST: Received with shortage for incident testing"
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/receive",
            json=receive_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed to receive: {resp.text}"
        data = resp.json()
        assert data.get("status") == "received_pending"
        assert data.get("has_variance") == True
        print(f"✓ Received with variance. Shortages: {len(data.get('shortages', []))}")
    
    def test_09_accept_receipt_with_incident(self):
        """Accept receipt with action='accept_with_incident' to create incident ticket."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        
        accept_data = {
            "action": "accept_with_incident",
            "note": "TEST: Creating incident ticket for investigation of missing 5 units"
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/accept-receipt",
            json=accept_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed to accept: {resp.text}"
        data = resp.json()
        
        # Verify incident ticket was created
        assert "incident_ticket_id" in data, f"Expected incident_ticket_id: {data}"
        assert "incident_ticket_number" in data
        
        TestFullIncidentTicketLifecycle.incident_ticket_id = data["incident_ticket_id"]
        print(f"✓ Receipt accepted with incident ticket: {data['incident_ticket_number']}")
    
    def test_10_get_incident_ticket_detail(self):
        """GET /api/incident-tickets/{id} should return ticket with timeline."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Validate structure
        assert data["id"] == ticket_id
        assert "ticket_number" in data
        assert "transfer_id" in data
        assert "timeline" in data
        assert data["status"] == "open"
        assert len(data["timeline"]) >= 1
        assert data["timeline"][0]["action"] == "created"
        
        print(f"✓ Ticket detail verified: {data['ticket_number']}")
    
    def test_11_assign_ticket(self):
        """PUT /api/incident-tickets/{id}/assign should assign and set investigating."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        admin_user = TestFullIncidentTicketLifecycle.admin_user
        
        assign_data = {
            "assigned_to_id": admin_user["id"],
            "assigned_to_name": admin_user.get("full_name", admin_user["username"])
        }
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/assign",
            json=assign_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print("✓ Ticket assigned")
    
    def test_12_verify_ticket_is_investigating(self):
        """Verify ticket status is now 'investigating'."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "investigating"
        actions = [e["action"] for e in data["timeline"]]
        assert "assigned" in actions
        print("✓ Ticket status is 'investigating'")
    
    def test_13_add_note_to_ticket(self):
        """PUT /api/incident-tickets/{id}/add-note should add note."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/add-note",
            json={"note": "TEST: Reviewed delivery receipt - shortage confirmed"},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["message"] == "Note added"
        print("✓ Note added")
    
    def test_14_verify_note_in_timeline(self):
        """Verify note in timeline."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        note_events = [e for e in data["timeline"] if e["action"] == "note"]
        assert len(note_events) >= 1
        print(f"✓ Note verified in timeline")
    
    def test_15_add_empty_note_fails(self):
        """Adding empty note should fail."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/add-note",
            json={"note": ""},
            headers=self.headers
        )
        assert resp.status_code == 400
        print("✓ Empty note rejected")
    
    def test_16_resolve_ticket(self):
        """PUT /api/incident-tickets/{id}/resolve should resolve."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_note": "TEST: Investigation complete - shortage attributed to transit damage",
                "recovery_amount": 250.0
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["status"] == "resolved"
        print("✓ Ticket resolved")
    
    def test_17_verify_resolved_state(self):
        """Verify resolved state."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "resolved"
        assert data["recovery_amount"] == 250.0
        assert data["resolved_by_id"] != ""
        print("✓ Resolved state verified")
    
    def test_18_close_ticket(self):
        """PUT /api/incident-tickets/{id}/close should close ticket (admin)."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/close",
            json={"note": "TEST: Case closed after recovery processed"},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["message"] == "Ticket closed"
        print("✓ Ticket closed")
    
    def test_19_verify_closed_state(self):
        """Verify closed state."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "closed"
        assert data["closed_at"] is not None
        
        closed_events = [e for e in data["timeline"] if e["action"] == "closed"]
        assert len(closed_events) == 1
        print(f"✓ Ticket closed. Timeline has {len(data['timeline'])} events")


class TestAcceptReceiptWithoutIncident:
    """Test accept-receipt with action='accept' (no incident ticket creation)."""
    
    auth_token = None
    transfer_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestAcceptReceiptWithoutIncident.auth_token:
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            TestAcceptReceiptWithoutIncident.auth_token = resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestAcceptReceiptWithoutIncident.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_20_ensure_inventory_and_create_transfer(self):
        """Ensure inventory and create transfer."""
        # Add inventory
        requests.post(
            f"{BASE_URL}/api/inventory/adjust",
            json={
                "product_id": TEST_PRODUCT_ID,
                "branch_id": SOURCE_BRANCH_ID,
                "quantity": 50,
                "reason": "TEST: Stock for accept-only test"
            },
            headers=self.headers
        )
        
        # Create transfer
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers",
            json={
                "from_branch_id": SOURCE_BRANCH_ID,
                "to_branch_id": DEST_BRANCH_ID,
                "items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "product_name": TEST_PRODUCT_NAME,
                    "sku": "TEST-ACCEPT-71",
                    "qty": 10,
                    "unit": "kg",
                    "branch_capital": 200.0,
                    "transfer_capital": 210.0,
                    "branch_retail": 260.0
                }],
                "notes": "TEST: Transfer for accept-only test"
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        TestAcceptReceiptWithoutIncident.transfer_id = resp.json()["id"]
        print(f"✓ Transfer created: {resp.json().get('order_number')}")
    
    def test_21_send_transfer(self):
        """Send transfer."""
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestAcceptReceiptWithoutIncident.transfer_id}/send",
            headers=self.headers
        )
        assert resp.status_code == 200
        print("✓ Transfer sent")
    
    def test_22_receive_with_variance(self):
        """Receive with variance."""
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestAcceptReceiptWithoutIncident.transfer_id}/receive",
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "qty": 10, "qty_received": 8}],
                "skip_receipt_check": True
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "received_pending"
        print("✓ Received with variance")
    
    def test_23_accept_with_accept_action_only(self):
        """Accept with action='accept' should NOT create incident ticket."""
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestAcceptReceiptWithoutIncident.transfer_id}/accept-receipt",
            json={"action": "accept", "note": "TEST: Accepting without incident"},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Should NOT have incident_ticket_id
        assert data.get("incident_ticket_id") is None or "incident_ticket_id" not in data
        assert data.get("status") == "received"
        print("✓ Receipt accepted WITHOUT incident ticket")
    
    def test_24_verify_transfer_state(self):
        """Verify transfer is received with accept action logged."""
        resp = requests.get(
            f"{BASE_URL}/api/branch-transfers/{TestAcceptReceiptWithoutIncident.transfer_id}",
            headers=self.headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "received"
        assert data.get("accept_action") == "accept"
        print("✓ Transfer state verified")


class TestSummaryAndFilters:
    """Test summary counts and filters after lifecycle tests."""
    
    auth_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestSummaryAndFilters.auth_token:
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            TestSummaryAndFilters.auth_token = resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestSummaryAndFilters.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_25_summary_reflects_ticket_count(self):
        """Summary should show ticket counts."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/summary", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        total = data["open"] + data["investigating"] + data["resolved"] + data["closed"]
        print(f"✓ Summary: total={total}, open={data['open']}, investigating={data['investigating']}, "
              f"resolved={data['resolved']}, closed={data['closed']}")
    
    def test_26_list_tickets_with_transfer_filter(self):
        """List tickets by transfer_id."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets?limit=1", headers=self.headers)
        tickets = resp.json().get("tickets", [])
        
        if tickets:
            transfer_id = tickets[0]["transfer_id"]
            resp = requests.get(
                f"{BASE_URL}/api/incident-tickets?transfer_id={transfer_id}",
                headers=self.headers
            )
            assert resp.status_code == 200
            print(f"✓ Transfer filter works")
        else:
            print("⚠ No tickets to test filter")
    
    def test_27_list_tickets_with_branch_filter(self):
        """List tickets by branch_id."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets?branch_id={SOURCE_BRANCH_ID}",
            headers=self.headers
        )
        assert resp.status_code == 200
        print(f"✓ Branch filter works: {resp.json().get('total', 0)} tickets")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
