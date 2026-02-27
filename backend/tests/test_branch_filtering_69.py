"""
Branch-specific filtering tests for Product Detail page bug fixes.
Tests:
1. GET /api/products/{id}/movements?branch_id=xxx - filter movements by branch
2. GET /api/products/{id}/orders?branch_id=xxx - filter orders by branch (POs + Sales)
3. GET /api/products/{id}/capital-history?branch_id=xxx - filter capital changes by branch
4. POST /api/products/{id}/vendors - accepts branch_id field
5. GET /api/products/{id}/detail?branch_id=xxx - filters vendors by branch
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def generate_id():
    return str(uuid.uuid4()).replace('-', '')[:24]


class TestBranchFiltering:
    """Tests for branch-specific filtering on Product Detail page endpoints"""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_test_data(self, request):
        """Seed test data: organization, branches, users, products, movements, orders, vendors"""
        # Store all IDs for cleanup
        self.ids = {}
        
        # Generate unique identifiers for this test run
        run_id = generate_id()[:8]
        
        # Create organization
        org_response = requests.post(f"{BASE_URL}/api/organizations", json={
            "name": f"Test Org {run_id}",
            "business_type": "retail",
            "plan_id": "professional",
        })
        print(f"Create org: {org_response.status_code}")
        if org_response.status_code == 200:
            org_data = org_response.json()
            self.ids['org_id'] = org_data.get('id') or org_data.get('organization', {}).get('id')
        else:
            print(f"Org creation response: {org_response.text[:200]}")
            # Try to proceed with existing setup
        
        # Create test user (admin)
        admin_email = f"test_admin_{run_id}@test.com"
        admin_password = "TestPass123!"
        
        # Try to login first to see if there's existing data
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sibugayagrivetsupply@gmail.com",
            "password": "521325"
        })
        
        if login_resp.status_code == 200:
            print("Using existing admin credentials")
            token_data = login_resp.json()
            self.token = token_data.get('access_token') or token_data.get('token')
            self.user = token_data.get('user', {})
        else:
            # Register new admin
            print("Attempting to register new admin")
            reg_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": admin_email,
                "password": admin_password,
                "full_name": "Test Admin",
                "role": "admin"
            })
            print(f"Register: {reg_resp.status_code}")
            if reg_resp.status_code == 200:
                reg_data = reg_resp.json()
                self.token = reg_data.get('access_token') or reg_data.get('token')
                self.user = reg_data.get('user', {})
            else:
                pytest.skip(f"Cannot authenticate: {reg_resp.text[:200]}")
        
        if not hasattr(self, 'token') or not self.token:
            pytest.skip("No authentication token available")
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get or create branches
        branches_resp = requests.get(f"{BASE_URL}/api/branches", headers=self.headers)
        if branches_resp.status_code == 200:
            branches = branches_resp.json()
            if isinstance(branches, list) and len(branches) >= 2:
                self.ids['branch_1'] = branches[0]['id']
                self.ids['branch_2'] = branches[1]['id']
                print(f"Using existing branches: {self.ids['branch_1']}, {self.ids['branch_2']}")
            else:
                # Create branches
                for i in range(2):
                    branch_resp = requests.post(f"{BASE_URL}/api/branches", headers=self.headers, json={
                        "name": f"Test Branch {i+1} {run_id}",
                        "address": f"Test Address {i+1}"
                    })
                    if branch_resp.status_code in [200, 201]:
                        self.ids[f'branch_{i+1}'] = branch_resp.json().get('id')
        
        # Create test product
        product_resp = requests.post(f"{BASE_URL}/api/products", headers=self.headers, json={
            "name": f"TEST_Product_{run_id}",
            "sku": f"TEST-SKU-{run_id}",
            "category": "Test Category",
            "cost_price": 100.0,
            "prices": {"retail": 150.0, "wholesale": 130.0}
        })
        if product_resp.status_code in [200, 201]:
            self.ids['product_id'] = product_resp.json().get('id')
            print(f"Created product: {self.ids['product_id']}")
        else:
            print(f"Product creation: {product_resp.status_code} - {product_resp.text[:200]}")
        
        # Store request for cleanup
        request.cls.ids = self.ids
        request.cls.token = self.token
        request.cls.headers = self.headers
        
        yield
        
        # Cleanup - delete test product
        if 'product_id' in self.ids:
            requests.delete(f"{BASE_URL}/api/products/{self.ids['product_id']}", headers=self.headers)

    def test_01_basic_api_health(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/setup/status")
        print(f"API Health check: {response.status_code}")
        assert response.status_code == 200, f"API not accessible: {response.text[:200]}"

    def test_02_movements_endpoint_accepts_branch_id(self):
        """Test GET /api/products/{id}/movements?branch_id=xxx"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        branch_id = self.ids.get('branch_1', 'test-branch-1')
        
        # Test without branch_id (should return all)
        resp_all = requests.get(
            f"{BASE_URL}/api/products/{product_id}/movements",
            headers=self.headers
        )
        print(f"Movements (no filter): {resp_all.status_code}")
        assert resp_all.status_code == 200, f"Movements endpoint failed: {resp_all.text[:200]}"
        
        # Test with branch_id filter
        resp_filtered = requests.get(
            f"{BASE_URL}/api/products/{product_id}/movements",
            headers=self.headers,
            params={"branch_id": branch_id}
        )
        print(f"Movements (with branch_id): {resp_filtered.status_code}")
        assert resp_filtered.status_code == 200, f"Movements endpoint with branch_id failed: {resp_filtered.text[:200]}"
        
        data = resp_filtered.json()
        assert "movements" in data, "Response should contain 'movements' key"
        print(f"Movements endpoint accepts branch_id param - PASS")

    def test_03_orders_endpoint_accepts_branch_id(self):
        """Test GET /api/products/{id}/orders?branch_id=xxx"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        branch_id = self.ids.get('branch_1', 'test-branch-1')
        
        # Test without branch_id
        resp_all = requests.get(
            f"{BASE_URL}/api/products/{product_id}/orders",
            headers=self.headers
        )
        print(f"Orders (no filter): {resp_all.status_code}")
        assert resp_all.status_code == 200, f"Orders endpoint failed: {resp_all.text[:200]}"
        
        # Test with branch_id filter
        resp_filtered = requests.get(
            f"{BASE_URL}/api/products/{product_id}/orders",
            headers=self.headers,
            params={"branch_id": branch_id}
        )
        print(f"Orders (with branch_id): {resp_filtered.status_code}")
        assert resp_filtered.status_code == 200, f"Orders endpoint with branch_id failed: {resp_filtered.text[:200]}"
        
        data = resp_filtered.json()
        assert "orders" in data, "Response should contain 'orders' key"
        print(f"Orders endpoint accepts branch_id param - PASS")

    def test_04_capital_history_accepts_branch_id(self):
        """Test GET /api/products/{id}/capital-history?branch_id=xxx"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        branch_id = self.ids.get('branch_1', 'test-branch-1')
        
        # Test without branch_id
        resp_all = requests.get(
            f"{BASE_URL}/api/products/{product_id}/capital-history",
            headers=self.headers
        )
        print(f"Capital History (no filter): {resp_all.status_code}")
        assert resp_all.status_code == 200, f"Capital history endpoint failed: {resp_all.text[:200]}"
        
        # Test with branch_id filter
        resp_filtered = requests.get(
            f"{BASE_URL}/api/products/{product_id}/capital-history",
            headers=self.headers,
            params={"branch_id": branch_id}
        )
        print(f"Capital History (with branch_id): {resp_filtered.status_code}")
        assert resp_filtered.status_code == 200, f"Capital history endpoint with branch_id failed: {resp_filtered.text[:200]}"
        
        data = resp_filtered.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Capital history endpoint accepts branch_id param - PASS")

    def test_05_add_vendor_with_branch_id(self):
        """Test POST /api/products/{id}/vendors accepts branch_id field"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        branch_id = self.ids.get('branch_1', 'test-branch-1')
        
        # Add vendor with branch_id
        vendor_data = {
            "vendor_name": f"TEST_Vendor_{datetime.now().timestamp()}",
            "vendor_contact": "09123456789",
            "last_price": 95.0,
            "is_preferred": False,
            "branch_id": branch_id  # Branch-specific vendor
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/products/{product_id}/vendors",
            headers=self.headers,
            json=vendor_data
        )
        print(f"Add vendor with branch_id: {resp.status_code}")
        assert resp.status_code in [200, 201], f"Add vendor failed: {resp.text[:200]}"
        
        data = resp.json()
        assert "branch_id" in data, "Vendor response should contain branch_id"
        assert data["branch_id"] == branch_id, f"Vendor branch_id mismatch: expected {branch_id}, got {data.get('branch_id')}"
        
        # Store vendor ID for cleanup
        self.ids['vendor_1'] = data.get('id')
        print(f"Add vendor with branch_id - PASS")

    def test_06_add_vendor_without_branch_id(self):
        """Test POST /api/products/{id}/vendors without branch_id (global vendor)"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        
        # Add vendor without branch_id (global)
        vendor_data = {
            "vendor_name": f"TEST_GlobalVendor_{datetime.now().timestamp()}",
            "vendor_contact": "09987654321",
            "last_price": 90.0,
            "is_preferred": True,
            # No branch_id - global vendor
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/products/{product_id}/vendors",
            headers=self.headers,
            json=vendor_data
        )
        print(f"Add global vendor: {resp.status_code}")
        assert resp.status_code in [200, 201], f"Add global vendor failed: {resp.text[:200]}"
        
        data = resp.json()
        # Should have empty branch_id or not set
        assert data.get("branch_id", "") == "" or data.get("branch_id") is None, \
            "Global vendor should have empty branch_id"
        
        self.ids['vendor_2'] = data.get('id')
        print(f"Add global vendor - PASS")

    def test_07_product_detail_filters_vendors_by_branch(self):
        """Test GET /api/products/{id}/detail?branch_id=xxx filters vendors"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        branch_id = self.ids.get('branch_1', 'test-branch-1')
        
        # Get product detail without branch filter (should return all vendors)
        resp_all = requests.get(
            f"{BASE_URL}/api/products/{product_id}/detail",
            headers=self.headers
        )
        print(f"Product detail (no filter): {resp_all.status_code}")
        assert resp_all.status_code == 200, f"Product detail failed: {resp_all.text[:200]}"
        
        all_vendors = resp_all.json().get("vendors", [])
        print(f"All vendors count: {len(all_vendors)}")
        
        # Get product detail with branch filter
        resp_filtered = requests.get(
            f"{BASE_URL}/api/products/{product_id}/detail",
            headers=self.headers,
            params={"branch_id": branch_id}
        )
        print(f"Product detail (with branch_id): {resp_filtered.status_code}")
        assert resp_filtered.status_code == 200, f"Product detail with branch_id failed: {resp_filtered.text[:200]}"
        
        data = resp_filtered.json()
        filtered_vendors = data.get("vendors", [])
        print(f"Filtered vendors count: {len(filtered_vendors)}")
        
        # Verify filtered vendors belong to the branch OR are global
        for v in filtered_vendors:
            v_branch = v.get("branch_id", "")
            assert v_branch in [branch_id, "", None], \
                f"Vendor {v.get('vendor_name')} has wrong branch: {v_branch}"
        
        print(f"Product detail filters vendors by branch - PASS")

    def test_08_product_detail_contains_expected_fields(self):
        """Test product detail response contains all expected fields"""
        if not hasattr(self, 'ids') or 'product_id' not in self.ids:
            pytest.skip("No test product created")
        
        product_id = self.ids['product_id']
        
        resp = requests.get(
            f"{BASE_URL}/api/products/{product_id}/detail",
            headers=self.headers
        )
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Check required fields
        required_fields = ["product", "inventory", "cost", "vendors"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Check cost object fields
        cost = data.get("cost", {})
        cost_fields = ["cost_price", "capital_method", "moving_average", "last_purchase"]
        for field in cost_fields:
            assert field in cost, f"Missing cost field: {field}"
        
        print(f"Product detail contains all expected fields - PASS")


class TestDataIsolation:
    """Tests for branch-specific data isolation"""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_auth(self, request):
        """Setup authentication"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sibugayagrivetsupply@gmail.com",
            "password": "521325"
        })
        
        if login_resp.status_code != 200:
            pytest.skip("Cannot authenticate with existing credentials")
        
        token_data = login_resp.json()
        self.token = token_data.get('access_token') or token_data.get('token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        request.cls.token = self.token
        request.cls.headers = self.headers
        
        yield

    def test_09_get_branches_list(self):
        """Get list of branches for reference"""
        resp = requests.get(f"{BASE_URL}/api/branches", headers=self.headers)
        print(f"Branches list: {resp.status_code}")
        
        if resp.status_code == 200:
            branches = resp.json()
            if isinstance(branches, list):
                print(f"Found {len(branches)} branches")
                for b in branches[:5]:
                    print(f"  - {b.get('name', 'N/A')} (ID: {b.get('id', 'N/A')[:8]}...)")
        
        assert resp.status_code == 200

    def test_10_get_products_list(self):
        """Get list of products for reference"""
        resp = requests.get(f"{BASE_URL}/api/products", headers=self.headers, params={"limit": 10})
        print(f"Products list: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            products = data.get("products", [])
            print(f"Found {len(products)} products (showing first 10)")
            for p in products[:5]:
                print(f"  - {p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')[:8]}...)")
        
        assert resp.status_code == 200


class TestCodeReview:
    """Code review verification tests"""
    
    def test_11_verify_movements_endpoint_implementation(self):
        """Verify movements endpoint has branch_id parameter in code"""
        import re
        
        with open('/app/backend/routes/products.py', 'r') as f:
            content = f.read()
        
        # Check that get_product_movements accepts branch_id parameter
        pattern = r'async def get_product_movements.*branch_id.*Optional\[str\]'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "get_product_movements should accept Optional[str] branch_id parameter"
        
        # Check that the query uses branch_id filter
        assert 'query["branch_id"] = branch_id' in content or '"branch_id": branch_id' in content, \
            "Movements endpoint should filter by branch_id"
        
        print("Movements endpoint implementation verified - PASS")

    def test_12_verify_orders_endpoint_implementation(self):
        """Verify orders endpoint has branch_id parameter and returns both POs and Sales"""
        with open('/app/backend/routes/products.py', 'r') as f:
            content = f.read()
        
        # Check that get_product_orders accepts branch_id parameter
        assert 'async def get_product_orders' in content
        assert 'branch_id: Optional[str]' in content
        
        # Check that it queries both purchase_orders and sales
        assert 'db.purchase_orders.find' in content
        assert 'db.sales.find' in content
        
        # Check that branch filter is applied to both
        assert 'po_match["branch_id"] = branch_id' in content or '"branch_id": branch_id' in content
        assert 'sale_match["branch_id"] = branch_id' in content
        
        print("Orders endpoint implementation verified - PASS")

    def test_13_verify_capital_history_implementation(self):
        """Verify capital-history endpoint filters by branch_id"""
        with open('/app/backend/routes/products.py', 'r') as f:
            content = f.read()
        
        # Check that get_capital_history accepts branch_id parameter
        assert 'async def get_capital_history' in content
        assert 'branch_id: Optional[str]' in content
        
        # Check for backward compatibility logic ($or with branch_id exists)
        assert '"branch_id": {"$exists": False}' in content or '$exists' in content
        
        print("Capital history endpoint implementation verified - PASS")

    def test_14_verify_vendor_accepts_branch_id(self):
        """Verify add_product_vendor accepts branch_id in request body"""
        with open('/app/backend/routes/products.py', 'r') as f:
            content = f.read()
        
        # Check that add_product_vendor extracts branch_id from data
        assert 'async def add_product_vendor' in content
        assert '"branch_id": data.get("branch_id"' in content
        
        print("Vendor endpoint accepts branch_id - PASS")

    def test_15_verify_product_detail_filters_vendors(self):
        """Verify get_product_detail filters vendors by branch_id"""
        with open('/app/backend/routes/products.py', 'r') as f:
            content = f.read()
        
        # Check that get_product_detail has vendor filtering logic
        assert 'async def get_product_detail' in content
        
        # Check for vendor filtering by branch
        assert 'vendor_query' in content or '"$or"' in content
        
        print("Product detail filters vendors by branch - PASS")

    def test_16_verify_capital_changes_include_branch_id(self):
        """Verify capital_changes insert includes branch_id"""
        # Check purchase_orders.py
        with open('/app/backend/routes/purchase_orders.py', 'r') as f:
            po_content = f.read()
        
        # Check branch_transfers.py
        with open('/app/backend/routes/branch_transfers.py', 'r') as f:
            bt_content = f.read()
        
        # Verify capital_changes insert includes branch_id in PO
        assert 'capital_changes.insert_one' in po_content
        assert '"branch_id": branch_id' in po_content
        
        # Verify capital_changes insert includes branch_id in branch transfers
        assert 'capital_changes.insert_one' in bt_content
        assert '"branch_id": to_branch_id' in bt_content
        
        print("Capital changes include branch_id - PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
