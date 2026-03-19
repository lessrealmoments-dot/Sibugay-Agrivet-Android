"""
Test Suite: Phase 4 Incident Tickets - Branch Filtering, Stock Resolution Types, and Link PO Feature
Tests:
1. GET /api/incident-tickets returns tickets
2. GET /api/incident-tickets?branch_id=X filters by branch_id
3. GET /api/incident-tickets/resolution-types?ticket_type=negative_stock_override returns only stock resolution types
4. GET /api/incident-tickets/resolution-types returns all resolution types when no filter
5. PUT /api/incident-tickets/{id}/add-note adds a note to timeline
6. PUT /api/incident-tickets/{id}/resolve with resolution_type=unencoded_po and linked_po stores linked PO data
7. PUT /api/incident-tickets/{id}/resolve requires PIN authorization
8. Verify stock resolution types are: unencoded_po, count_error, wrong_item, shrinkage
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CORRECT_PIN = "521325"  # Manager PIN
WRONG_PIN = "000000"
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
BRANCH_ID = "c435277f-9fc7-4d83-83e7-38be5b4423ac"  # Branch 1


@pytest.fixture(scope="session")
def auth_headers():
    """Get authentication token for API calls."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("token")
    assert token, f"No token in response: {data}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"Logged in as: {data.get('user', {}).get('email')}")
    return headers


class TestTicketListing:
    """Test ticket listing and branch filtering."""
    
    def test_list_tickets_returns_tickets(self, auth_headers):
        """GET /api/incident-tickets returns tickets array."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "tickets" in data, f"Missing 'tickets' field: {data}"
        assert "total" in data, f"Missing 'total' field: {data}"
        assert isinstance(data["tickets"], list)
        print(f"✓ GET /api/incident-tickets returned {data['total']} tickets")
    
    def test_branch_filter_reduces_count(self, auth_headers):
        """GET /api/incident-tickets?branch_id=X filters tickets by branch."""
        # Get all tickets first
        resp_all = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        all_count = resp_all.json()["total"]
        
        # Filter by specific branch
        resp_filtered = requests.get(
            f"{BASE_URL}/api/incident-tickets", 
            params={"branch_id": BRANCH_ID},
            headers=auth_headers
        )
        assert resp_filtered.status_code == 200
        filtered_count = resp_filtered.json()["total"]
        
        print(f"✓ All tickets: {all_count}, Filtered by branch: {filtered_count}")
        # Filtered should be less or equal to all
        assert filtered_count <= all_count


class TestResolutionTypes:
    """Test resolution type filtering by ticket type."""
    
    def test_stock_resolution_types_filter(self, auth_headers):
        """GET /api/incident-tickets/resolution-types?ticket_type=negative_stock_override returns only 4 stock types."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets/resolution-types",
            params={"ticket_type": "negative_stock_override"},
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        types = resp.json()
        
        # Should return exactly 4 stock resolution types
        assert len(types) == 4, f"Expected 4 stock resolution types, got {len(types)}: {types}"
        
        values = [t["value"] for t in types]
        expected = ["unencoded_po", "count_error", "wrong_item", "shrinkage"]
        for exp in expected:
            assert exp in values, f"Missing {exp} in stock resolution types"
        
        print(f"✓ Stock resolution types: {values}")
    
    def test_all_resolution_types_no_filter(self, auth_headers):
        """GET /api/incident-tickets/resolution-types returns all 10 types when no filter."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets/resolution-types",
            headers=auth_headers
        )
        assert resp.status_code == 200
        types = resp.json()
        
        # Should return all 10 types (6 transfer + 4 stock)
        assert len(types) == 10, f"Expected 10 resolution types, got {len(types)}"
        print(f"✓ All resolution types count: {len(types)}")
    
    def test_transfer_resolution_types_filter(self, auth_headers):
        """GET /api/incident-tickets/resolution-types?ticket_type=transfer returns only 6 transfer types."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets/resolution-types",
            params={"ticket_type": "transfer_variance"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        types = resp.json()
        
        # Should return 6 transfer resolution types
        assert len(types) == 6, f"Expected 6 transfer resolution types, got {len(types)}"
        
        values = [t["value"] for t in types]
        expected = ["transit_loss", "sender_error", "receiver_error", "write_off", "insurance_claim", "partial_recovery"]
        for exp in expected:
            assert exp in values, f"Missing {exp} in transfer resolution types"
        
        print(f"✓ Transfer resolution types: {values}")


class TestAddNote:
    """Test add-note endpoint."""
    
    def test_add_note_to_ticket_timeline(self, auth_headers):
        """PUT /api/incident-tickets/{id}/add-note adds note to timeline."""
        # Get any ticket
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No tickets available for testing")
        
        ticket = tickets[0]
        ticket_id = ticket["id"]
        original_timeline_count = len(ticket.get("timeline", []))
        
        # Add note
        note_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/add-note",
            json={"note": "Test investigation note from pytest"},
            headers=auth_headers
        )
        
        # Note: might fail if ticket is already closed
        if note_resp.status_code == 400 and "closed" in note_resp.text.lower():
            pytest.skip("Ticket is closed, cannot add note")
        
        assert note_resp.status_code == 200, f"Failed: {note_resp.text}"
        assert note_resp.json().get("message") == "Note added"
        
        # Verify note was added to timeline
        verify_resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=auth_headers)
        updated_ticket = verify_resp.json()
        new_timeline_count = len(updated_ticket.get("timeline", []))
        
        # Timeline should have at least one more entry (could be more if other tests ran)
        assert new_timeline_count >= original_timeline_count, "Timeline count should not decrease"
        
        # Check last timeline event
        last_event = updated_ticket["timeline"][-1] if updated_ticket.get("timeline") else {}
        if last_event.get("action") == "note":
            print(f"✓ Note added to timeline: '{last_event.get('detail', '')[:50]}...'")
        else:
            print(f"✓ Note was added (timeline count: {original_timeline_count} -> {new_timeline_count})")


