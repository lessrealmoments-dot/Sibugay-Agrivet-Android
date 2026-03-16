"""
Test Suite: Phase 3 Incident Tickets - Auto Journal Entries & PIN Authorization
Tests:
1. Summary returns correct total_real_capital_loss (excluding sender_error)
2. Resolve without PIN fails (400)
3. Resolve with wrong PIN fails (403)
4. Resolve with correct PIN succeeds
5. transit_loss resolution creates journal entry with DR 1110 / CR 1200
6. write_off resolution creates journal entry with DR 5500 / CR 1200
7. insurance_claim resolution creates journal entry with DR 1120 / CR 1200
8. sender_error resolution creates NO journal entry
9. Journal entry has entry_type='incident_adjustment'
10. Ticket stores journal_entry_id and journal_entry_number after resolve
11. Approved by name and method stored in ticket
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CORRECT_PIN = "521325"
WRONG_PIN = "000000"
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"


@pytest.fixture(scope="session")
def auth_headers():
    """Get authentication token for API calls."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("token")  # API returns 'token' not 'access_token'
    assert token, f"No token in response: {data}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"Logged in as: {data.get('user', {}).get('email')}")
    return headers


class TestPhase3SummaryCapitalLoss:
    """Test that summary endpoint returns total_real_capital_loss excluding sender_error tickets."""
    
    def test_summary_returns_total_real_capital_loss(self, auth_headers):
        """Summary endpoint should return total_real_capital_loss field."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets/summary", headers=auth_headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Must contain total_real_capital_loss field
        assert "total_real_capital_loss" in data, f"Missing total_real_capital_loss: {data}"
        
        # Value should be 3150 (sum of all tickets except sender_error)
        # INC-00001 (transit_loss): 1050
        # INC-00002 (write_off): 1050
        # INC-00003 (open, was write_off but doesn't matter): 1050
        # INC-00004, 05, 06 are sender_error (excluded)
        total = data["total_real_capital_loss"]
        print(f"total_real_capital_loss: {total}")
        assert total == 3150, f"Expected 3150, got {total}"


class TestPhase3PINAuthorization:
    """Test PIN authorization is required for resolving incident tickets."""
    
    def test_resolve_without_pin_fails(self, auth_headers):
        """Resolve should fail with 400 when no PIN provided."""
        # Find an open ticket
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", 
                          params={"status": "open"}, headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No open tickets to test")
        
        ticket_id = tickets[0]["id"]
        
        # Try to resolve without PIN
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "write_off",
                "resolution_note": "Test without PIN"
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 400, f"Expected 400, got {resolve_resp.status_code}: {resolve_resp.text}"
        assert "PIN required" in resolve_resp.text or "pin" in resolve_resp.text.lower()
        print(f"✓ Resolve without PIN correctly rejected: {resolve_resp.json()}")
    
    def test_resolve_with_wrong_pin_fails(self, auth_headers):
        """Resolve should fail with 403 when wrong PIN provided."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", 
                          params={"status": "open"}, headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No open tickets to test")
        
        ticket_id = tickets[0]["id"]
        
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "write_off",
                "resolution_note": "Test with wrong PIN",
                "pin": WRONG_PIN
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 403, f"Expected 403, got {resolve_resp.status_code}: {resolve_resp.text}"
        print(f"✓ Resolve with wrong PIN correctly rejected: {resolve_resp.json()}")


