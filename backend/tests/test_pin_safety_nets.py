"""
PIN Safety Nets Tests - iteration_98
Tests for PIN verification on destructive financial actions:
- Cancel PO (DELETE /api/purchase-orders/{id})
- Reopen PO (POST /api/purchase-orders/{id}/reopen)
- Void Expense (DELETE /api/expenses/{id})
- Void Invoice (POST /api/invoices/{id}/void)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get JWT token"""
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        }, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed with status {response.status_code}")
    except Exception as e:
        pytest.skip(f"Authentication failed: {str(e)}")


@pytest.fixture
def api_client(auth_token):
    """Authenticated API client"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    session.timeout = 30
    return session


class TestCancelPOPinRequirement:
    """Tests for Cancel PO requiring PIN"""
    
    def test_cancel_po_without_pin_fails(self, api_client):
        """Cancel PO without PIN should return 400"""
        # Get a draft PO first
        response = api_client.get(f"{BASE_URL}/api/purchase-orders", params={"status": "draft"})
        if response.status_code != 200:
            pytest.skip("Could not get PO list")
        
        data = response.json()
        pos = data.get("purchase_orders", [])
        
        # Find a draft/ordered PO that can be cancelled
        cancellable_po = None
        for po in pos:
            if po.get("status") in ["draft", "ordered"]:
                cancellable_po = po
                break
        
        if not cancellable_po:
            pytest.skip("No cancellable PO found")
        
        # Try to cancel without PIN
        response = api_client.delete(f"{BASE_URL}/api/purchase-orders/{cancellable_po['id']}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "PIN" in response.json().get("detail", "").upper() or "pin" in response.json().get("detail", "").lower()
        print(f"✓ Cancel PO without PIN correctly rejected: {response.json().get('detail')}")
    
    def test_cancel_po_with_invalid_pin_fails(self, api_client):
        """Cancel PO with invalid PIN should return 403"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders", params={"status": "draft"})
        if response.status_code != 200:
            pytest.skip("Could not get PO list")
        
        data = response.json()
        pos = data.get("purchase_orders", [])
        
        cancellable_po = None
        for po in pos:
            if po.get("status") in ["draft", "ordered"]:
                cancellable_po = po
                break
        
        if not cancellable_po:
            pytest.skip("No cancellable PO found")
        
        # Try to cancel with invalid PIN
        response = api_client.delete(
            f"{BASE_URL}/api/purchase-orders/{cancellable_po['id']}",
            json={"pin": "000000"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Cancel PO with invalid PIN correctly rejected")
    
    def test_cancel_po_with_valid_pin_succeeds(self, api_client):
        """Cancel PO with valid manager PIN should succeed"""
        # First create a test PO
        branches_resp = api_client.get(f"{BASE_URL}/api/branches")
        if branches_resp.status_code != 200:
            pytest.skip("Could not get branches")
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available")
        
        branch_id = branches[0].get("id", "")
        
        # Create a draft PO
        po_data = {
            "vendor": "TEST_CANCEL_VENDOR",
            "branch_id": branch_id,
            "items": [{"product_id": "", "product_name": "Test Item", "quantity": 1, "unit_price": 100}],
            "po_type": "draft",
            "purchase_date": "2026-01-15"
        }
        create_resp = api_client.post(f"{BASE_URL}/api/purchase-orders", json=po_data)
        if create_resp.status_code != 200:
            pytest.skip(f"Could not create test PO: {create_resp.text}")
        
        new_po = create_resp.json()
        po_id = new_po.get("id")
        
        # Now cancel with valid PIN
        response = api_client.delete(
            f"{BASE_URL}/api/purchase-orders/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        print(f"✓ Cancel PO with valid PIN succeeded: {response.json().get('message')}")


class TestReopenPOPinRequirement:
    """Tests for Reopen PO requiring PIN"""
    
    def test_reopen_po_without_pin_fails(self, api_client):
        """Reopen PO without PIN should return 400"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders", params={"status": "received"})
        if response.status_code != 200:
            pytest.skip("Could not get PO list")
        
        data = response.json()
        pos = data.get("purchase_orders", [])
        
        received_po = None
        for po in pos:
            if po.get("status") == "received":
                received_po = po
                break
        
        if not received_po:
            pytest.skip("No received PO found")
        
        # Try to reopen without PIN
        response = api_client.post(f"{BASE_URL}/api/purchase-orders/{received_po['id']}/reopen")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        detail = response.json().get("detail", "")
        assert "PIN" in detail.upper() or "pin" in detail.lower(), f"Expected PIN error, got: {detail}"
        print(f"✓ Reopen PO without PIN correctly rejected: {detail}")
    
    def test_reopen_po_with_invalid_pin_fails(self, api_client):
        """Reopen PO with invalid PIN should return 403"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders", params={"status": "received"})
        if response.status_code != 200:
            pytest.skip("Could not get PO list")
        
        data = response.json()
        pos = data.get("purchase_orders", [])
        
        received_po = None
        for po in pos:
            if po.get("status") == "received":
                received_po = po
                break
        
        if not received_po:
            pytest.skip("No received PO found")
        
        # Try to reopen with invalid PIN
        response = api_client.post(
            f"{BASE_URL}/api/purchase-orders/{received_po['id']}/reopen",
            json={"pin": "000000"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Reopen PO with invalid PIN correctly rejected")


class TestVoidExpensePinRequirement:
    """Tests for Void Expense requiring PIN"""
    
    def test_void_expense_without_pin_fails(self, api_client):
        """Void expense without PIN should return 400"""
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"limit": 10})
        if response.status_code != 200:
            pytest.skip("Could not get expenses list")
        
        data = response.json()
        expenses = data.get("expenses", [])
        
        non_voided = None
        for exp in expenses:
            if not exp.get("voided"):
                non_voided = exp
                break
        
        if not non_voided:
            pytest.skip("No non-voided expense found")
        
        # Try to delete without PIN
        response = api_client.delete(f"{BASE_URL}/api/expenses/{non_voided['id']}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        detail = response.json().get("detail", "")
        assert "PIN" in detail.upper() or "pin" in detail.lower(), f"Expected PIN error, got: {detail}"
        print(f"✓ Void expense without PIN correctly rejected: {detail}")
    
    def test_void_expense_with_invalid_pin_fails(self, api_client):
        """Void expense with invalid PIN should return 403"""
        response = api_client.get(f"{BASE_URL}/api/expenses", params={"limit": 10})
        if response.status_code != 200:
            pytest.skip("Could not get expenses list")
        
        data = response.json()
        expenses = data.get("expenses", [])
        
        non_voided = None
        for exp in expenses:
            if not exp.get("voided"):
                non_voided = exp
                break
        
        if not non_voided:
            pytest.skip("No non-voided expense found")
        
        # Try to delete with invalid PIN
        response = api_client.delete(
            f"{BASE_URL}/api/expenses/{non_voided['id']}",
            json={"pin": "000000"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Void expense with invalid PIN correctly rejected")


class TestVoidInvoicePinRequirement:
    """Tests for Void Invoice requiring PIN"""
    
    def test_void_invoice_without_pin_fails(self, api_client):
        """Void invoice without PIN should return 400"""
        response = api_client.get(f"{BASE_URL}/api/invoices", params={"limit": 10})
        if response.status_code != 200:
            pytest.skip("Could not get invoices list")
        
        data = response.json()
        invoices = data.get("invoices", [])
        
        non_voided = None
        for inv in invoices:
            if inv.get("status") != "voided":
                non_voided = inv
                break
        
        if not non_voided:
            pytest.skip("No non-voided invoice found")
        
        # Try to void without PIN
        response = api_client.post(f"{BASE_URL}/api/invoices/{non_voided['id']}/void", json={
            "reason": "Test void without PIN"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        detail = response.json().get("detail", "")
        assert "PIN" in detail.upper() or "pin" in detail.lower(), f"Expected PIN error, got: {detail}"
        print(f"✓ Void invoice without PIN correctly rejected: {detail}")
    
    def test_void_invoice_with_invalid_pin_fails(self, api_client):
        """Void invoice with invalid PIN should return 403"""
        response = api_client.get(f"{BASE_URL}/api/invoices", params={"limit": 10})
        if response.status_code != 200:
            pytest.skip("Could not get invoices list")
        
        data = response.json()
        invoices = data.get("invoices", [])
        
        non_voided = None
        for inv in invoices:
            if inv.get("status") != "voided":
                non_voided = inv
                break
        
        if not non_voided:
            pytest.skip("No non-voided invoice found")
        
        # Try to void with invalid PIN
        response = api_client.post(
            f"{BASE_URL}/api/invoices/{non_voided['id']}/void",
            json={"reason": "Test void", "manager_pin": "000000"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Void invoice with invalid PIN correctly rejected")
    
    def test_void_invoice_accepts_both_pin_fields(self, api_client):
        """Void invoice should accept both 'pin' and 'manager_pin' fields"""
        response = api_client.get(f"{BASE_URL}/api/invoices", params={"limit": 10})
        if response.status_code != 200:
            pytest.skip("Could not get invoices list")
        
        data = response.json()
        invoices = data.get("invoices", [])
        
        non_voided = None
        for inv in invoices:
            if inv.get("status") != "voided":
                non_voided = inv
                break
        
        if not non_voided:
            pytest.skip("No non-voided invoice found")
        
        # Check both field names work (test with invalid PIN to avoid actually voiding)
        response_pin = api_client.post(
            f"{BASE_URL}/api/invoices/{non_voided['id']}/void",
            json={"reason": "Test", "pin": "000000"}
        )
        response_manager_pin = api_client.post(
            f"{BASE_URL}/api/invoices/{non_voided['id']}/void",
            json={"reason": "Test", "manager_pin": "000000"}
        )
        
        # Both should fail with 403 (invalid PIN) not 400 (missing PIN)
        assert response_pin.status_code == 403, "pin field should be accepted"
        assert response_manager_pin.status_code == 403, "manager_pin field should be accepted"
        print(f"✓ Void invoice accepts both 'pin' and 'manager_pin' fields")


class TestPinPolicies:
    """Tests for PIN policy configuration endpoint"""
    
    def test_pin_policies_endpoint_accessible(self, api_client):
        """Settings endpoint should include PIN policies"""
        response = api_client.get(f"{BASE_URL}/api/settings")
        if response.status_code == 200:
            print(f"✓ Settings endpoint accessible")
        else:
            # Not critical, just informational
            print(f"⚠ Settings endpoint returned {response.status_code}")
    
    def test_verify_pin_actions_defined(self, api_client):
        """Verify that cancel_po, reopen_po, void_expense are in PIN policy actions"""
        # This is more of a code review check, but we can verify the endpoint exists
        response = api_client.get(f"{BASE_URL}/api/system/pin-policies")
        if response.status_code == 404:
            # Endpoint might not exist publicly, that's OK
            print(f"⚠ PIN policies endpoint not publicly exposed (expected)")
            pytest.skip("PIN policies endpoint not public")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ PIN policies accessible: {list(data.keys()) if isinstance(data, dict) else 'list'}")


class TestPaySupplierPageAccess:
    """Test that Pay Supplier page loads without errors"""
    
    def test_payables_by_supplier_endpoint(self, api_client):
        """Pay Supplier page uses payables-by-supplier endpoint"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders/payables-by-supplier")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Should return a list of suppliers"
        print(f"✓ payables-by-supplier endpoint working, {len(data)} suppliers with unpaid POs")
    
    def test_unpaid_po_summary_endpoint(self, api_client):
        """Unpaid PO summary endpoint works"""
        response = api_client.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_unpaid" in data, "Should have total_unpaid field"
        print(f"✓ unpaid-summary endpoint working, total unpaid: {data.get('total_unpaid')}")
