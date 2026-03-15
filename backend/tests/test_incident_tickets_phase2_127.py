"""
Iteration 127: Phase 2 Incident Tickets - Structured Variance Resolution Workflow

Test coverage for Phase 2 features:
1. GET /api/incident-tickets/resolution-types - Returns 6 resolution types
2. PUT /api/incident-tickets/{id}/resolve - With resolution_type, accountable_party, recovery_amount
3. PUT /api/incident-tickets/{id}/sender-confirm - Sender confirmation flow with auto-resolve
4. Validation: resolution_type required, accountable_party for certain types
5. Data persistence verification

Resolution Types:
- transit_loss, sender_error, receiver_error, write_off, insurance_claim, partial_recovery
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known test data
TEST_PRODUCT_ID = "58ae683d-6067-406e-bf47-a091bb2152ab"
TEST_PRODUCT_NAME = "Animal Feed Deluxe 1kg"
SOURCE_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"  # Main Branch
DEST_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"   # IPIL BRANCH


class TestResolutionTypesEndpoint:
    """Test GET /api/incident-tickets/resolution-types endpoint."""
    
    auth_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestResolutionTypesEndpoint.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
            TestResolutionTypesEndpoint.auth_token = login_resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestResolutionTypesEndpoint.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_01_resolution_types_endpoint_returns_6_types(self):
        """GET /api/incident-tickets/resolution-types should return 6 types."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/resolution-types", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 6, f"Expected 6 types, got {len(data)}"
        
        expected_types = {"transit_loss", "sender_error", "receiver_error", 
                         "write_off", "insurance_claim", "partial_recovery"}
        actual_types = {item["value"] for item in data}
        assert actual_types == expected_types, f"Mismatch. Got: {actual_types}"
        
        # Verify each item has value and label
        for item in data:
            assert "value" in item, "Each type should have 'value'"
            assert "label" in item, "Each type should have 'label'"
            assert len(item["label"]) > 0, "Label should not be empty"
        
        print(f"✓ Resolution types endpoint returns 6 types: {actual_types}")


class TestResolveWithResolutionType:
    """Test resolve endpoint with Phase 2 resolution_type field."""
    
    auth_token = None
    admin_user = None
    transfer_id = None
    incident_ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestResolveWithResolutionType.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200
            data = login_resp.json()
            TestResolveWithResolutionType.auth_token = data["token"]
            TestResolveWithResolutionType.admin_user = data["user"]
        self.headers = {
            "Authorization": f"Bearer {TestResolveWithResolutionType.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_02_setup_transfer_with_variance(self):
        """Create and receive a transfer with variance to create incident ticket."""
        # Ensure inventory
        requests.post(
            f"{BASE_URL}/api/inventory/adjust",
            json={
                "product_id": TEST_PRODUCT_ID,
                "branch_id": SOURCE_BRANCH_ID,
                "quantity": 100,
                "reason": "TEST: Phase 2 resolution type testing"
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
                    "sku": "TEST-P2-127",
                    "qty": 15,
                    "unit": "kg",
                    "branch_capital": 200.0,
                    "transfer_capital": 210.0,
                    "branch_retail": 260.0
                }],
                "notes": "TEST: Phase 2 resolution type test transfer"
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed to create transfer: {resp.text}"
        TestResolveWithResolutionType.transfer_id = resp.json()["id"]
        print(f"✓ Transfer created: {resp.json().get('order_number')}")
    
    def test_03_send_and_receive_with_variance(self):
        """Send and receive transfer with shortage."""
        transfer_id = TestResolveWithResolutionType.transfer_id
        
        # Send
        resp = requests.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/send", headers=self.headers)
        assert resp.status_code == 200, f"Failed to send: {resp.text}"
        
        # Receive with shortage
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/receive",
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "qty": 15, "qty_received": 10}],  # 5 unit shortage
                "skip_receipt_check": True
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed to receive: {resp.text}"
        print("✓ Transfer received with variance")
    
    def test_04_create_incident_ticket(self):
        """Accept with incident ticket."""
        transfer_id = TestResolveWithResolutionType.transfer_id
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/accept-receipt",
            json={"action": "accept_with_incident", "note": "TEST: Phase 2 resolution test"},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "incident_ticket_id" in data
        TestResolveWithResolutionType.incident_ticket_id = data["incident_ticket_id"]
        print(f"✓ Incident ticket created: {data['incident_ticket_number']}")
    
    def test_05_resolve_with_transit_loss_type(self):
        """Resolve ticket with transit_loss resolution type and accountable party."""
        ticket_id = TestResolveWithResolutionType.incident_ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "transit_loss",
                "resolution_note": "TEST: 5 units lost in transit, driver acknowledges",
                "accountable_party": "Driver Juan Cruz",
                "recovery_amount": 500.0
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["status"] == "resolved"
        assert "transit_loss" in data.get("message", "")
        print("✓ Ticket resolved with transit_loss type")
    
    def test_06_verify_resolution_data_persisted(self):
        """Verify resolution_type, accountable_party, and recovery_amount are persisted."""
        ticket_id = TestResolveWithResolutionType.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "resolved"
        assert data["resolution_type"] == "transit_loss", f"Got: {data.get('resolution_type')}"
        assert data["accountable_party"] == "Driver Juan Cruz", f"Got: {data.get('accountable_party')}"
        assert data["recovery_amount"] == 500.0, f"Got: {data.get('recovery_amount')}"
        assert "transit" in data["resolution_note"].lower()
        
        # Check timeline has resolution_type
        resolved_events = [e for e in data["timeline"] if e["action"] == "resolved"]
        assert len(resolved_events) >= 1
        assert resolved_events[0].get("resolution_type") == "transit_loss"
        
        print("✓ Resolution data verified: transit_loss, Driver Juan Cruz, PHP 500")