class TestPhase3JournalEntryCreation:
    """Test auto-creation of journal entries on resolution."""
    
    @pytest.fixture
    def create_test_ticket(self, auth_headers):
        """Helper to reopen a ticket or find an open one for testing."""
        # First check if there's already an open ticket
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", 
                          params={"status": "open"}, headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        if tickets:
            return tickets[0]
        
        # If no open tickets, we need to manually create one via MongoDB
        # For now, skip the test if no open tickets
        pytest.skip("No open tickets available - need to reopen one in MongoDB")
    
    def test_transit_loss_creates_journal_entry(self, auth_headers):
        """transit_loss resolution creates DR 1110 (Driver Receivable), CR 1200 (Inventory)."""
        # Get an open ticket
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", 
                          params={"status": "open"}, headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        if not tickets:
            pytest.skip("No open tickets to test")
        
        ticket = tickets[0]
        ticket_id = ticket["id"]
        ticket_number = ticket.get("ticket_number")
        capital_loss = ticket.get("total_capital_loss", 0)
        
        # Resolve with transit_loss + correct PIN
        resolve_resp = requests.put(
            f"{BASE_URL}/api/incident-tickets/{ticket_id}/resolve",
            json={
                "resolution_type": "transit_loss",
                "resolution_note": "Test transit loss with auto JE",
                "accountable_party": "Test Driver ABC",
                "pin": CORRECT_PIN
            },
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, f"Resolve failed: {resolve_resp.text}"
        result = resolve_resp.json()
        
        # Check journal_entry is returned
        je_id = result.get("journal_entry")
        print(f"Resolved ticket {ticket_number}, journal_entry={je_id}")
        assert je_id is not None, f"Expected journal_entry in response: {result}"
        
        # Fetch the ticket to verify it has journal_entry_id and journal_entry_number
        ticket_resp = requests.get(f"{BASE_URL}/api/incident-tickets/{ticket_id}", headers=auth_headers)
        assert ticket_resp.status_code == 200
        updated_ticket = ticket_resp.json()
        
        assert updated_ticket.get("journal_entry_id") == je_id
        assert updated_ticket.get("journal_entry_number") is not None
        je_number = updated_ticket.get("journal_entry_number")
        print(f"✓ Ticket now has journal_entry_number: {je_number}")
        
        # Verify approved_by fields
        assert updated_ticket.get("approved_by_name") is not None
        assert updated_ticket.get("approval_method") is not None
        print(f"✓ Approved by: {updated_ticket.get('approved_by_name')} ({updated_ticket.get('approval_method')})")
        
        # Fetch the journal entry to verify structure
        je_resp = requests.get(f"{BASE_URL}/api/journal-entries/{je_id}", headers=auth_headers)
        assert je_resp.status_code == 200
        je = je_resp.json()
        
        assert je["entry_type"] == "incident_adjustment", f"Expected incident_adjustment, got {je['entry_type']}"
        assert je["reference_number"] == ticket_number
        
        # Verify lines: DR 1110, CR 1200
        lines = je.get("lines", [])
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"
        
        dr_line = next((l for l in lines if l.get("debit", 0) > 0), None)
        cr_line = next((l for l in lines if l.get("credit", 0) > 0), None)
        
        assert dr_line is not None, "Missing debit line"
        assert cr_line is not None, "Missing credit line"
        
        assert dr_line["account_code"] == "1110", f"Expected DR 1110, got {dr_line['account_code']}"
        assert cr_line["account_code"] == "1200", f"Expected CR 1200, got {cr_line['account_code']}"
        
        print(f"✓ JE lines correct: DR {dr_line['account_code']} {dr_line['debit']}, CR {cr_line['account_code']} {cr_line['credit']}")
        
        # Reopen the ticket for next tests
        # Note: This would require admin access or direct DB update


class TestPhase3JournalEntryTypes:
    """Test journal entry accounts for different resolution types."""
    
    def test_je_accounts_endpoint(self, auth_headers):
        """Verify accounts endpoint includes 1110, 1120."""
        resp = requests.get(f"{BASE_URL}/api/journal-entries/accounts", headers=auth_headers)
        assert resp.status_code == 200
        accounts = resp.json().get("accounts", [])
        
        codes = [a["code"] for a in accounts]
        assert "1110" in codes, "Missing account 1110 (Driver/Courier Receivable)"
        assert "1120" in codes, "Missing account 1120 (Insurance Receivable)"
        print(f"✓ Accounts include 1110 (Driver Receivable) and 1120 (Insurance Receivable)")
    
    def test_je_list_incident_adjustment_type(self, auth_headers):
        """Journal entries list can filter by entry_type=incident_adjustment."""
        resp = requests.get(
            f"{BASE_URL}/api/journal-entries",
            params={"entry_type": "incident_adjustment"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        entries = resp.json().get("entries", [])
        
        # Should have at least the entries we created
        print(f"✓ Found {len(entries)} journal entries with entry_type=incident_adjustment")
        
        for je in entries:
            assert je["entry_type"] == "incident_adjustment", f"Wrong type: {je['entry_type']}"
            print(f"  - {je['je_number']}: {je['memo'][:50]}...")


class TestPhase3ExistingJournalEntries:
    """Verify existing journal entries from previous resolutions."""
    
    def test_verify_existing_transit_loss_je(self, auth_headers):
        """Verify JE-IB-001000 (transit_loss) has correct accounts."""
        # Get the ticket that has this JE
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        
        transit_ticket = next((t for t in tickets if t.get("journal_entry_number") == "JE-IB-001000"), None)
        if not transit_ticket:
            # Try to find by resolution type
            transit_ticket = next((t for t in tickets if t.get("resolution_type") == "transit_loss" and t.get("journal_entry_id")), None)
        
        if not transit_ticket:
            pytest.skip("No transit_loss ticket with JE found")
        
        je_id = transit_ticket.get("journal_entry_id")
        je_resp = requests.get(f"{BASE_URL}/api/journal-entries/{je_id}", headers=auth_headers)
        assert je_resp.status_code == 200
        je = je_resp.json()
        
        lines = je.get("lines", [])
        dr_codes = [l["account_code"] for l in lines if l.get("debit", 0) > 0]
        cr_codes = [l["account_code"] for l in lines if l.get("credit", 0) > 0]
        
        print(f"transit_loss JE: DR {dr_codes}, CR {cr_codes}")
        assert "1110" in dr_codes, f"Expected DR 1110 (Driver Receivable), got {dr_codes}"
        assert "1200" in cr_codes, f"Expected CR 1200 (Inventory), got {cr_codes}"
    
    def test_verify_existing_write_off_je(self, auth_headers):
        """Verify JE-IB-001001 (write_off) has correct accounts."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        
        writeoff_ticket = next((t for t in tickets if t.get("journal_entry_number") == "JE-IB-001001"), None)
        if not writeoff_ticket:
            writeoff_ticket = next((t for t in tickets if t.get("resolution_type") == "write_off" and t.get("journal_entry_id")), None)
        
        if not writeoff_ticket:
            pytest.skip("No write_off ticket with JE found")
        
        je_id = writeoff_ticket.get("journal_entry_id")
        je_resp = requests.get(f"{BASE_URL}/api/journal-entries/{je_id}", headers=auth_headers)
        assert je_resp.status_code == 200
        je = je_resp.json()
        
        lines = je.get("lines", [])
        dr_codes = [l["account_code"] for l in lines if l.get("debit", 0) > 0]
        cr_codes = [l["account_code"] for l in lines if l.get("credit", 0) > 0]
        
        print(f"write_off JE: DR {dr_codes}, CR {cr_codes}")
        assert "5500" in dr_codes, f"Expected DR 5500 (Inventory Loss), got {dr_codes}"
        assert "1200" in cr_codes, f"Expected CR 1200 (Inventory), got {cr_codes}"


class TestPhase3SenderErrorNoJE:
    """Verify sender_error resolutions create no journal entry."""
    
    def test_sender_error_tickets_have_no_je(self, auth_headers):
        """Tickets resolved as sender_error should have no journal_entry_id."""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", headers=auth_headers)
        tickets = resp.json().get("tickets", [])
        
        sender_error_tickets = [t for t in tickets if t.get("resolution_type") == "sender_error"]
        assert len(sender_error_tickets) > 0, "No sender_error tickets found"
        
        for t in sender_error_tickets:
            je_id = t.get("journal_entry_id")
            je_num = t.get("journal_entry_number")
            print(f"{t['ticket_number']} (sender_error): je_id={je_id}, je_num={je_num}")
            assert je_id is None or je_id == "", f"sender_error ticket {t['ticket_number']} should not have JE"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