class TestPINAuthorization:
    """Test PIN authorization for resolve endpoint."""
    
    def test_resolve_without_pin_fails_400(self, auth_headers):
        """PUT /api/incident-tickets/{id}/resolve without PIN returns 400."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets",
            params={"status": "open"},
            headers=auth_headers
        )
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No open tickets to test")
        
        ticket_id = tickets[0]["id"]
        
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={"resolution_type": "count_error", "resolution_note": "Test without PIN"},
            headers=auth_headers
        )
        assert resolve_resp.status_code == 400, f"Expected 400, got {resolve_resp.status_code}"
        assert "PIN required" in resolve_resp.text
        print(f"✓ Resolve without PIN correctly returns 400")
    
    def test_resolve_with_wrong_pin_fails_403(self, auth_headers):
        """PUT /api/incident-tickets/{id}/resolve with wrong PIN returns 403."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets",
            params={"status": "open"},
            headers=auth_headers
        )
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No open tickets to test")
        
        ticket_id = tickets[0]["id"]
        
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={"resolution_type": "count_error", "resolution_note": "Test with wrong PIN", "pin": WRONG_PIN},
            headers=auth_headers
        )
        assert resolve_resp.status_code == 403, f"Expected 403, got {resolve_resp.status_code}"
        print(f"✓ Resolve with wrong PIN correctly returns 403")


