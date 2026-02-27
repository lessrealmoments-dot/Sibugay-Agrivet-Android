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
10. Full lifecycle test: Create ticket via variance → assign → note → resolve → close

NOTE: The accept-receipt endpoint requires actual inventory in the source branch.
      Tests create inventory before accepting transfers.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIncidentTicketsAPI:
    """Tests for incident tickets APIs - independent of transfer flow."""
    
    auth_token = None
    admin_user = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token."""
        if not TestIncidentTicketsAPI.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
            data = login_resp.json()
            TestIncidentTicketsAPI.auth_token = data["token"]
            TestIncidentTicketsAPI.admin_user = data["user"]
            
        self.headers = {
            "Authorization": f"Bearer {TestIncidentTicketsAPI.auth_token}",
            "Content-Type": "application/json"
        }
    
    # ========================================================================
    # Test 1-4: Incident Tickets List and Summary APIs (No Dependencies)
    # ========================================================================
    
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
            # All returned tickets should have the filtered status
            for ticket in data.get("tickets", []):
                assert ticket["status"] == status, f"Expected status {status}, got {ticket['status']}"
        print("✓ Status filter works for all status values")
    
    def test_03_incident_summary_endpoint_works(self):
        """GET /api/incident-tickets/summary should return status counts."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/summary", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Check required fields
        required_fields = ["open", "investigating", "resolved", "closed", 
                          "total_unresolved_capital_loss", "total_unresolved_retail_loss"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], (int, float)), f"Field {field} should be numeric"
        
        print(f"✓ Summary endpoint works: open={data['open']}, investigating={data['investigating']}")
    
    def test_04_get_nonexistent_ticket_returns_404(self):
        """GET /api/incident-tickets/{id} should return 404 for non-existent ticket."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/nonexistent-id", headers=self.headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ 404 returned for non-existent ticket")


class TestFullIncidentTicketLifecycle:
    """Full lifecycle test: Create transfer with variance → accept with incident → manage ticket."""
    
    auth_token = None
    admin_user = None
    branches = None
    source_branch_id = None
    dest_branch_id = None
    test_product = None
    transfer_id = None
    incident_ticket_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth and branches."""
        if not TestFullIncidentTicketLifecycle.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
            data = login_resp.json()
            TestFullIncidentTicketLifecycle.auth_token = data["token"]
            TestFullIncidentTicketLifecycle.admin_user = data["user"]
            
        self.headers = {
            "Authorization": f"Bearer {TestFullIncidentTicketLifecycle.auth_token}",
            "Content-Type": "application/json"
        }
    
    # ========================================================================
    # Setup: Get branches and ensure inventory exists
    # ========================================================================
    
    def test_05_get_branches(self):
        """Get available branches for transfer."""
        resp = requests.get(f"{BASE_URL}/api/branches", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        branches = data.get("branches", []) if isinstance(data, dict) else data
        assert len(branches) >= 2, "Need at least 2 branches"
        TestFullIncidentTicketLifecycle.branches = branches
        TestFullIncidentTicketLifecycle.source_branch_id = branches[0]["id"]
        TestFullIncidentTicketLifecycle.dest_branch_id = branches[1]["id"]
        print(f"✓ Using branches: {branches[0]['name']} → {branches[1]['name']}")
    
    def test_06_get_product_with_inventory(self):
        """Find a product that has inventory in the source branch."""
        source_branch = TestFullIncidentTicketLifecycle.source_branch_id
        
        # Get inventory for the source branch
        resp = requests.get(
            f"{BASE_URL}/api/inventory?branch_id={source_branch}&limit=10",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        inventory_items = data.get("items", data.get("inventory", []))
        
        # Find a product with qty >= 10
        suitable_product = None
        for item in inventory_items:
            if float(item.get("quantity", 0)) >= 10:
                suitable_product = item
                break
        
        if not suitable_product:
            # Create inventory for a test product
            print("⚠ No product with inventory >= 10 found, will create test inventory")
            # Get any product
            resp = requests.get(f"{BASE_URL}/api/products?limit=1", headers=self.headers)
            assert resp.status_code == 200
            products = resp.json().get("products", [])
            assert len(products) > 0, "No products found"
            product = products[0]
            
            # Add inventory to source branch
            adjust_data = {
                "product_id": product["id"],
                "branch_id": source_branch,
                "adjustment": 100,
                "reason": "TEST: Adding stock for incident ticket testing"
            }
            resp = requests.post(f"{BASE_URL}/api/inventory/adjust", json=adjust_data, headers=self.headers)
            if resp.status_code == 200:
                print(f"✓ Added 100 units of {product['name']} to source branch")
            else:
                print(f"⚠ Could not adjust inventory: {resp.text}")
            
            TestFullIncidentTicketLifecycle.test_product = {
                "id": product["id"],
                "name": product["name"],
                "sku": product.get("sku", ""),
                "cost_price": float(product.get("cost_price", 100))
            }
        else:
            TestFullIncidentTicketLifecycle.test_product = {
                "id": suitable_product["product_id"],
                "name": suitable_product.get("product_name", "Unknown"),
                "sku": suitable_product.get("sku", ""),
                "cost_price": float(suitable_product.get("cost_price", 100))
            }
            print(f"✓ Found product with inventory: {TestFullIncidentTicketLifecycle.test_product['name']}")
    
    def test_07_create_transfer_for_incident_test(self):
        """Create a transfer order for incident testing."""
        product = TestFullIncidentTicketLifecycle.test_product
        source = TestFullIncidentTicketLifecycle.source_branch_id
        dest = TestFullIncidentTicketLifecycle.dest_branch_id
        
        transfer_data = {
            "from_branch_id": source,
            "to_branch_id": dest,
            "items": [{
                "product_id": product["id"],
                "product_name": product["name"],
                "sku": product.get("sku", "TEST-SKU"),
                "qty": 10,
                "unit": "pcs",
                "branch_capital": product["cost_price"],
                "transfer_capital": product["cost_price"] * 1.05,
                "branch_retail": product["cost_price"] * 1.3
            }],
            "notes": "TEST: Transfer for incident ticket lifecycle testing"
        }
        
        resp = requests.post(f"{BASE_URL}/api/branch-transfers", json=transfer_data, headers=self.headers)
        assert resp.status_code == 200, f"Failed to create transfer: {resp.text}"
        data = resp.json()
        TestFullIncidentTicketLifecycle.transfer_id = data["id"]
        print(f"✓ Created transfer: {data.get('order_number')}")
    
    def test_08_send_transfer(self):
        """Send the transfer."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        resp = requests.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/send", headers=self.headers)
        assert resp.status_code == 200, f"Failed to send: {resp.text}"
        print("✓ Transfer sent")
    
    def test_09_receive_with_variance(self):
        """Receive transfer with variance (shortage)."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        product = TestFullIncidentTicketLifecycle.test_product
        
        receive_data = {
            "items": [{
                "product_id": product["id"],
                "qty": 10,
                "qty_received": 7  # Shortage of 3 units
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
    
    def test_10_accept_receipt_with_incident(self):
        """Accept receipt with action='accept_with_incident' to create incident ticket."""
        transfer_id = TestFullIncidentTicketLifecycle.transfer_id
        
        accept_data = {
            "action": "accept_with_incident",
            "note": "TEST: Accepting with incident ticket for investigation of missing 3 units"
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/accept-receipt",
            json=accept_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed to accept: {resp.text}"
        data = resp.json()
        
        # Verify incident ticket was created
        assert "incident_ticket_id" in data, f"Expected incident_ticket_id in response: {data}"
        assert "incident_ticket_number" in data, f"Expected incident_ticket_number: {data}"
        
        TestFullIncidentTicketLifecycle.incident_ticket_id = data["incident_ticket_id"]
        print(f"✓ Receipt accepted with incident ticket: {data['incident_ticket_number']}")
    
    # ========================================================================
    # Test Incident Ticket Detail
    # ========================================================================
    
    def test_11_get_incident_ticket_detail(self):
        """GET /api/incident-tickets/{id} should return ticket with timeline."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Validate structure
        assert data["id"] == ticket_id
        assert "ticket_number" in data
        assert "transfer_id" in data
        assert "order_number" in data
        assert "items" in data
        assert "timeline" in data
        assert "status" in data
        assert data["status"] == "open"
        
        # Timeline should have 'created' event
        assert len(data["timeline"]) >= 1
        assert data["timeline"][0]["action"] == "created"
        
        print(f"✓ Ticket detail verified: {data['ticket_number']}, status={data['status']}")
    
    # ========================================================================
    # Test Assign Ticket
    # ========================================================================
    
    def test_12_assign_ticket(self):
        """PUT /api/incident-tickets/{id}/assign should assign and set status to investigating."""
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
        assert resp.status_code == 200, f"Failed to assign: {resp.text}"
        print("✓ Ticket assigned")
    
    def test_13_verify_ticket_is_investigating(self):
        """Verify ticket status is now 'investigating'."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "investigating"
        assert data["assigned_to_id"] != ""
        
        # Timeline should have 'assigned' event
        actions = [e["action"] for e in data["timeline"]]
        assert "assigned" in actions
        print("✓ Ticket status is 'investigating' with assigned event in timeline")
    
    # ========================================================================
    # Test Add Note
    # ========================================================================
    
    def test_14_add_note_to_ticket(self):
        """PUT /api/incident-tickets/{id}/add-note should add investigation note."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        note_data = {"note": "TEST: Reviewed delivery receipt photos - shortage confirmed"}
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/add-note",
            json=note_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["message"] == "Note added"
        print("✓ Note added")
    
    def test_15_verify_note_in_timeline(self):
        """Verify note appears in timeline."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        note_events = [e for e in data["timeline"] if e["action"] == "note"]
        assert len(note_events) >= 1
        assert "shortage confirmed" in note_events[-1]["detail"]
        print(f"✓ Note found in timeline ({len(note_events)} note events)")
    
    def test_16_add_empty_note_fails(self):
        """Adding empty note should fail with 400."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/add-note",
            json={"note": ""},
            headers=self.headers
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ Empty note correctly rejected")
    
    # ========================================================================
    # Test Resolve Ticket
    # ========================================================================
    
    def test_17_resolve_ticket(self):
        """PUT /api/incident-tickets/{id}/resolve should resolve with note and recovery."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        resolve_data = {
            "resolution_note": "TEST: Investigation complete - missing units attributed to transit damage. Insurance claim filed.",
            "recovery_amount": 150.0
        }
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json=resolve_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "resolved"
        print("✓ Ticket resolved")
    
    def test_18_verify_resolved_state(self):
        """Verify ticket has resolved state with all fields."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "resolved"
        assert "transit damage" in data["resolution_note"]
        assert data["recovery_amount"] == 150.0
        assert data["resolved_by_id"] != ""
        assert data["resolved_at"] is not None
        
        # Timeline should have 'resolved' event
        resolved_events = [e for e in data["timeline"] if e["action"] == "resolved"]
        assert len(resolved_events) == 1
        print("✓ Resolved state verified with all fields")
    
    # ========================================================================
    # Test Close Ticket (Admin Only)
    # ========================================================================
    
    def test_19_close_ticket(self):
        """PUT /api/incident-tickets/{id}/close should close the ticket."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        
        close_data = {"note": "TEST: Case closed after insurance recovery processed"}
        
        resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/close",
            json=close_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["message"] == "Ticket closed"
        print("✓ Ticket closed")
    
    def test_20_verify_closed_state(self):
        """Verify ticket is closed with timeline event."""
        ticket_id = TestFullIncidentTicketLifecycle.incident_ticket_id
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "closed"
        assert data["closed_at"] is not None
        
        # Timeline should have 'closed' event
        closed_events = [e for e in data["timeline"] if e["action"] == "closed"]
        assert len(closed_events) == 1
        print(f"✓ Ticket closed. Timeline has {len(data['timeline'])} events total")


class TestAcceptReceiptWithoutIncident:
    """Test accept-receipt with action='accept' (no incident ticket creation)."""
    
    auth_token = None
    branches = None
    source_branch_id = None
    dest_branch_id = None
    test_product = None
    transfer_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth."""
        if not TestAcceptReceiptWithoutIncident.auth_token:
            login_resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            assert login_resp.status_code == 200
            TestAcceptReceiptWithoutIncident.auth_token = login_resp.json()["token"]
            
        self.headers = {
            "Authorization": f"Bearer {TestAcceptReceiptWithoutIncident.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_21_setup_branches_and_product(self):
        """Setup branches and find/create product with inventory."""
        # Get branches
        resp = requests.get(f"{BASE_URL}/api/branches", headers=self.headers)
        assert resp.status_code == 200
        branches = resp.json().get("branches", []) if isinstance(resp.json(), dict) else resp.json()
        assert len(branches) >= 2
        TestAcceptReceiptWithoutIncident.branches = branches
        TestAcceptReceiptWithoutIncident.source_branch_id = branches[0]["id"]
        TestAcceptReceiptWithoutIncident.dest_branch_id = branches[1]["id"]
        
        # Find product with inventory
        resp = requests.get(
            f"{BASE_URL}/api/inventory?branch_id={branches[0]['id']}&limit=5",
            headers=self.headers
        )
        assert resp.status_code == 200
        items = resp.json().get("items", resp.json().get("inventory", []))
        
        product = None
        for item in items:
            if float(item.get("quantity", 0)) >= 5:
                product = {
                    "id": item["product_id"],
                    "name": item.get("product_name", "Test Product"),
                    "cost_price": float(item.get("cost_price", 100))
                }
                break
        
        if not product:
            # Fallback: get any product and adjust inventory
            resp = requests.get(f"{BASE_URL}/api/products?limit=1", headers=self.headers)
            products = resp.json().get("products", [])
            assert len(products) > 0
            p = products[0]
            product = {
                "id": p["id"],
                "name": p["name"],
                "cost_price": float(p.get("cost_price", 100))
            }
            # Adjust inventory
            requests.post(
                f"{BASE_URL}/api/inventory/adjust",
                json={"product_id": p["id"], "branch_id": branches[0]["id"], "adjustment": 50, "reason": "TEST"},
                headers=self.headers
            )
        
        TestAcceptReceiptWithoutIncident.test_product = product
        print(f"✓ Setup complete: {product['name']}")
    
    def test_22_create_and_send_transfer(self):
        """Create and send transfer."""
        product = TestAcceptReceiptWithoutIncident.test_product
        source = TestAcceptReceiptWithoutIncident.source_branch_id
        dest = TestAcceptReceiptWithoutIncident.dest_branch_id
        
        transfer_data = {
            "from_branch_id": source,
            "to_branch_id": dest,
            "items": [{
                "product_id": product["id"],
                "product_name": product["name"],
                "sku": "TEST-ACCEPT-ONLY",
                "qty": 5,
                "unit": "pcs",
                "branch_capital": product["cost_price"],
                "transfer_capital": product["cost_price"] * 1.05,
                "branch_retail": product["cost_price"] * 1.3
            }],
            "notes": "TEST: Transfer for accept-only test"
        }
        
        resp = requests.post(f"{BASE_URL}/api/branch-transfers", json=transfer_data, headers=self.headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        TestAcceptReceiptWithoutIncident.transfer_id = resp.json()["id"]
        
        # Send
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{TestAcceptReceiptWithoutIncident.transfer_id}/send",
            headers=self.headers
        )
        assert resp.status_code == 200
        print("✓ Transfer created and sent")
    
    def test_23_receive_with_variance(self):
        """Receive with variance."""
        transfer_id = TestAcceptReceiptWithoutIncident.transfer_id
        product = TestAcceptReceiptWithoutIncident.test_product
        
        receive_data = {
            "items": [{"product_id": product["id"], "qty": 5, "qty_received": 4}],
            "skip_receipt_check": True
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/receive",
            json=receive_data,
            headers=self.headers
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "received_pending"
        print("✓ Received with variance")
    
    def test_24_accept_with_accept_action_only(self):
        """Accept with action='accept' should NOT create incident ticket."""
        transfer_id = TestAcceptReceiptWithoutIncident.transfer_id
        
        accept_data = {
            "action": "accept",
            "note": "TEST: Accepting variance without creating incident ticket"
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{transfer_id}/accept-receipt",
            json=accept_data,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Should NOT have incident_ticket_id (or it should be None)
        incident_id = data.get("incident_ticket_id")
        assert incident_id is None or incident_id == "", f"Should not create incident ticket: {data}"
        assert data.get("status") == "received"
        print("✓ Receipt accepted WITHOUT incident ticket")
    
    def test_25_verify_audit_log_created(self):
        """Verify audit log was created for variance acceptance."""
        transfer_id = TestAcceptReceiptWithoutIncident.transfer_id
        
        # Get the transfer to check accept_action
        resp = requests.get(f"{BASE_URL}/api/branch-transfers/{transfer_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "received"
        assert data.get("accept_action") == "accept"
        assert data.get("accepted_by") is not None
        print("✓ Transfer state verified: accepted without incident")


class TestSummaryAfterLifecycle:
    """Verify summary counts after creating/closing a ticket."""
    
    auth_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not TestSummaryAfterLifecycle.auth_token:
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
            )
            TestSummaryAfterLifecycle.auth_token = resp.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {TestSummaryAfterLifecycle.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_26_summary_reflects_closed_ticket(self):
        """Summary should show at least 1 closed ticket after lifecycle test."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/summary", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # After the lifecycle test, we should have at least 1 closed ticket
        assert data["closed"] >= 1, f"Expected at least 1 closed ticket: {data}"
        print(f"✓ Summary shows: open={data['open']}, investigating={data['investigating']}, "
              f"resolved={data['resolved']}, closed={data['closed']}")
    
    def test_27_list_tickets_with_transfer_filter(self):
        """List tickets filtered by transfer_id should work."""
        # Get any transfer_id from tickets
        resp = requests.get(f"{BASE_URL}/api/incident-tickets?limit=1", headers=self.headers)
        assert resp.status_code == 200
        tickets = resp.json().get("tickets", [])
        
        if len(tickets) > 0:
            transfer_id = tickets[0].get("transfer_id")
            resp = requests.get(
                f"{BASE_URL}/api/incident-tickets?transfer_id={transfer_id}",
                headers=self.headers
            )
            assert resp.status_code == 200
            filtered = resp.json().get("tickets", [])
            for t in filtered:
                assert t["transfer_id"] == transfer_id
            print(f"✓ Transfer filter works, found {len(filtered)} ticket(s)")
        else:
            print("⚠ No tickets to test transfer filter")
    
    def test_28_list_tickets_with_branch_filter(self):
        """List tickets filtered by branch_id should work."""
        # Get any branch_id from tickets
        resp = requests.get(f"{BASE_URL}/api/incident-tickets?limit=1", headers=self.headers)
        tickets = resp.json().get("tickets", [])
        
        if len(tickets) > 0:
            branch_id = tickets[0].get("from_branch_id")
            resp = requests.get(
                f"{BASE_URL}/api/incident-tickets?branch_id={branch_id}",
                headers=self.headers
            )
            assert resp.status_code == 200
            print(f"✓ Branch filter works, returned {resp.json().get('total', 0)} ticket(s)")
        else:
            print("⚠ No tickets to test branch filter")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
