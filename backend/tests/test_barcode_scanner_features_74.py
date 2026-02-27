"""
Iteration 74: Testing 3 New Barcode Features
1. Barcode Management Page APIs - barcode generation, products listing
2. Print Barcodes - /barcode-inventory/{branch_id} endpoint
3. Scanner Sessions - create, get, close session APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
LOGIN_EMAIL = "janmarkeahig@gmail.com"
LOGIN_PASSWORD = "Aa@58798546521325"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns 'token' not 'access_token'
    assert "token" in data, "No token in login response"
    return data["token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def branch_id(auth_token):
    """Get a valid branch ID for testing."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = requests.get(f"{BASE_URL}/api/branches", headers=headers)
    assert response.status_code == 200
    branches = response.json()
    assert len(branches) > 0, "No branches found"
    return branches[0]["id"]


class TestScannerSessionAPIs:
    """Tests for scanner session management - Feature 3: Linked Phone Scanner"""

    def test_01_create_scanner_session(self, headers, branch_id):
        """POST /api/scanner/create-session - creates session with branch_id"""
        response = requests.post(
            f"{BASE_URL}/api/scanner/create-session",
            json={"branch_id": branch_id},
            headers=headers
        )
        assert response.status_code == 200, f"Create session failed: {response.text}"
        data = response.json()
        assert "session_id" in data, "No session_id in response"
        assert "branch_id" in data, "No branch_id in response"
        assert data["branch_id"] == branch_id, "Branch ID mismatch"
        print(f"✓ Created scanner session: {data['session_id']}")
        return data["session_id"]

    def test_02_get_scanner_session(self, headers, branch_id):
        """GET /api/scanner/session/{session_id} - validates session exists"""
        # First create a session
        create_res = requests.post(
            f"{BASE_URL}/api/scanner/create-session",
            json={"branch_id": branch_id},
            headers=headers
        )
        assert create_res.status_code == 200
        session_id = create_res.json()["session_id"]

        # Then get the session (NO auth required for phone access)
        response = requests.get(f"{BASE_URL}/api/scanner/session/{session_id}")
        assert response.status_code == 200, f"Get session failed: {response.text}"
        data = response.json()
        assert data["session_id"] == session_id
        assert data["branch_id"] == branch_id
        assert data["status"] in ["waiting", "connected"], f"Unexpected status: {data['status']}"
        print(f"✓ Session {session_id[:8]}... status: {data['status']}")

    def test_03_get_invalid_session_404(self, headers):
        """GET /api/scanner/session/{invalid} - returns 404 for invalid session"""
        response = requests.get(f"{BASE_URL}/api/scanner/session/invalid-session-123")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid session returns 404 correctly")

    def test_04_close_scanner_session(self, headers, branch_id):
        """POST /api/scanner/close-session/{session_id} - closes session"""
        # Create a session first
        create_res = requests.post(
            f"{BASE_URL}/api/scanner/create-session",
            json={"branch_id": branch_id},
            headers=headers
        )
        session_id = create_res.json()["session_id"]

        # Close it
        response = requests.post(
            f"{BASE_URL}/api/scanner/close-session/{session_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Close session failed: {response.text}"
        data = response.json()
        assert data.get("closed") == True, "closed not True in response"
        print(f"✓ Closed session {session_id[:8]}...")

    def test_05_get_closed_session_returns_410(self, headers, branch_id):
        """GET /api/scanner/session/{closed_session} - returns 410 Gone for closed session"""
        # Create and close a session
        create_res = requests.post(
            f"{BASE_URL}/api/scanner/create-session",
            json={"branch_id": branch_id},
            headers=headers
        )
        session_id = create_res.json()["session_id"]

        requests.post(f"{BASE_URL}/api/scanner/close-session/{session_id}", headers=headers)

        # Try to get the closed session
        response = requests.get(f"{BASE_URL}/api/scanner/session/{session_id}")
        assert response.status_code == 410, f"Expected 410 Gone, got {response.status_code}"
        print("✓ Closed session returns 410 Gone correctly")


class TestBarcodeInventoryAPI:
    """Tests for barcode inventory endpoint - Feature 2: Load from Inventory"""

    def test_06_get_barcode_inventory(self, headers, branch_id):
        """GET /api/products/barcode-inventory/{branch_id} - returns products with barcodes that have inventory"""
        response = requests.get(
            f"{BASE_URL}/api/products/barcode-inventory/{branch_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Barcode inventory failed: {response.text}"
        data = response.json()
        assert "products" in data, "No products key in response"
        products = data["products"]
        print(f"✓ Found {len(products)} products with barcodes in branch inventory")

        # Verify each product has required fields
        if products:
            sample = products[0]
            assert "id" in sample, "Missing id"
            assert "name" in sample, "Missing name"
            assert "barcode" in sample, "Missing barcode"
            assert "stock" in sample, "Missing stock"
            assert sample["barcode"], "Barcode should not be empty"
            assert sample["stock"] > 0, "Stock should be > 0"
            print(f"✓ Sample product: {sample['name']}, barcode: {sample['barcode']}, stock: {sample['stock']}")


class TestBarcodeManagementAPIs:
    """Tests for barcode management - Feature 1: Barcode Management Page"""

    def test_07_list_products_filter_parent_only(self, headers):
        """GET /api/products - list parent products (is_repack=false)"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            params={"is_repack": False, "limit": 100},
            headers=headers
        )
        assert response.status_code == 200, f"List products failed: {response.text}"
        data = response.json()
        assert "products" in data
        assert "total" in data

        products = data["products"]
        # Check all returned are non-repacks
        for p in products[:10]:  # Check first 10
            assert p.get("is_repack") != True, f"Product {p['name']} is a repack"

        # Count products with/without barcodes
        with_barcode = [p for p in products if p.get("barcode")]
        without_barcode = [p for p in products if not p.get("barcode")]
        print(f"✓ Parent products: {len(with_barcode)} with barcode, {len(without_barcode)} without barcode")

    def test_08_bulk_generate_barcodes(self, headers):
        """POST /api/products/generate-barcodes-bulk - generate barcodes for products without one"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-barcodes-bulk",
            headers=headers
        )
        assert response.status_code == 200, f"Bulk generate failed: {response.text}"
        data = response.json()
        assert "generated" in data, "No generated count in response"
        # Should be 0 since all products already have barcodes
        print(f"✓ Bulk generate returned: {data['generated']} products (expected 0 as all have barcodes)")

    def test_09_individual_generate_barcode(self, headers):
        """POST /api/products/{id}/generate-barcode - generate for single product"""
        # Get a product first
        products_res = requests.get(
            f"{BASE_URL}/api/products",
            params={"is_repack": False, "limit": 1},
            headers=headers
        )
        products = products_res.json().get("products", [])
        assert len(products) > 0, "No products found"
        product_id = products[0]["id"]

        # Generate barcode (will return existing if already has one)
        response = requests.post(
            f"{BASE_URL}/api/products/{product_id}/generate-barcode",
            headers=headers
        )
        assert response.status_code == 200, f"Generate barcode failed: {response.text}"
        data = response.json()
        assert "barcode" in data, "No barcode in response"
        assert data["barcode"].startswith("AG"), f"Barcode should start with AG: {data['barcode']}"
        print(f"✓ Product barcode: {data['barcode']} (already_existed: {data.get('already_existed')})")

    def test_10_product_search_with_barcode(self, headers):
        """GET /api/products - search includes barcode field"""
        # First get a known barcode
        products_res = requests.get(
            f"{BASE_URL}/api/products",
            params={"is_repack": False, "limit": 10},
            headers=headers
        )
        products = products_res.json().get("products", [])
        barcode_products = [p for p in products if p.get("barcode")]
        assert len(barcode_products) > 0, "No products with barcodes found"

        barcode_to_search = barcode_products[0]["barcode"]

        # Search by barcode
        response = requests.get(
            f"{BASE_URL}/api/products",
            params={"search": barcode_to_search},
            headers=headers
        )
        assert response.status_code == 200
        results = response.json().get("products", [])
        assert len(results) > 0, f"No results for barcode search: {barcode_to_search}"
        found = any(p["barcode"] == barcode_to_search for p in results)
        assert found, f"Barcode {barcode_to_search} not found in search results"
        print(f"✓ Search by barcode '{barcode_to_search}' returned {len(results)} result(s)")


class TestBarcodeLookupAPI:
    """Tests for barcode lookup (used by scanner)"""

    def test_11_barcode_lookup_found(self, headers, branch_id):
        """GET /api/products/barcode-lookup/{barcode} - returns product with stock"""
        # Get a product with barcode
        products_res = requests.get(
            f"{BASE_URL}/api/products",
            params={"is_repack": False, "limit": 50},
            headers=headers
        )
        products = [p for p in products_res.json().get("products", []) if p.get("barcode")]
        assert len(products) > 0, "No products with barcodes"

        barcode = products[0]["barcode"]
        response = requests.get(
            f"{BASE_URL}/api/products/barcode-lookup/{barcode}",
            params={"branch_id": branch_id},
            headers=headers
        )
        assert response.status_code == 200, f"Barcode lookup failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "barcode" in data
        assert "available" in data
        assert data["barcode"] == barcode
        print(f"✓ Barcode lookup: {data['name']} (stock: {data['available']})")

    def test_12_barcode_lookup_not_found(self, headers):
        """GET /api/products/barcode-lookup/{invalid} - returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/products/barcode-lookup/INVALID12345678",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid barcode lookup returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