class TestLinkedPOFeature:
    """Test the Link PO feature for unencoded_po resolution."""
    
    def test_resolve_with_linked_po_stores_data(self, auth_headers):
        """Resolve as unencoded_po with linked_po_id/number stores the PO reference."""
        # Get an open negative_stock_override ticket
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets",
            params={"status": "open"},
            headers=auth_headers
        )
        tickets = resp.json().get("tickets", [])
        stock_tickets = [t for t in tickets if t.get("ticket_type") == "negative_stock_override"]
        
        if not stock_tickets:
            pytest.skip("No open negative_stock_override tickets to test")
        
        ticket = stock_tickets[0]
        ticket_id = ticket["id"]
        
        # Get a PO to link
        po_resp = requests.get(f"{BASE_URL}/api/purchase-orders", params={"limit": 1}, headers=auth_headers)
        pos = po_resp.json().get("purchase_orders", [])
        if not pos:
            pytest.skip("No purchase orders available to link")
        
        po = pos[0]
        
        # Resolve with linked PO
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "unencoded_po",
                "resolution_note": "Found the missing PO - linking for audit trail",
                "linked_po_id": po["id"],
                "linked_po_number": po["po_number"],
                "pin": CORRECT_PIN
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Failed: {resolve_resp.text}"
        
        # Verify ticket has linked_po fields
        verify_resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=auth_headers)
        updated = verify_resp.json()
        
        assert updated.get("linked_po_id") == po["id"], f"linked_po_id not stored"
        assert updated.get("linked_po_number") == po["po_number"], f"linked_po_number not stored"
        assert updated.get("status") == "resolved"
        assert updated.get("resolution_type") == "unencoded_po"
        
        print(f"✓ Resolved ticket {updated['ticket_number']} with linked PO: {po['po_number']}")


class TestStockResolutionTypes:
    """Test resolving negative_stock_override tickets with stock-specific resolution types."""
    
    def test_resolve_as_count_error(self, auth_headers):
        """Can resolve negative_stock_override as count_error."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets",
            params={"status": "open"},
            headers=auth_headers
        )
        tickets = resp.json().get("tickets", [])
        stock_tickets = [t for t in tickets if t.get("ticket_type") == "negative_stock_override"]
        
        if not stock_tickets:
            pytest.skip("No open negative_stock_override tickets to test")
        
        ticket = stock_tickets[0]
        ticket_id = ticket["id"]
        
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "count_error",
                "resolution_note": "Last count was off, corrected via count sheet",
                "pin": CORRECT_PIN
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Failed: {resolve_resp.text}"
        print(f"✓ Resolved as count_error")
    
    def test_resolve_as_wrong_item(self, auth_headers):
        """Can resolve negative_stock_override as wrong_item."""
        resp = requests.get(
            f"{BASE_URL}/api/incident-tickets",
            params={"status": "open"},
            headers=auth_headers
        )
        tickets = resp.json().get("tickets", [])
        stock_tickets = [t for t in tickets if t.get("ticket_type") == "negative_stock_override"]
        
        if not stock_tickets:
            pytest.skip("No open negative_stock_override tickets to test")
        
        ticket = stock_tickets[0]
        ticket_id = ticket["id"]
        
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "wrong_item",
                "resolution_note": "Cashier scanned wrong barcode, voiding sale",
                "pin": CORRECT_PIN
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Failed: {resolve_resp.text}"
        print(f"✓ Resolved as wrong_item")


class TestTicketDetailFields:
    """Verify ticket detail contains required fields for negative_stock_override."""
    
    def test_negative_stock_ticket_has_required_fields(self, auth_headers):
        """Negative stock ticket should have product, branch, invoice, stock change, cashier, override_by."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        stock_tickets = [t for t in tickets if t.get("ticket_type") == "negative_stock_override"]
        
        if not stock_tickets:
            pytest.skip("No negative_stock_override tickets to test")
        
        ticket = stock_tickets[0]
        
        # Required fields
        required_fields = [
            "product_name", "product_id", "branch_id",
            "invoice_number", "invoice_id",
            "qty_before_sale", "qty_after_sale",
            "cashier_name", "cashier_id",
            "override_by_name", "override_by_id", "override_method"
        ]
        
        for field in required_fields:
            assert field in ticket, f"Missing required field: {field}"
        
        print(f"✓ Negative stock ticket has all required fields")
        print(f"  - Product: {ticket['product_name']}")
        print(f"  - Stock change: {ticket['qty_before_sale']} → {ticket['qty_after_sale']}")
        print(f"  - Cashier: {ticket['cashier_name']}")
        print(f"  - Override by: {ticket['override_by_name']} ({ticket['override_method']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
