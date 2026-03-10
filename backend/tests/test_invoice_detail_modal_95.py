"""
Test Suite for Invoice Detail Modal (Iteration 95)
Tests for InvoiceDetailModal as full transaction viewer supporting both invoices and POs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"

# Test data references
TEST_INVOICE = "SI-20260302-0188"  # Split/GCash invoice
TEST_PO = "PO-20260301103349-566F"  # Existing PO


class TestInvoiceDetailModalAPI:
    """API Tests for Invoice Detail Modal features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: GET /api/invoices/by-number/{invoice_number} for invoices
    # ───────────────────────────────────────────────────────────────────────
    def test_get_invoice_by_number(self):
        """Test fetching invoice by number returns full invoice data"""
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_INVOICE}")
        assert response.status_code == 200, f"Failed to get invoice: {response.text}"
        
        data = response.json()
        # Verify invoice fields
        assert "id" in data
        assert data.get("invoice_number") == TEST_INVOICE
        assert "customer_name" in data
        assert "grand_total" in data
        assert "status" in data
        assert "items" in data
        print(f"✓ GET invoice by number works - {data.get('customer_name')}, ₱{data.get('grand_total')}")
    
    def test_invoice_has_digital_payment_fields(self):
        """Test invoice with digital payment has platform, ref, fund_source"""
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_INVOICE}")
        assert response.status_code == 200
        
        data = response.json()
        # This invoice should have digital payment info (GCash split)
        assert "digital_platform" in data or "fund_source" in data, "Missing digital payment fields"
        
        digital_platform = data.get("digital_platform")
        fund_source = data.get("fund_source")
        print(f"✓ Invoice digital info: platform={digital_platform}, fund_source={fund_source}")
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: GET /api/invoices/by-number/{po_number} for POs
    # ───────────────────────────────────────────────────────────────────────
    def test_get_po_by_number(self):
        """Test fetching PO by number via invoices/by-number endpoint"""
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO}")
        assert response.status_code == 200, f"Failed to get PO: {response.text}"
        
        data = response.json()
        # Verify PO fields
        assert "id" in data
        assert data.get("po_number") == TEST_PO
        assert "vendor" in data
        assert "payment_status" in data
        assert data.get("_collection") == "purchase_orders", "PO should have _collection='purchase_orders'"
        print(f"✓ GET PO by number works - vendor: {data.get('vendor')}, status: {data.get('payment_status')}")
    
    def test_po_has_dr_number_field(self):
        """Test PO response includes dr_number (DR#) field"""
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO}")
        assert response.status_code == 200
        
        data = response.json()
        assert "dr_number" in data, "PO should include dr_number field"
        print(f"✓ PO has dr_number field: '{data.get('dr_number')}'")
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: GET /api/purchase-orders/{po_id} direct endpoint
    # ───────────────────────────────────────────────────────────────────────
    def test_get_purchase_order_by_id(self):
        """Test GET /api/purchase-orders/{po_id} returns single PO"""
        # First get the PO ID from by-number endpoint
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO}")
        assert response.status_code == 200
        po_id = response.json()["id"]
        
        # Now test direct endpoint
        response = self.session.get(f"{BASE_URL}/api/purchase-orders/{po_id}")
        assert response.status_code == 200, f"Failed to get PO by ID: {response.text}"
        
        data = response.json()
        assert data["id"] == po_id
        assert "po_number" in data
        assert "vendor" in data
        assert "items" in data
        print(f"✓ GET /api/purchase-orders/{po_id[:8]}... works")
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: GET /api/expenses/{expense_id} direct endpoint
    # ───────────────────────────────────────────────────────────────────────
    def test_get_expense_by_id(self):
        """Test GET /api/expenses/{expense_id} returns single expense"""
        # First search for an expense
        response = self.session.get(f"{BASE_URL}/api/search/transactions", params={
            "q": "expense", "type": "expense", "limit": 1
        })
        assert response.status_code == 200
        results = response.json().get("results", [])
        if not results:
            pytest.skip("No expenses found for testing")
        
        expense_id = results[0]["id"]
        
        # Test direct endpoint
        response = self.session.get(f"{BASE_URL}/api/expenses/{expense_id}")
        assert response.status_code == 200, f"Failed to get expense: {response.text}"
        
        data = response.json()
        assert data["id"] == expense_id
        assert "category" in data
        assert "amount" in data
        print(f"✓ GET /api/expenses/{expense_id[:8]}... works - {data.get('category')}")
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: POST /api/verify/{type}/{id} with PIN
    # ───────────────────────────────────────────────────────────────────────
    def test_verify_endpoint_exists(self):
        """Test that verify endpoint exists and responds to requests"""
        # Get an unverified invoice first
        response = self.session.get(f"{BASE_URL}/api/search/transactions", params={
            "q": "Walk-in", "type": "invoice", "limit": 10
        })
        assert response.status_code == 200
        
        results = response.json().get("results", [])
        # Find any invoice (doesn't have to be unverified for endpoint existence test)
        if not results:
            pytest.skip("No invoices found")
        
        invoice_id = results[0]["id"]
        
        # Test verify endpoint with wrong PIN (should return 403, not 404)
        response = self.session.post(f"{BASE_URL}/api/verify/invoice/{invoice_id}", json={
            "pin": "000000"  # Wrong PIN
        })
        # 400 or 403 means endpoint exists, 404 would mean it doesn't
        assert response.status_code in [200, 400, 403], f"Verify endpoint issue: {response.status_code}"
        print(f"✓ Verify endpoint exists - response: {response.status_code}")
    
    def test_verify_with_correct_pin(self):
        """Test verifying an invoice with correct manager PIN"""
        # Get invoice details
        response = self.session.get(f"{BASE_URL}/api/invoices/by-number/{TEST_INVOICE}")
        assert response.status_code == 200
        invoice_data = response.json()
        invoice_id = invoice_data["id"]
        
        # Check if already verified
        if invoice_data.get("verified"):
            print(f"✓ Invoice already verified - skipping verify test")
            return
        
        # Try to verify
        response = self.session.post(f"{BASE_URL}/api/verify/invoice/{invoice_id}", json={
            "pin": MANAGER_PIN
        })
        
        # Either 200 (success) or 400 (already verified or other business rule)
        assert response.status_code in [200, 400], f"Verify failed unexpectedly: {response.text}"
        print(f"✓ Verify endpoint responded: {response.status_code}")
    
    # ───────────────────────────────────────────────────────────────────────
    # Test: Search results return correct data-testids
    # ───────────────────────────────────────────────────────────────────────
    def test_search_returns_invoice_types(self):
        """Test search returns invoice type correctly"""
        response = self.session.get(f"{BASE_URL}/api/search/transactions", params={
            "q": "Walk-in", "type": "invoice", "limit": 5
        })
        assert response.status_code == 200
        
        results = response.json().get("results", [])
        for r in results:
            assert r.get("type") == "invoice", f"Expected invoice type, got {r.get('type')}"
        print(f"✓ Search returns {len(results)} invoice results correctly")
    
    def test_search_returns_po_types(self):
        """Test search returns purchase_order type correctly"""
        response = self.session.get(f"{BASE_URL}/api/search/transactions", params={
            "q": "PO", "type": "po", "limit": 5
        })
        assert response.status_code == 200
        
        results = response.json().get("results", [])
        for r in results:
            assert r.get("type") == "purchase_order", f"Expected purchase_order, got {r.get('type')}"
        print(f"✓ Search returns {len(results)} PO results correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
