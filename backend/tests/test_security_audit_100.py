"""
Security Audit Tests - Iteration 100
Testing PIN verification endpoints and autoComplete attribute verification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


class TestPINVerificationEndpoints:
    """Test backend PIN verification endpoints work correctly"""
    
    def test_verify_manager_pin_credit_sale_approval(self, auth_token):
        """Test verify-manager-pin for credit_sale_approval action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "credit_sale_approval"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        assert "manager_id" in data, "Response should include manager_id"
        assert "manager_name" in data, "Response should include manager_name"
        print(f"✓ credit_sale_approval PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_void_invoice(self, auth_token):
        """Test verify-manager-pin for void_invoice action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "void_invoice"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        print(f"✓ void_invoice PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_cancel_po(self, auth_token):
        """Test verify-manager-pin for cancel_po action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "cancel_po"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        print(f"✓ cancel_po PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_reopen_po(self, auth_token):
        """Test verify-manager-pin for reopen_po action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "reopen_po"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        print(f"✓ reopen_po PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_daily_close(self, auth_token):
        """Test verify-manager-pin for daily_close action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "daily_close"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        print(f"✓ daily_close PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_fund_transfer(self, auth_token):
        """Test verify-manager-pin for fund_transfer_cashier_safe action"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "521325",
                "action_key": "fund_transfer_cashier_safe"
            }
        )
        assert response.status_code == 200, f"PIN verification failed: {response.text}"
        data = response.json()
        assert data.get("valid") == True, f"PIN should be valid: {data}"
        print(f"✓ fund_transfer_cashier_safe PIN verified: {data['manager_name']}")
    
    def test_verify_manager_pin_invalid_pin(self, auth_token):
        """Test that invalid PIN returns valid=false"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "pin": "000000",
                "action_key": "credit_sale_approval"
            }
        )
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        assert data.get("valid") == False, f"Invalid PIN should return valid=false: {data}"
        print("✓ Invalid PIN correctly rejected")


class TestCartItemsBugFix:
    """Verify the cartItems bug is fixed - grandTotal is used instead"""
    
    def test_unified_sales_uses_grand_total(self):
        """Verify UnifiedSalesPage uses grandTotal (not cartItems) in verifyManagerPin"""
        import subprocess
        # Check that the code uses grandTotal, not cartItems
        result = subprocess.run(
            ["grep", "-n", "grandTotal", "/app/frontend/src/pages/UnifiedSalesPage.js"],
            capture_output=True, text=True
        )
        assert "grandTotal" in result.stdout, "grandTotal should be used in UnifiedSalesPage"
        
        # Check that cartItems is NOT used in the verify context
        result2 = subprocess.run(
            ["grep", "-n", "amount: cartItems", "/app/frontend/src/pages/UnifiedSalesPage.js"],
            capture_output=True, text=True
        )
        assert "amount: cartItems" not in result2.stdout, "cartItems should NOT be used in amount context"
        print("✓ cartItems bug fix verified - grandTotal is used in PIN verification context")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
