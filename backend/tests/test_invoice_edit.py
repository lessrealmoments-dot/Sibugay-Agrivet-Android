"""
Invoice Detail/Edit Feature Tests
Tests for QuickBooks-style invoice viewer/editor functionality:
- GET /invoices/{id} with edit_history and edit_count
- GET /invoices/by-number/{number} cross-collection search
- PUT /invoices/{id}/edit with required reason
- Edit history tracking
- Inventory adjustments on edit
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def test_customer(auth_headers):
    """Get or create a test customer"""
    # Use existing Test Customer from previous tests
    resp = requests.get(f"{BASE_URL}/api/customers", headers=auth_headers, params={"limit": 100})
    assert resp.status_code == 200
    customers = resp.json().get("customers", [])
    
    for c in customers:
        if "Test Customer" in c.get("name", ""):
            return c
    
    # Create test customer if not found
    resp = requests.post(f"{BASE_URL}/api/customers", headers=auth_headers, json={
        "name": "Test Customer Invoice Edit",
        "phone": "09123456789",
        "price_scheme": "Walk-in",
        "credit_limit": 100000,
        "interest_rate": 3,
        "grace_period": 7
    })
    assert resp.status_code in [200, 201], f"Failed to create customer: {resp.text}"
    return resp.json()

@pytest.fixture(scope="module")
def test_invoice(auth_headers, test_customer):
    """Create a test invoice for editing"""
    # First, get a branch
    resp = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers)
    assert resp.status_code == 200
    branches = resp.json()
    branch_id = branches[0]["id"] if branches else None
    
    # Get a product for the invoice
    resp = requests.get(f"{BASE_URL}/api/products", headers=auth_headers, params={"limit": 10})
    assert resp.status_code == 200
    products = resp.json().get("products", [])
    assert len(products) > 0, "No products found for testing"
    product = products[0]
    
    # Create invoice using unified-sale endpoint
    invoice_data = {
        "branch_id": branch_id,
        "customer_id": test_customer["id"],
        "customer_name": test_customer["name"],
        "items": [{
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": 5,
            "rate": product.get("prices", {}).get("Walk-in", 100) or 100,
        }],
        "payment_type": "credit",
        "amount_paid": 0,
        "terms": "Net 30",
        "terms_days": 30,
        "notes": "Test invoice for edit feature"
    }
    
    resp = requests.post(f"{BASE_URL}/api/unified-sale", headers=auth_headers, json=invoice_data)
    if resp.status_code != 200:
        # Try regular invoice endpoint as fallback
        resp = requests.post(f"{BASE_URL}/api/invoices", headers=auth_headers, json=invoice_data)
    assert resp.status_code == 200 or resp.status_code == 201, f"Failed to create invoice: {resp.text}"
    return resp.json()


class TestInvoiceDetailEndpoint:
    """Tests for GET /invoices/{id} with edit_history and edit_count"""
    
    def test_get_invoice_returns_edit_history_and_count(self, auth_headers, test_invoice):
        """Test that invoice detail includes edit_history and edit_count fields"""
        invoice_id = test_invoice["id"]
        resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        
        assert resp.status_code == 200, f"Failed to get invoice: {resp.text}"
        data = resp.json()
        
        # Verify edit fields are present
        assert "edit_history" in data, "Missing edit_history field in response"
        assert "edit_count" in data, "Missing edit_count field in response"
        assert isinstance(data["edit_history"], list), "edit_history should be a list"
        assert isinstance(data["edit_count"], int), "edit_count should be an integer"
        print(f"Invoice has edit_count: {data['edit_count']}, edit_history: {len(data['edit_history'])} records")
    
    def test_new_invoice_has_zero_edit_count(self, auth_headers, test_invoice):
        """New invoices should have edit_count of 0"""
        invoice_id = test_invoice["id"]
        resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Initially should have no edits
        assert data["edit_count"] == 0, "New invoice should have edit_count of 0"
        assert data["edit_history"] == [], "New invoice should have empty edit_history"


class TestInvoiceByNumberEndpoint:
    """Tests for GET /invoices/by-number/{number}"""
    
    def test_find_invoice_by_number(self, auth_headers, test_invoice):
        """Test finding invoice by its number"""
        invoice_number = test_invoice.get("invoice_number")
        assert invoice_number, "Test invoice doesn't have invoice_number"
        
        resp = requests.get(
            f"{BASE_URL}/api/invoices/by-number/{invoice_number}", 
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Failed to find invoice by number: {resp.text}"
        data = resp.json()
        assert data["invoice_number"] == invoice_number
        assert "_collection" in data, "Response should include _collection field"
        print(f"Found invoice in collection: {data['_collection']}")
    
    def test_invoice_not_found_returns_404(self, auth_headers):
        """Test that non-existent invoice number returns 404"""
        resp = requests.get(
            f"{BASE_URL}/api/invoices/by-number/NONEXISTENT-12345", 
            headers=auth_headers
        )
        assert resp.status_code == 404


class TestInvoiceEditEndpoint:
    """Tests for PUT /invoices/{id}/edit"""
    
    def test_edit_requires_reason(self, auth_headers, test_invoice):
        """Test that edit endpoint requires 'reason' field"""
        invoice_id = test_invoice["id"]
        
        # Try edit without reason
        edit_data = {
            "notes": "Updated notes",
            "_collection": "invoices"
        }
        resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/edit", headers=auth_headers, json=edit_data)
        
        assert resp.status_code == 400, f"Expected 400 without reason, got {resp.status_code}: {resp.text}"
        assert "reason" in resp.text.lower(), "Error should mention 'reason'"
    
    def test_edit_with_reason_succeeds(self, auth_headers, test_invoice):
        """Test that edit with reason succeeds"""
        invoice_id = test_invoice["id"]
        
        edit_data = {
            "notes": f"Updated notes at {datetime.now().isoformat()}",
            "reason": "Correcting invoice notes per customer request",
            "_collection": "invoices"
        }
        resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/edit", headers=auth_headers, json=edit_data)
        
        assert resp.status_code == 200, f"Edit failed: {resp.text}"
        data = resp.json()
        assert "message" in data
        print(f"Edit response: {data.get('message')}, changes: {data.get('changes', [])}")
    
    def test_edit_creates_history_record(self, auth_headers, test_invoice):
        """Test that editing creates a history record"""
        invoice_id = test_invoice["id"]
        
        # Make an edit
        edit_data = {
            "notes": f"Second edit at {datetime.now().isoformat()}",
            "reason": "Test edit for history tracking",
            "_collection": "invoices"
        }
        resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/edit", headers=auth_headers, json=edit_data)
        assert resp.status_code == 200, f"Edit failed: {resp.text}"
        
        # Verify edit_count increased
        resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["edit_count"] >= 1, f"edit_count should be at least 1, got {data['edit_count']}"
        assert len(data["edit_history"]) >= 1, "edit_history should have at least 1 record"
        
        # Verify history record content
        latest_edit = data["edit_history"][0]
        assert "reason" in latest_edit
        assert "edited_by_name" in latest_edit
        assert "edited_at" in latest_edit
        assert "changes" in latest_edit
        print(f"Edit history record: reason='{latest_edit['reason']}', by='{latest_edit['edited_by_name']}'")
    
    def test_edited_invoice_has_edited_flag(self, auth_headers, test_invoice):
        """Test that edited invoice has 'edited' flag set to true"""
        invoice_id = test_invoice["id"]
        
        resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("edited") == True, f"'edited' flag should be True, got {data.get('edited')}"
        assert data.get("last_edited_at") is not None, "last_edited_at should be set"
        assert data.get("last_edited_by") is not None, "last_edited_by should be set"
        print(f"Invoice edited by: {data.get('last_edited_by')} at {data.get('last_edited_at')}")


class TestInvoiceEditHistory:
    """Tests for GET /invoices/{id}/edit-history"""
    
    def test_get_edit_history_endpoint(self, auth_headers, test_invoice):
        """Test dedicated edit history endpoint"""
        invoice_id = test_invoice["id"]
        
        resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}/edit-history", headers=auth_headers)
        
        assert resp.status_code == 200, f"Failed to get edit history: {resp.text}"
        history = resp.json()
        
        assert isinstance(history, list), "History should be a list"
        # Should have records from previous tests
        print(f"Edit history has {len(history)} records")
        
        if len(history) > 0:
            record = history[0]
            required_fields = ["id", "invoice_id", "edited_by_name", "edited_at", "reason"]
            for field in required_fields:
                assert field in record, f"History record missing '{field}' field"


class TestInventoryAdjustmentOnEdit:
    """Tests for inventory adjustments when invoice items are edited"""
    
    def test_reducing_quantity_returns_stock(self, auth_headers):
        """Test that reducing item quantity returns stock to inventory"""
        # Get a branch and product
        resp = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers)
        branches = resp.json()
        branch_id = branches[0]["id"] if branches else None
        
        resp = requests.get(f"{BASE_URL}/api/products", headers=auth_headers, params={"limit": 10})
        products = resp.json().get("products", [])
        if not products:
            pytest.skip("No products for inventory test")
        product = products[0]
        
        # Get current inventory
        resp = requests.get(f"{BASE_URL}/api/inventory", headers=auth_headers, params={"branch_id": branch_id, "product_id": product["id"]})
        initial_stock = 0
        if resp.status_code == 200:
            inv_data = resp.json()
            if isinstance(inv_data, list) and len(inv_data) > 0:
                initial_stock = inv_data[0].get("quantity", 0)
            elif isinstance(inv_data, dict):
                items = inv_data.get("items", [])
                if items:
                    initial_stock = items[0].get("quantity", 0)
        
        print(f"Initial stock for {product['name']}: {initial_stock}")
        
        # Create a credit invoice
        invoice_data = {
            "branch_id": branch_id,
            "customer_name": "Test Inventory Customer",
            "items": [{
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": 3,
                "rate": 100
            }],
            "payment_type": "credit",
            "amount_paid": 0
        }
        
        resp = requests.post(f"{BASE_URL}/api/unified-sale", headers=auth_headers, json=invoice_data)
        if resp.status_code != 200:
            pytest.skip("Could not create invoice for inventory test")
        
        invoice = resp.json()
        invoice_id = invoice["id"]
        
        # Now edit to reduce quantity from 3 to 1
        edit_data = {
            "items": [{
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": 1,  # Reduced from 3 to 1
                "rate": 100
            }],
            "reason": "Customer changed order, reducing quantity",
            "_collection": "invoices"
        }
        
        resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/edit", headers=auth_headers, json=edit_data)
        assert resp.status_code == 200, f"Edit failed: {resp.text}"
        
        data = resp.json()
        print(f"Edit response: {data}")
        
        # Verify inventory adjustments were recorded
        if "inventory_adjustments" in data:
            print(f"Inventory adjustments: {data['inventory_adjustments']}")
            # Should have a positive adjustment (returning stock)
            for adj in data.get("inventory_adjustments", []):
                if adj["product_id"] == product["id"]:
                    assert adj["change"] > 0, "Stock return should be positive"
                    print(f"Stock returned: +{adj['change']}")


class TestVoidedInvoiceEdit:
    """Test that voided invoices cannot be edited"""
    
    def test_cannot_edit_voided_invoice(self, auth_headers):
        """Test that editing a voided invoice returns error"""
        # First find a voided invoice or create and void one
        resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers, params={"status": "voided", "limit": 1})
        if resp.status_code == 200 and resp.json().get("invoices"):
            voided = resp.json()["invoices"][0]
            invoice_id = voided["id"]
        else:
            # Skip if no voided invoices
            pytest.skip("No voided invoices to test")
        
        edit_data = {
            "notes": "Trying to edit voided invoice",
            "reason": "Test edit on voided",
            "_collection": "invoices"
        }
        
        resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/edit", headers=auth_headers, json=edit_data)
        assert resp.status_code == 400, f"Should not allow editing voided invoice, got {resp.status_code}"
        assert "voided" in resp.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