class TestResolveValidation:
    """Test validation for resolve endpoint."""
    
    auth_token = None
    transfer_id = None
    ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestResolveValidation.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200
            TestResolveValidation.auth_token = login_resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestResolveValidation.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_07_setup_ticket_for_validation_tests(self):
        """Create a new ticket for validation testing."""
        # Ensure inventory
        requests.post(
            f"{BASE_URL}/api/inventory/adjust",
            json={
                "product_id": TEST_PRODUCT_ID,
                "branch_id": SOURCE_BRANCH_ID,
                "quantity": 100,
                "reason": "TEST: Validation tests"
            },
            headers=self.headers
        )
        
        # Create, send, receive, create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers",
            json={
                "from_branch_id": SOURCE_BRANCH_ID,
                "to_branch_id": DEST_BRANCH_ID,
                "items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "product_name": TEST_PRODUCT_NAME,
                    "sku": "TEST-VAL-127",
                    "qty": 10,
                    "unit": "kg",
                    "branch_capital": 200.0,
                    "transfer_capital": 210.0,
                    "branch_retail": 260.0
                }],
                "notes": "TEST: Validation tests"
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        TestResolveValidation.transfer_id = resp.json()["id"]
        
        # Send
        requests.post(f"{BASE_URL}/api/branch-transfers/{TestResolveValidation.transfer_id}/send", headers=self.headers)
        
        # Receive with variance
        requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestResolveValidation.transfer_id}/receive",
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "qty": 10, "qty_received": 7}],
                "skip_receipt_check": True
            },
            headers=self.headers
        )
        
        # Create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestResolveValidation.transfer_id}/accept-receipt",
            json={"action": "accept_with_incident", "note": "TEST: Validation"},
            headers=self.headers
        )
        assert resp.status_code == 200
        TestResolveValidation.ticket_id = resp.json()["incident_ticket_id"]
        print(f"✓ Setup complete. Ticket: {resp.json()['incident_ticket_number']}")
    
    def test_08_resolve_without_note_fails(self):
        """Resolve without resolution_note should fail."""
        ticket_id = TestResolveValidation.ticket_id
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={"resolution_type": "write_off"},  # No note
            headers=self.headers
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "note" in resp.json().get("detail", "").lower()
        print("✓ Resolution without note rejected (400)")
    
    def test_09_resolve_with_invalid_type_fails(self):
        """Resolve with invalid resolution_type should fail."""
        ticket_id = TestResolveValidation.ticket_id
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={"resolution_type": "invalid_type", "resolution_note": "Test note"},
            headers=self.headers
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "invalid" in resp.json().get("detail", "").lower()
        print("✓ Invalid resolution_type rejected (400)")
    
    def test_10_resolve_with_sender_error_no_accountable_party_ok(self):
        """Resolve with sender_error should work without accountable_party."""
        ticket_id = TestResolveValidation.ticket_id
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "sender_error",
                "resolution_note": "Sender miscounted, no actual loss"
                # No accountable_party - should be fine for sender_error
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        print("✓ sender_error resolution works without accountable_party")


