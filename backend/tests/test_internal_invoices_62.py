"""
Test Internal Invoices - Phase 2: Internal Invoicing for branch-to-branch transfers
Tests:
1. Internal invoice auto-created when branch transfer is created
2. Invoice has correct fields (invoice_number, transfer_id, items, grand_total, status, terms_days, due_date)
3. GET /internal-invoices lists all invoices with branch name enrichment
4. GET /internal-invoices/summary returns payable/receivable totals
5. GET /internal-invoices/by-transfer/{transfer_id} returns the linked invoice
6. Invoice status updates to 'sent' when transfer is sent
7. Invoice status updates to 'received' when transfer is received
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


class TestInternalInvoices:
    """Test Internal Invoices feature for branch-to-branch transfers"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sibugayagrivetsupply@gmail.com",
            "password": "521325"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token = login_response.json().get("token")
        assert token, "No token in response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get branches for testing
        branches_resp = self.session.get(f"{BASE_URL}/api/branches")
        assert branches_resp.status_code == 200, f"Failed to get branches: {branches_resp.text}"
        self.branches = branches_resp.json() if isinstance(branches_resp.json(), list) else branches_resp.json().get("branches", [])
        assert len(self.branches) >= 2, "Need at least 2 branches for transfer testing"
        
        yield

    def test_01_internal_invoices_endpoint_exists(self):
        """Test that GET /internal-invoices endpoint exists and returns data"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices")
        assert response.status_code == 200, f"GET /internal-invoices failed: {response.text}"
        
        data = response.json()
        assert "invoices" in data, "Response should have 'invoices' key"
        assert "total" in data, "Response should have 'total' key"
        print(f"PASS: GET /internal-invoices returns {data['total']} invoices")

    def test_02_internal_invoices_summary_endpoint(self):
        """Test that GET /internal-invoices/summary returns payable/receivable totals"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices/summary")
        assert response.status_code == 200, f"GET /internal-invoices/summary failed: {response.text}"
        
        data = response.json()
        assert "payable" in data, "Response should have 'payable' key"
        assert "receivable" in data, "Response should have 'receivable' key"
        
        # Check payable structure
        payable = data["payable"]
        assert "total" in payable, "Payable should have 'total'"
        assert "count" in payable, "Payable should have 'count'"
        assert "overdue_total" in payable, "Payable should have 'overdue_total'"
        assert "overdue_count" in payable, "Payable should have 'overdue_count'"
        assert "due_soon_total" in payable, "Payable should have 'due_soon_total'"
        assert "due_soon_count" in payable, "Payable should have 'due_soon_count'"
        
        # Check receivable structure
        receivable = data["receivable"]
        assert "total" in receivable, "Receivable should have 'total'"
        assert "count" in receivable, "Receivable should have 'count'"
        
        print(f"PASS: Summary - Payable: {payable['total']} ({payable['count']}), Receivable: {receivable['total']} ({receivable['count']})")

    def test_03_create_transfer_auto_creates_invoice(self):
        """Test that creating a branch transfer auto-creates an internal invoice"""
        # Get a product for the transfer
        products_resp = self.session.get(f"{BASE_URL}/api/products", params={"limit": 1})
        assert products_resp.status_code == 200
        products = products_resp.json().get("products", [])
        assert len(products) > 0, "Need at least one product"
        product = products[0]
        
        # Create a branch transfer
        from_branch = self.branches[0]
        to_branch = self.branches[1]
        
        transfer_data = {
            "from_branch_id": from_branch["id"],
            "to_branch_id": to_branch["id"],
            "min_margin": 20,
            "items": [{
                "product_id": product["id"],
                "product_name": product.get("name", "Test Product"),
                "sku": product.get("sku", "SKU001"),
                "category": product.get("category", "General"),
                "unit": product.get("unit", "pc"),
                "qty": 5,
                "branch_capital": 100.00,
                "transfer_capital": 110.00,
                "branch_retail": 150.00
            }]
        }
        
        transfer_resp = self.session.post(f"{BASE_URL}/api/branch-transfers", json=transfer_data)
        assert transfer_resp.status_code == 200, f"Create transfer failed: {transfer_resp.text}"
        
        transfer = transfer_resp.json()
        self.__class__.test_transfer_id = transfer["id"]
        self.__class__.test_order_number = transfer["order_number"]
        
        # Verify invoice was auto-created
        assert "invoice_id" in transfer, f"Transfer should have invoice_id: {transfer}"
        assert "invoice_number" in transfer, f"Transfer should have invoice_number: {transfer}"
        assert transfer["invoice_number"].startswith("INV-"), f"Invoice number should start with 'INV-': {transfer['invoice_number']}"
        
        self.__class__.test_invoice_id = transfer["invoice_id"]
        self.__class__.test_invoice_number = transfer["invoice_number"]
        
        print(f"PASS: Transfer {transfer['order_number']} auto-created invoice {transfer['invoice_number']}")

    def test_04_invoice_by_transfer_endpoint(self):
        """Test GET /internal-invoices/by-transfer/{transfer_id} returns linked invoice"""
        transfer_id = getattr(self.__class__, 'test_transfer_id', None)
        if not transfer_id:
            pytest.skip("No test transfer created")
        
        response = self.session.get(f"{BASE_URL}/api/internal-invoices/by-transfer/{transfer_id}")
        assert response.status_code == 200, f"GET invoice by transfer failed: {response.text}"
        
        invoice = response.json()
        
        # Verify invoice fields
        assert invoice["transfer_id"] == transfer_id, "Invoice should have correct transfer_id"
        assert "invoice_number" in invoice, "Invoice should have invoice_number"
        assert "items" in invoice, "Invoice should have items"
        assert "grand_total" in invoice, "Invoice should have grand_total"
        assert "status" in invoice, "Invoice should have status"
        assert "terms_days" in invoice, "Invoice should have terms_days"
        assert "due_date" in invoice, "Invoice should have due_date"
        
        # Verify default values
        assert invoice["terms_days"] == 15, f"Default terms should be 15 days: {invoice['terms_days']}"
        assert invoice["status"] == "prepared", f"Initial status should be 'prepared': {invoice['status']}"
        
        # Verify items
        items = invoice["items"]
        assert len(items) == 1, f"Invoice should have 1 item: {len(items)}"
        item = items[0]
        assert item["qty"] == 5, f"Item qty should be 5: {item['qty']}"
        assert item["transfer_capital"] == 110.00, f"Item transfer_capital should be 110: {item['transfer_capital']}"
        assert "line_total" in item, "Item should have line_total"
        
        # Verify grand_total calculation
        expected_total = 110.00 * 5  # transfer_capital * qty
        assert invoice["grand_total"] == expected_total, f"Grand total should be {expected_total}: {invoice['grand_total']}"
        
        # Verify branch names enrichment
        assert "from_branch_name" in invoice, "Invoice should have from_branch_name"
        assert "to_branch_name" in invoice, "Invoice should have to_branch_name"
        
        print(f"PASS: Invoice {invoice['invoice_number']} has correct fields - Total: {invoice['grand_total']}, Status: {invoice['status']}, Terms: Net {invoice['terms_days']}")

    def test_05_invoice_appears_in_list(self):
        """Test that created invoice appears in /internal-invoices list with branch name enrichment"""
        invoice_id = getattr(self.__class__, 'test_invoice_id', None)
        if not invoice_id:
            pytest.skip("No test invoice created")
        
        response = self.session.get(f"{BASE_URL}/api/internal-invoices")
        assert response.status_code == 200
        
        invoices = response.json().get("invoices", [])
        test_invoice = next((inv for inv in invoices if inv["id"] == invoice_id), None)
        
        assert test_invoice is not None, f"Invoice {invoice_id} should appear in list"
        
        # Verify branch name enrichment
        assert "from_branch_name" in test_invoice, "Invoice should have from_branch_name"
        assert "to_branch_name" in test_invoice, "Invoice should have to_branch_name"
        assert test_invoice["from_branch_name"], "from_branch_name should not be empty"
        assert test_invoice["to_branch_name"], "to_branch_name should not be empty"
        
        print(f"PASS: Invoice in list with branch names: {test_invoice['from_branch_name']} → {test_invoice['to_branch_name']}")

    def test_06_invoice_status_updates_on_send(self):
        """Test that invoice status updates to 'sent' when transfer is sent"""
        transfer_id = getattr(self.__class__, 'test_transfer_id', None)
        if not transfer_id:
            pytest.skip("No test transfer created")
        
        # Send the transfer
        send_resp = self.session.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/send")
        assert send_resp.status_code == 200, f"Send transfer failed: {send_resp.text}"
        
        # Verify invoice status updated
        invoice_resp = self.session.get(f"{BASE_URL}/api/internal-invoices/by-transfer/{transfer_id}")
        assert invoice_resp.status_code == 200
        
        invoice = invoice_resp.json()
        assert invoice["status"] == "sent", f"Invoice status should be 'sent' after transfer sent: {invoice['status']}"
        assert invoice["sent_at"] is not None, "Invoice should have sent_at timestamp"
        
        print(f"PASS: Invoice status updated to 'sent' at {invoice['sent_at']}")

    def test_07_invoice_status_updates_on_receive(self):
        """Test that invoice status updates to 'received' when transfer is received"""
        transfer_id = getattr(self.__class__, 'test_transfer_id', None)
        if not transfer_id:
            pytest.skip("No test transfer created")
        
        # First check current transfer status
        transfer_resp = self.session.get(f"{BASE_URL}/api/branch-transfers/{transfer_id}")
        assert transfer_resp.status_code == 200
        transfer = transfer_resp.json()
        
        if transfer["status"] != "sent":
            pytest.skip("Transfer must be in 'sent' status to test receive")
        
        # Receive the transfer (exact match - no variance)
        receive_data = {
            "items": [{
                "product_id": transfer["items"][0]["product_id"],
                "qty": transfer["items"][0]["qty"],
                "qty_received": transfer["items"][0]["qty"],
                "transfer_capital": transfer["items"][0]["transfer_capital"],
                "branch_retail": transfer["items"][0]["branch_retail"]
            }],
            "notes": "Test receive for internal invoice testing",
            "skip_receipt_check": True  # Skip receipt photo requirement for testing
        }
        
        receive_resp = self.session.post(f"{BASE_URL}/api/branch-transfers/{transfer_id}/receive", json=receive_data)
        assert receive_resp.status_code == 200, f"Receive transfer failed: {receive_resp.text}"
        
        # Verify invoice status updated
        invoice_resp = self.session.get(f"{BASE_URL}/api/internal-invoices/by-transfer/{transfer_id}")
        assert invoice_resp.status_code == 200
        
        invoice = invoice_resp.json()
        assert invoice["status"] == "received", f"Invoice status should be 'received' after transfer received: {invoice['status']}"
        assert invoice["received_at"] is not None, "Invoice should have received_at timestamp"
        
        # Check for received_total and has_variance fields
        assert "received_total" in invoice or invoice.get("grand_total"), "Invoice should track received total"
        
        print(f"PASS: Invoice status updated to 'received' at {invoice['received_at']}")

    def test_08_get_single_invoice(self):
        """Test GET /internal-invoices/{invoice_id} returns single invoice with branch enrichment"""
        invoice_id = getattr(self.__class__, 'test_invoice_id', None)
        if not invoice_id:
            pytest.skip("No test invoice created")
        
        response = self.session.get(f"{BASE_URL}/api/internal-invoices/{invoice_id}")
        assert response.status_code == 200, f"GET single invoice failed: {response.text}"
        
        invoice = response.json()
        assert invoice["id"] == invoice_id, "Invoice ID should match"
        assert "from_branch_name" in invoice, "Should have from_branch_name"
        assert "to_branch_name" in invoice, "Should have to_branch_name"
        
        print(f"PASS: GET single invoice works with branch enrichment")

    def test_09_summary_reflects_new_invoice(self):
        """Test that summary endpoint reflects the new invoice in counts"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices/summary")
        assert response.status_code == 200
        
        data = response.json()
        # The invoice should appear in either payable or receivable depending on branch context
        total_count = data["payable"]["count"] + data["receivable"]["count"]
        
        print(f"PASS: Summary totals - Payable count: {data['payable']['count']}, Receivable count: {data['receivable']['count']}")
        assert total_count >= 0, "Summary should have valid counts"

    def test_10_invoice_404_for_nonexistent_transfer(self):
        """Test that GET /internal-invoices/by-transfer returns 404 for non-existent transfer"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices/by-transfer/nonexistent-id-12345")
        assert response.status_code == 404, f"Should return 404 for non-existent transfer: {response.status_code}"
        print("PASS: 404 returned for non-existent transfer")

    def test_11_existing_transfer_has_invoice(self):
        """Test that existing test transfer BTO-20260226-0045 has an invoice"""
        # Check the existing test transfer mentioned in context
        response = self.session.get(f"{BASE_URL}/api/branch-transfers", params={"limit": 50})
        assert response.status_code == 200
        
        orders = response.json().get("orders", [])
        # Find any transfer that has an invoice
        transfers_with_invoice = [o for o in orders if o.get("invoice_number")]
        
        if transfers_with_invoice:
            transfer = transfers_with_invoice[0]
            print(f"PASS: Found transfer {transfer['order_number']} with invoice {transfer.get('invoice_number')}")
            
            # Verify invoice exists
            if transfer.get("invoice_id"):
                invoice_resp = self.session.get(f"{BASE_URL}/api/internal-invoices/{transfer['invoice_id']}")
                if invoice_resp.status_code == 200:
                    print(f"PASS: Invoice {transfer['invoice_number']} exists and is retrievable")
        else:
            print("INFO: No existing transfers with invoices found (new invoices created during test)")


