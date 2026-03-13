"""
Test Phase 1 Print System: Business Info API and Settings
Tests for:
- GET /api/settings/business-info endpoint
- PUT /api/settings/business-info endpoint
- Business info fields: business_name, phone, address, TIN, trust_receipt_terms, receipt_footer
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestBusinessInfoEndpoint:
    """Test GET /api/settings/business-info endpoint"""

    def test_01_get_business_info_returns_200(self, auth_headers):
        """GET /api/settings/business-info should return 200"""
        response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/settings/business-info returns 200")

    def test_02_get_business_info_has_required_fields(self, auth_headers):
        """Business info response should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        required_fields = ["business_name", "phone", "address", "tin", "trust_receipt_terms", "receipt_footer"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            print(f"  - Field '{field}' present: {data[field][:50] if isinstance(data[field], str) and len(data[field]) > 50 else data[field]}")
        
        print("PASS: All required fields present in business info response")

    def test_03_get_business_info_trust_receipt_terms_present(self, auth_headers):
        """Verify trust_receipt_terms field is present and has content"""
        response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "trust_receipt_terms" in data, "trust_receipt_terms field missing"
        terms = data["trust_receipt_terms"]
        assert isinstance(terms, str), f"trust_receipt_terms should be string, got {type(terms)}"
        print(f"PASS: trust_receipt_terms present, length: {len(terms)} chars")


class TestBusinessInfoUpdate:
    """Test PUT /api/settings/business-info endpoint"""

    def test_04_update_business_info_returns_200(self, auth_headers):
        """PUT /api/settings/business-info should return success"""
        # First get current info to preserve existing data
        get_response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert get_response.status_code == 200
        current_data = get_response.json()
        
        # Update with test data
        update_payload = {
            "business_name": current_data.get("business_name") or "Test Business",
            "phone": current_data.get("phone") or "09123456789",
            "address": current_data.get("address") or "Test Address",
            "tin": current_data.get("tin") or "123-456-789-000",
            "trust_receipt_terms": current_data.get("trust_receipt_terms") or "Test terms",
            "receipt_footer": current_data.get("receipt_footer") or "Test footer"
        }
        
        response = requests.put(f"{BASE_URL}/api/settings/business-info", json=update_payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: PUT /api/settings/business-info returns 200")

    def test_05_update_business_info_persists_changes(self, auth_headers):
        """Verify that PUT changes persist via GET"""
        # Update business info
        test_footer = "TEST_FOOTER_PERSISTENCE_CHECK"
        
        # Get current data first
        get_current = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        current_data = get_current.json()
        
        update_payload = {
            "business_name": current_data.get("business_name") or "Test Business",
            "phone": current_data.get("phone") or "",
            "address": current_data.get("address") or "",
            "tin": current_data.get("tin") or "",
            "trust_receipt_terms": current_data.get("trust_receipt_terms") or "",
            "receipt_footer": test_footer
        }
        
        put_response = requests.put(f"{BASE_URL}/api/settings/business-info", json=update_payload, headers=auth_headers)
        assert put_response.status_code == 200
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["receipt_footer"] == test_footer, f"Expected '{test_footer}', got '{data['receipt_footer']}'"
        print("PASS: Business info changes persist correctly")
        
        # Restore original footer
        original_footer = current_data.get("receipt_footer", "This is not an official receipt.")
        restore_payload = {**update_payload, "receipt_footer": original_footer}
        requests.put(f"{BASE_URL}/api/settings/business-info", json=restore_payload, headers=auth_headers)

    def test_06_update_business_info_requires_business_name(self, auth_headers):
        """PUT should fail if business_name is empty"""
        update_payload = {
            "business_name": "",  # Empty name should fail
            "phone": "12345",
            "address": "Test",
            "tin": "Test",
            "trust_receipt_terms": "Test",
            "receipt_footer": "Test"
        }
        
        response = requests.put(f"{BASE_URL}/api/settings/business-info", json=update_payload, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400 for empty business_name, got {response.status_code}"
        print("PASS: PUT fails with 400 when business_name is empty")

    def test_07_update_trust_receipt_terms(self, auth_headers):
        """Verify trust_receipt_terms can be updated"""
        # Get current data
        get_current = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        current_data = get_current.json()
        
        test_terms = "TEST_TRUST_RECEIPT_TERMS_UPDATE"
        update_payload = {
            "business_name": current_data.get("business_name") or "Test Business",
            "phone": current_data.get("phone") or "",
            "address": current_data.get("address") or "",
            "tin": current_data.get("tin") or "",
            "trust_receipt_terms": test_terms,
            "receipt_footer": current_data.get("receipt_footer") or ""
        }
        
        put_response = requests.put(f"{BASE_URL}/api/settings/business-info", json=update_payload, headers=auth_headers)
        assert put_response.status_code == 200
        
        # Verify
        get_response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        data = get_response.json()
        
        assert data["trust_receipt_terms"] == test_terms, f"Expected '{test_terms}', got '{data['trust_receipt_terms']}'"
        print("PASS: trust_receipt_terms can be updated")
        
        # Restore original
        original_terms = current_data.get("trust_receipt_terms", "")
        restore_payload = {**update_payload, "trust_receipt_terms": original_terms}
        requests.put(f"{BASE_URL}/api/settings/business-info", json=restore_payload, headers=auth_headers)


class TestInvoicesEndpointForQuickActions:
    """Test /api/invoices endpoint to verify data available for Quick Actions menu"""

    def test_08_get_invoices_returns_list(self, auth_headers):
        """GET /api/invoices should return invoices list"""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "invoices" in data, "Response should have 'invoices' key"
        assert "total" in data, "Response should have 'total' key"
        print(f"PASS: GET /api/invoices returns {len(data['invoices'])} invoices, total: {data['total']}")

    def test_09_invoice_has_fields_for_print(self, auth_headers):
        """Verify invoice data has fields needed for printing"""
        response = requests.get(f"{BASE_URL}/api/invoices?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["invoices"]) > 0:
            invoice = data["invoices"][0]
            # Fields needed for print engine (sale_type is the payment type field)
            print_fields = ["invoice_number", "customer_name", "grand_total", "items", "sale_type", "status"]
            for field in print_fields:
                assert field in invoice, f"Invoice missing '{field}' field"
            print(f"PASS: Invoice has all required print fields. Invoice #: {invoice.get('invoice_number')}, Sale Type: {invoice.get('sale_type')}")
        else:
            print("SKIP: No invoices to test")

    def test_10_invoice_has_balance_for_add_payment(self, auth_headers):
        """Verify invoice data has balance field for Add Payment action"""
        response = requests.get(f"{BASE_URL}/api/invoices?status=open&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["invoices"]) > 0:
            invoice = data["invoices"][0]
            assert "balance" in invoice, "Invoice should have 'balance' field for Add Payment"
            print(f"PASS: Invoice has 'balance' field. Balance: {invoice.get('balance')}")
        else:
            print("SKIP: No open invoices to test")


class TestQuickActionEndpoints:
    """Test endpoints used by Quick Action menu"""

    def test_11_get_single_invoice_detail(self, auth_headers):
        """GET /api/invoices/{id} should return invoice detail for View Details action"""
        # First get list to get an ID
        list_response = requests.get(f"{BASE_URL}/api/invoices?limit=1", headers=auth_headers)
        assert list_response.status_code == 200
        invoices = list_response.json().get("invoices", [])
        
        if len(invoices) > 0:
            invoice_id = invoices[0]["id"]
            detail_response = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
            assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}"
            
            invoice = detail_response.json()
            assert "invoice_number" in invoice, "Detail should have invoice_number"
            assert "items" in invoice, "Detail should have items"
            print(f"PASS: GET /api/invoices/{invoice_id} returns invoice detail")
        else:
            print("SKIP: No invoices to test detail endpoint")

    def test_12_business_info_available_for_printing(self, auth_headers):
        """Verify business info is loaded for PrintEngine usage"""
        response = requests.get(f"{BASE_URL}/api/settings/business-info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # PrintEngine needs these fields
        assert "business_name" in data, "Missing business_name for printing"
        assert "trust_receipt_terms" in data, "Missing trust_receipt_terms for Trust Receipt"
        assert "receipt_footer" in data, "Missing receipt_footer for Order Slip"
        
        print(f"PASS: Business info ready for printing. Business: {data.get('business_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