class TestSenderConfirmFlow:
    """Test sender confirmation flow with auto-resolve."""
    
    auth_token = None
    transfer_id = None
    ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestSenderConfirmFlow.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200
            TestSenderConfirmFlow.auth_token = login_resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestSenderConfirmFlow.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_11_setup_ticket_for_sender_confirm(self):
        """Create ticket for sender confirmation test."""
        # Ensure inventory
        requests.post(
            f"{BASE_URL}/api/inventory/adjust",
            json={
                "product_id": TEST_PRODUCT_ID,
                "branch_id": SOURCE_BRANCH_ID,
                "quantity": 100,
                "reason": "TEST: Sender confirm test"
            },
            headers=self.headers
        )
        
        # Create, send, receive with variance, create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers",
            json={
                "from_branch_id": SOURCE_BRANCH_ID,
                "to_branch_id": DEST_BRANCH_ID,
                "items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "product_name": TEST_PRODUCT_NAME,
                    "sku": "TEST-SC-127",
                    "qty": 20,
                    "unit": "kg",
                    "branch_capital": 200.0,
                    "transfer_capital": 210.0,
                    "branch_retail": 260.0
                }],
                "notes": "TEST: Sender confirm test"
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        TestSenderConfirmFlow.transfer_id = resp.json()["id"]
        
        # Send
        requests.post(f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmFlow.transfer_id}/send", headers=self.headers)
        
        # Receive with variance (15 received instead of 20)
        requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmFlow.transfer_id}/receive",
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "qty": 20, "qty_received": 15}],
                "skip_receipt_check": True
            },
            headers=self.headers
        )
        
        # Create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmFlow.transfer_id}/accept-receipt",
            json={"action": "accept_with_incident", "note": "TEST: Sender confirm"},
            headers=self.headers
        )
        assert resp.status_code == 200
        TestSenderConfirmFlow.ticket_id = resp.json()["incident_ticket_id"]
        print(f"✓ Ticket created: {resp.json()['incident_ticket_number']}")
    
    def test_12_sender_confirm_with_matching_qty_auto_resolves(self):
        """Sender confirm with qty matching receiver should auto-resolve as sender_error."""
        ticket_id = TestSenderConfirmFlow.ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/sender-confirm",
            json={
                "confirmed_items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "sender_confirmed_qty": 15  # Matches receiver qty
                }],
                "note": "Warehouse confirms only 15 were packed"
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("auto_resolved") == True, f"Expected auto_resolved=True: {data}"
        assert "cancelled" in data.get("message", "").lower() or "no actual loss" in data.get("message", "").lower()
        print("✓ Sender confirm auto-resolved ticket (sender_error)")
    
    def test_13_verify_auto_resolved_ticket(self):
        """Verify ticket was auto-resolved with sender_error type."""
        ticket_id = TestSenderConfirmFlow.ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "resolved"
        assert data["resolution_type"] == "sender_error"
        assert data["sender_confirmed"] == True
        assert "sender_confirmed_qty" in str(data.get("items", []))
        
        # Check timeline
        sc_events = [e for e in data["timeline"] if e["action"] == "sender_confirmed"]
        assert len(sc_events) >= 1
        assert sc_events[0].get("variance_cancelled") == True
        
        print("✓ Ticket verified: auto-resolved as sender_error")