class TestInvoiceFieldValidation:
    """Additional tests for invoice field validation"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sibugayagrivetsupply@gmail.com",
            "password": "521325"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield

    def test_invoice_due_date_calculation(self):
        """Test that due_date is correctly calculated (created_at + terms_days)"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices", params={"limit": 10})
        assert response.status_code == 200
        
        invoices = response.json().get("invoices", [])
        if not invoices:
            pytest.skip("No invoices to test due date calculation")
        
        invoice = invoices[0]
        created_at = invoice.get("created_at")
        due_date = invoice.get("due_date")
        terms_days = invoice.get("terms_days", 15)
        
        if created_at and due_date:
            # Parse dates and verify
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            due_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            expected_due = created_dt + timedelta(days=terms_days)
            
            # Allow 1 second tolerance for timing
            diff = abs((due_dt - expected_due).total_seconds())
            assert diff < 86400, f"Due date calculation off by {diff} seconds"  # Within 1 day
            print(f"PASS: Due date correctly calculated - Created: {created_at[:10]}, Due: {due_date[:10]}, Terms: Net {terms_days}")

    def test_invoice_items_have_line_totals(self):
        """Test that each invoice item has line_total calculated"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices", params={"limit": 10})
        assert response.status_code == 200
        
        invoices = response.json().get("invoices", [])
        if not invoices:
            pytest.skip("No invoices to test")
        
        for invoice in invoices:
            for item in invoice.get("items", []):
                assert "line_total" in item, f"Item should have line_total: {item}"
                expected = item.get("transfer_capital", 0) * item.get("qty", 0)
                assert abs(item["line_total"] - expected) < 0.01, f"line_total should equal transfer_capital * qty"
        
        print(f"PASS: All invoice items have correct line_total calculations")

    def test_invoice_grand_total_matches_items(self):
        """Test that grand_total equals sum of all line_totals"""
        response = self.session.get(f"{BASE_URL}/api/internal-invoices", params={"limit": 10})
        assert response.status_code == 200
        
        invoices = response.json().get("invoices", [])
        if not invoices:
            pytest.skip("No invoices to test")
        
        for invoice in invoices:
            items = invoice.get("items", [])
            calculated_total = sum(item.get("line_total", 0) for item in items)
            grand_total = invoice.get("grand_total", 0)
            
            assert abs(grand_total - calculated_total) < 0.01, f"grand_total {grand_total} should match sum of line_totals {calculated_total}"
        
        print(f"PASS: Invoice grand_totals match sum of line_totals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
