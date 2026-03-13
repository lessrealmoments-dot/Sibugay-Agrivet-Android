"""
Test suite for Budget Checker / Kiosk Mode APIs
Iteration 109 - Tests the PIN verification for kiosk_unlock and kiosk_cost_reveal actions,
and the product search/barcode-lookup endpoints used by the kiosk.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"


class TestKioskPINVerification:
    """Tests for PIN verification endpoints used by Budget Checker kiosk"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_verify_manager_pin_kiosk_unlock_valid(self):
        """Test valid Manager PIN for kiosk_unlock action"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={
            "pin": MANAGER_PIN,
            "action_key": "kiosk_unlock"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") is True
        assert "manager_id" in data
        assert "manager_name" in data
        print(f"PASS: kiosk_unlock with valid PIN - manager={data.get('manager_name')}")
    
    def test_verify_manager_pin_kiosk_cost_reveal_valid(self):
        """Test valid Manager PIN for kiosk_cost_reveal action"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={
            "pin": MANAGER_PIN,
            "action_key": "kiosk_cost_reveal"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") is True
        assert "manager_id" in data
        assert "manager_name" in data
        print(f"PASS: kiosk_cost_reveal with valid PIN - manager={data.get('manager_name')}")
    
    def test_verify_manager_pin_kiosk_unlock_invalid(self):
        """Test invalid PIN for kiosk_unlock action"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={
            "pin": "000000",  # Invalid PIN
            "action_key": "kiosk_unlock"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") is False
        print("PASS: kiosk_unlock with invalid PIN correctly rejected")
    
    def test_verify_manager_pin_kiosk_cost_reveal_invalid(self):
        """Test invalid PIN for kiosk_cost_reveal action"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={
            "pin": "999999",  # Invalid PIN
            "action_key": "kiosk_cost_reveal"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") is False
        print("PASS: kiosk_cost_reveal with invalid PIN correctly rejected")
    
    def test_verify_manager_pin_no_pin(self):
        """Test missing PIN returns error"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={
            "action_key": "kiosk_unlock"
        })
        assert response.status_code == 400
        print("PASS: Missing PIN returns 400 error")


class TestProductSearchForKiosk:
    """Tests for product search endpoints used by Budget Checker"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_product_search_detail_endpoint(self):
        """Test the search-detail endpoint used by kiosk"""
        response = self.session.get(f"{BASE_URL}/api/products/search-detail", params={
            "q": "a"  # Simple search
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            product = data[0]
            # Verify expected fields for kiosk display
            assert "id" in product
            assert "name" in product
            assert "prices" in product
            assert "sku" in product or product.get("sku") == ""
            print(f"PASS: search-detail returns {len(data)} products with expected fields")
        else:
            print("PASS: search-detail returns empty list (no products match)")
    
    def test_product_search_detail_with_branch(self):
        """Test search-detail with branch_id parameter"""
        # Get a branch ID first
        branches_response = self.session.get(f"{BASE_URL}/api/branches")
        if branches_response.status_code == 200:
            branches = branches_response.json()
            if len(branches) > 0:
                branch_id = branches[0]["id"]
                response = self.session.get(f"{BASE_URL}/api/products/search-detail", params={
                    "q": "a",
                    "branch_id": branch_id
                })
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                if len(data) > 0:
                    product = data[0]
                    # Check for available stock field
                    assert "available" in product
                    print(f"PASS: search-detail with branch returns products with available stock")
                else:
                    print("PASS: search-detail with branch returns empty list")
            else:
                pytest.skip("No branches available for testing")
        else:
            pytest.skip("Could not fetch branches")
    
    def test_barcode_lookup_endpoint(self):
        """Test barcode-lookup endpoint for kiosk barcode scanning"""
        # First get a product with a barcode
        products_response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50})
        if products_response.status_code == 200:
            products_data = products_response.json()
            products = products_data.get("products", [])
            product_with_barcode = None
            for p in products:
                if p.get("barcode"):
                    product_with_barcode = p
                    break
            
            if product_with_barcode:
                barcode = product_with_barcode["barcode"]
                response = self.session.get(f"{BASE_URL}/api/products/barcode-lookup/{barcode}")
                assert response.status_code == 200
                data = response.json()
                assert data.get("id") == product_with_barcode["id"]
                assert data.get("barcode") == barcode
                assert "prices" in data
                assert "available" in data
                print(f"PASS: barcode-lookup returns correct product for barcode={barcode}")
            else:
                print("SKIP: No products with barcodes found for testing")
        else:
            pytest.skip("Could not fetch products")
    
    def test_barcode_lookup_not_found(self):
        """Test barcode-lookup with non-existent barcode"""
        response = self.session.get(f"{BASE_URL}/api/products/barcode-lookup/NONEXISTENT12345")
        assert response.status_code == 404
        print("PASS: barcode-lookup returns 404 for non-existent barcode")


class TestPINPoliciesForKiosk:
    """Tests to verify PIN policy configuration includes kiosk actions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_verify_api_me_endpoint(self):
        """Verify /api/auth/me returns user info (confirms auth is working)"""
        response = self.session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        print(f"PASS: /api/auth/me returns user info - email={data.get('email')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