class TestSenderConfirmNoAutoResolve:
    """Test sender confirm when quantities don't match (no auto-resolve)."""
    
    auth_token = None
    transfer_id = None
    ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestSenderConfirmNoAutoResolve.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200
            TestSenderConfirmNoAutoResolve.auth_token = login_resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestSenderConfirmNoAutoResolve.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_14_setup_ticket(self):
        """Create ticket for no-auto-resolve test."""
        # Ensure inventory
        requests.post(
            f"{BASE_URL}/api/inventory/adjust",
            json={
                "product_id": TEST_PRODUCT_ID,
                "branch_id": SOURCE_BRANCH_ID,
                "quantity": 100,
                "reason": "TEST: No auto-resolve test"
            },
            headers=self.headers
        )
        
        # Create, send, receive with variance, create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers",
            json={
                "from_branch_id": SOURCE_BRANCH_ID,
                "to_branch_id": DEST_BRANCH_ID,
                "items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "product_name": TEST_PRODUCT_NAME,
                    "sku": "TEST-NAR-127",
                    "qty": 25,
                    "unit": "kg",
                    "branch_capital": 200.0,
                    "transfer_capital": 210.0,
                    "branch_retail": 260.0
                }],
                "notes": "TEST: No auto-resolve test"
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        TestSenderConfirmNoAutoResolve.transfer_id = resp.json()["id"]
        
        # Send
        requests.post(f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmNoAutoResolve.transfer_id}/send", headers=self.headers)
        
        # Receive with variance (20 received instead of 25)
        requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmNoAutoResolve.transfer_id}/receive",
            json={
                "items": [{"product_id": TEST_PRODUCT_ID, "qty": 25, "qty_received": 20}],
                "skip_receipt_check": True
            },
            headers=self.headers
        )
        
        # Create incident
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestSenderConfirmNoAutoResolve.transfer_id}/accept-receipt",
            json={"action": "accept_with_incident", "note": "TEST: No auto-resolve"},
            headers=self.headers
        )
        assert resp.status_code == 200
        TestSenderConfirmNoAutoResolve.ticket_id = resp.json()["incident_ticket_id"]
        print(f"✓ Ticket created: {resp.json()['incident_ticket_number']}")
    
    def test_15_sender_confirm_with_non_matching_qty_no_auto_resolve(self):
        """Sender confirm with qty NOT matching receiver should NOT auto-resolve."""
        ticket_id = TestSenderConfirmNoAutoResolve.ticket_id
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/sender-confirm",
            json={
                "confirmed_items": [{
                    "product_id": TEST_PRODUCT_ID,
                    "sender_confirmed_qty": 25  # Sender claims 25, receiver got 20 = still variance
                }],
                "note": "Sender confirms 25 were sent"
            },
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("auto_resolved") == False, f"Should not auto-resolve: {data}"
        print("✓ Sender confirm recorded but NOT auto-resolved")
    
    def test_16_verify_ticket_still_open(self):
        """Verify ticket is still open/investigating (not resolved)."""
        ticket_id = TestSenderConfirmNoAutoResolve.ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] in ["open", "investigating"], f"Should be open/investigating: {data['status']}"
        assert data["sender_confirmed"] == True
        
        # Items should have sender_confirmed_qty
        for item in data.get("items", []):
            assert "sender_confirmed_qty" in item
            assert item["sender_confirmed_qty"] == 25
        
        print(f"✓ Ticket still {data['status']} with sender confirmation recorded")


class TestExistingClosedTickets:
    """Test that existing closed tickets work correctly (no resolution_type)."""
    
    auth_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestExistingClosedTickets.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"}
            )
            assert login_resp.status_code == 200
            TestExistingClosedTickets.auth_token = login_resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestExistingClosedTickets.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_17_list_closed_tickets(self):
        """List closed tickets should work even without resolution_type."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets?status=closed", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        print(f"✓ Found {data['total']} closed tickets")
        
        for ticket in data.get("tickets", []):
            assert ticket["status"] == "closed"
            # Old tickets may not have resolution_type
            print(f"  - {ticket.get('ticket_number')}: resolution_type={ticket.get('resolution_type', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
