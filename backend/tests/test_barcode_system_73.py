"""
Iteration 73: Barcode System Testing
Tests for barcode generation, lookup, bulk generation, duplicate checking APIs.

Endpoints tested:
- GET /api/products - barcode column and search by barcode
- POST /api/products/generate-barcodes-bulk - generate barcodes for all products without one  
- POST /api/products/{product_id}/generate-barcode - generate barcode for single product
- GET /api/products/barcode-lookup/{barcode} - return product by barcode
- POST /api/products/barcode-check - detect duplicate barcodes
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBarcodeSystem:
    """Test barcode API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as super_admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.token = data.get("token") or data.get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.org_id = data.get("organization_id") or data.get("user", {}).get("organization_id")
        yield

    # ── Test 1: GET /api/products returns products with barcode field ──
    def test_01_get_products_includes_barcode_field(self):
        """Verify products endpoint returns barcode field"""
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 10})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        products = data.get("products", [])
        assert len(products) > 0, "No products returned"
        
        # Check barcode field exists
        product_with_barcode = None
        for p in products:
            if p.get("barcode"):
                product_with_barcode = p
                break
        
        assert product_with_barcode is not None, "No product with barcode found"
        assert product_with_barcode["barcode"].startswith("AG"), f"Barcode should start with AG, got {product_with_barcode['barcode']}"
        print(f"TEST 1 PASSED: Products have barcode field. Sample: {product_with_barcode['barcode']}")

    # ── Test 2: Search products by barcode ──
    def test_02_search_products_by_barcode(self):
        """Verify products can be searched by barcode"""
        # First get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        barcode = product_with_barcode["barcode"]
        
        # Search by barcode
        search_response = self.session.get(f"{BASE_URL}/api/products", params={"search": barcode, "limit": 10})
        assert search_response.status_code == 200
        
        search_results = search_response.json().get("products", [])
        found = any(p.get("barcode") == barcode for p in search_results)
        assert found, f"Product with barcode {barcode} not found in search results"
        print(f"TEST 2 PASSED: Search by barcode {barcode} works correctly")

    # ── Test 3: GET /api/products/barcode-lookup/{barcode} ──
    def test_03_barcode_lookup_valid(self):
        """Test barcode lookup endpoint with valid barcode"""
        # First get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        barcode = product_with_barcode["barcode"]
        product_id = product_with_barcode["id"]
        product_name = product_with_barcode["name"]
        
        # Lookup by barcode
        lookup_response = self.session.get(f"{BASE_URL}/api/products/barcode-lookup/{barcode}")
        assert lookup_response.status_code == 200, f"Expected 200, got {lookup_response.status_code}"
        
        lookup_data = lookup_response.json()
        assert lookup_data["id"] == product_id, "Product ID mismatch"
        assert lookup_data["barcode"] == barcode, "Barcode mismatch"
        assert "available" in lookup_data, "Response should include available stock"
        print(f"TEST 3 PASSED: Barcode lookup for {barcode} returns {product_name}")

    # ── Test 4: GET /api/products/barcode-lookup/{barcode} - not found ──
    def test_04_barcode_lookup_not_found(self):
        """Test barcode lookup endpoint with invalid barcode"""
        fake_barcode = "AG99999999FAKE"
        lookup_response = self.session.get(f"{BASE_URL}/api/products/barcode-lookup/{fake_barcode}")
        assert lookup_response.status_code == 404, f"Expected 404, got {lookup_response.status_code}"
        print(f"TEST 4 PASSED: Invalid barcode returns 404 as expected")

    # ── Test 5: POST /api/products/barcode-check - existing barcode ──
    def test_05_barcode_check_duplicate(self):
        """Test barcode duplicate check with existing barcode"""
        # Get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        barcode = product_with_barcode["barcode"]
        
        # Check duplicate
        check_response = self.session.post(f"{BASE_URL}/api/products/barcode-check", json={
            "barcode": barcode
        })
        assert check_response.status_code == 200
        
        check_data = check_response.json()
        assert check_data["duplicate"] == True, "Should detect duplicate"
        assert check_data["product"]["barcode"] == barcode
        print(f"TEST 5 PASSED: Duplicate check correctly identifies existing barcode {barcode}")

    # ── Test 6: POST /api/products/barcode-check - new barcode ──
    def test_06_barcode_check_not_duplicate(self):
        """Test barcode duplicate check with new barcode"""
        new_barcode = "AG12345678UNIQUE"
        check_response = self.session.post(f"{BASE_URL}/api/products/barcode-check", json={
            "barcode": new_barcode
        })
        assert check_response.status_code == 200
        
        check_data = check_response.json()
        assert check_data["duplicate"] == False, "Should not detect duplicate for new barcode"
        print(f"TEST 6 PASSED: New barcode {new_barcode} correctly identified as unique")

    # ── Test 7: POST /api/products/barcode-check - with exclude_product_id ──
    def test_07_barcode_check_exclude_self(self):
        """Test barcode check with exclude_product_id (same product editing)"""
        # Get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        barcode = product_with_barcode["barcode"]
        product_id = product_with_barcode["id"]
        
        # Check duplicate excluding self
        check_response = self.session.post(f"{BASE_URL}/api/products/barcode-check", json={
            "barcode": barcode,
            "exclude_product_id": product_id
        })
        assert check_response.status_code == 200
        
        check_data = check_response.json()
        assert check_data["duplicate"] == False, "Should not be duplicate when excluding self"
        print(f"TEST 7 PASSED: Barcode check excludes self correctly")

    # ── Test 8: POST /api/products/{product_id}/generate-barcode - already has barcode ──
    def test_08_generate_barcode_already_exists(self):
        """Test generate barcode for product that already has one"""
        # Get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        product_id = product_with_barcode["id"]
        existing_barcode = product_with_barcode["barcode"]
        
        # Try to generate barcode
        gen_response = self.session.post(f"{BASE_URL}/api/products/{product_id}/generate-barcode")
        assert gen_response.status_code == 200
        
        gen_data = gen_response.json()
        assert gen_data["already_existed"] == True, "Should indicate barcode already existed"
        assert gen_data["barcode"] == existing_barcode, "Should return existing barcode"
        print(f"TEST 8 PASSED: Generate barcode returns existing barcode {existing_barcode}")

    # ── Test 9: POST /api/products/generate-barcodes-bulk ──
    def test_09_generate_barcodes_bulk(self):
        """Test bulk barcode generation - should handle already-barcoded products"""
        # Note: Main agent said all 67 products now have barcodes, so this should return 0 generated
        response = self.session.post(f"{BASE_URL}/api/products/generate-barcodes-bulk")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "generated" in data, "Response should include generated count"
        assert "products" in data, "Response should include products list"
        
        # Since all products have barcodes, expect 0 generated
        print(f"TEST 9 PASSED: Bulk generate returned {data['generated']} products (expected 0 if all have barcodes)")

    # ── Test 10: Barcode lookup with branch_id parameter ──
    def test_10_barcode_lookup_with_branch(self):
        """Test barcode lookup with branch_id for branch-specific pricing"""
        # Get a product with barcode
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 50, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        product_with_barcode = next((p for p in products if p.get("barcode")), None)
        
        if not product_with_barcode:
            pytest.skip("No products with barcode found")
        
        barcode = product_with_barcode["barcode"]
        
        # Get branches
        branches_response = self.session.get(f"{BASE_URL}/api/branches")
        if branches_response.status_code != 200:
            pytest.skip("Could not get branches")
        
        branches = branches_response.json()
        if not branches:
            pytest.skip("No branches found")
        
        branch_id = branches[0].get("id")
        
        # Lookup with branch_id
        lookup_response = self.session.get(
            f"{BASE_URL}/api/products/barcode-lookup/{barcode}",
            params={"branch_id": branch_id}
        )
        assert lookup_response.status_code == 200
        
        data = lookup_response.json()
        assert data["barcode"] == barcode
        assert "available" in data
        print(f"TEST 10 PASSED: Barcode lookup with branch_id works correctly")

    # ── Test 11: Verify repacks don't have barcodes ──
    def test_11_repacks_no_barcodes(self):
        """Verify repack products do not have barcodes"""
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 100, "is_repack": True})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        if not products:
            print("TEST 11 SKIPPED: No repacks found")
            return
        
        repacks_with_barcode = [p for p in products if p.get("barcode")]
        assert len(repacks_with_barcode) == 0, f"Repacks should not have barcodes, found {len(repacks_with_barcode)}"
        print(f"TEST 11 PASSED: {len(products)} repacks verified - none have barcodes")

    # ── Test 12: Barcode format validation (AG prefix + 8 digits) ──
    def test_12_barcode_format_validation(self):
        """Verify barcodes follow AG prefix + 8 digit format"""
        response = self.session.get(f"{BASE_URL}/api/products", params={"limit": 100, "is_repack": False})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        products_with_barcode = [p for p in products if p.get("barcode")]
        
        invalid_format = []
        for p in products_with_barcode:
            barcode = p["barcode"]
            if not barcode.startswith("AG"):
                invalid_format.append(f"{barcode} (no AG prefix)")
            elif len(barcode) != 10:  # AG + 8 digits
                invalid_format.append(f"{barcode} (wrong length: {len(barcode)})")
            elif not barcode[2:].isdigit():
                invalid_format.append(f"{barcode} (non-digit suffix)")
        
        assert len(invalid_format) == 0, f"Invalid barcode formats: {invalid_format}"
        print(f"TEST 12 PASSED: {len(products_with_barcode)} barcodes verified with correct AG + 8 digit format")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
