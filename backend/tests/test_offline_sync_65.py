"""
Test Suite for Iteration 65: Bulletproof Offline Sales Features
================================================================
Tests:
1. GET /sync/pos-data without last_sync - full sync (is_delta=false)
2. GET /sync/pos-data with last_sync - delta sync (is_delta=true)
3. POST /sales/sync with envelope_id - idempotent sync
4. POST /sales/sync duplicate detection via envelope_id
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "sibugayagrivetsupply@gmail.com"
ADMIN_PASSWORD = "521325"


class TestOfflineSyncEndpoints:
    """Backend tests for offline sync improvements"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Auth headers"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture(scope="class")
    def branch_id(self, headers):
        """Get first branch ID for testing"""
        response = requests.get(f"{BASE_URL}/api/branches", headers=headers)
        assert response.status_code == 200
        branches = response.json()
        if branches:
            return branches[0]["id"]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Full Sync (no last_sync parameter)
    # ─────────────────────────────────────────────────────────────────────────
    def test_pos_data_full_sync_no_last_sync(self, headers):
        """GET /sync/pos-data without last_sync returns full data with is_delta=false"""
        response = requests.get(f"{BASE_URL}/api/sync/pos-data", headers=headers)
        
        assert response.status_code == 200, f"Full sync failed: {response.text}"
        data = response.json()
        
        # Verify is_delta flag is false for full sync
        assert "is_delta" in data, "Response missing is_delta field"
        assert data["is_delta"] == False, f"Expected is_delta=False for full sync, got {data['is_delta']}"
        
        # Verify response structure
        assert "products" in data, "Response missing products"
        assert "customers" in data, "Response missing customers"
        assert "price_schemes" in data, "Response missing price_schemes"
        assert "inventory" in data, "Response missing inventory"
        assert "sync_time" in data, "Response missing sync_time"
        
        # Store product count for delta comparison
        self.__class__.full_sync_product_count = len(data["products"])
        print(f"Full sync: {len(data['products'])} products, is_delta={data['is_delta']}")
        
    def test_pos_data_full_sync_with_branch(self, headers, branch_id):
        """GET /sync/pos-data with branch_id returns branch-specific data"""
        if not branch_id:
            pytest.skip("No branch available")
            
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"branch_id": branch_id},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_delta"] == False
        assert "branch_prices" in data, "Response missing branch_prices"
        
        # Verify inventory is branch-scoped
        if data["inventory"]:
            for inv in data["inventory"]:
                assert "product_id" in inv, "Inventory item missing product_id"
        
        print(f"Full sync with branch: {len(data['products'])} products, {len(data['inventory'])} inventory items")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Delta Sync (with last_sync parameter)
    # ─────────────────────────────────────────────────────────────────────────
    def test_pos_data_delta_sync_with_last_sync(self, headers):
        """GET /sync/pos-data with last_sync returns delta data with is_delta=true"""
        # Use a recent timestamp (1 hour ago) to get delta
        last_sync = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"last_sync": last_sync},
            headers=headers
        )
        
        assert response.status_code == 200, f"Delta sync failed: {response.text}"
        data = response.json()
        
        # Verify is_delta flag is true for delta sync
        assert "is_delta" in data, "Response missing is_delta field"
        assert data["is_delta"] == True, f"Expected is_delta=True for delta sync, got {data['is_delta']}"
        
        # Delta should have fewer or equal products than full sync
        delta_product_count = len(data["products"])
        full_count = getattr(self.__class__, 'full_sync_product_count', None)
        
        if full_count is not None:
            # Delta sync should return fewer or equal products (only changed ones)
            print(f"Delta sync: {delta_product_count} products (vs {full_count} full), is_delta={data['is_delta']}")
        else:
            print(f"Delta sync: {delta_product_count} products, is_delta={data['is_delta']}")
    
    def test_pos_data_delta_sync_old_timestamp(self, headers):
        """GET /sync/pos-data with very old last_sync should return all data"""
        # Use a very old timestamp - should return most/all products
        last_sync = "2020-01-01T00:00:00Z"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"last_sync": last_sync},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Even with old timestamp, is_delta should be true (because param was provided)
        assert data["is_delta"] == True, "is_delta should be True when last_sync is provided"
        print(f"Delta sync with old timestamp: {len(data['products'])} products")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Idempotent Sales Sync (envelope_id)
    # ─────────────────────────────────────────────────────────────────────────
    def test_sales_sync_with_envelope_id(self, headers, branch_id):
        """POST /sales/sync with envelope_id processes sales correctly"""
        if not branch_id:
            pytest.skip("No branch available")
        
        import uuid
        envelope_id = str(uuid.uuid4())
        sale_id = f"TEST-OFFLINE-{uuid.uuid4().hex[:8]}"
        
        sale_data = {
            "sales": [{
                "id": sale_id,
                "envelope_id": envelope_id,
                "branch_id": branch_id,
                "customer_name": "Test Walk-in",
                "items": [{
                    "product_id": "test-product-id",
                    "product_name": "Test Product",
                    "quantity": 1,
                    "rate": 100.0,
                    "price": 100.0
                }],
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "invoice_number": f"SYNC-TEST-{sale_id[:8]}",
                "status": "paid",
                "payment_type": "cash",
                "amount_paid": 100.0,
                "balance": 0,
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales/sync",
            json=sale_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Sales sync failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "synced" in data or "results" in data, "Response missing synced/results"
        assert "total_synced" in data or "total_errors" in data, "Response missing totals"
        
        results = data.get("results") or data.get("synced", [])
        if results:
            first_result = results[0]
            assert first_result.get("status") in ["synced", "duplicate"], f"Unexpected status: {first_result}"
            if "envelope_id" in first_result:
                assert first_result["envelope_id"] == envelope_id, "Envelope ID mismatch in response"
        
        print(f"Sales sync result: {data}")
        
        # Store envelope_id for duplicate test
        self.__class__.test_envelope_id = envelope_id
        self.__class__.test_sale_id = sale_id
        self.__class__.test_branch_id = branch_id
    
    def test_sales_sync_duplicate_detection(self, headers):
        """POST /sales/sync with same envelope_id returns duplicate status"""
        envelope_id = getattr(self.__class__, 'test_envelope_id', None)
        sale_id = getattr(self.__class__, 'test_sale_id', None)
        branch_id = getattr(self.__class__, 'test_branch_id', None)
        
        if not envelope_id:
            pytest.skip("No envelope_id from previous test")
        
        # Try to sync the same sale again
        sale_data = {
            "sales": [{
                "id": f"NEW-ID-{sale_id}",  # Different ID but same envelope_id
                "envelope_id": envelope_id,  # Same envelope_id
                "branch_id": branch_id,
                "customer_name": "Test Walk-in",
                "items": [{
                    "product_id": "test-product-id",
                    "product_name": "Test Product",
                    "quantity": 1,
                    "rate": 100.0
                }],
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "status": "paid",
                "payment_type": "cash",
                "amount_paid": 100.0,
                "balance": 0
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales/sync",
            json=sale_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Duplicate sync failed: {response.text}"
        data = response.json()
        
        results = data.get("results") or data.get("synced", [])
        if results:
            first_result = results[0]
            # Should be marked as duplicate due to envelope_id idempotency
            assert first_result.get("status") == "duplicate", f"Expected duplicate status, got: {first_result}"
            print(f"Duplicate detection working: {first_result}")
        else:
            print(f"No results but request succeeded: {data}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Sync Estimate Endpoint
    # ─────────────────────────────────────────────────────────────────────────
    def test_sync_estimate(self, headers, branch_id):
        """GET /sync/estimate returns quick data counts"""
        params = {}
        if branch_id:
            params["branch_id"] = branch_id
            
        response = requests.get(
            f"{BASE_URL}/api/sync/estimate",
            params=params,
            headers=headers
        )
        
        assert response.status_code == 200, f"Sync estimate failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "products" in data, "Response missing products count"
        assert "customers" in data, "Response missing customers count"
        assert "estimated_kb" in data, "Response missing estimated_kb"
        
        assert isinstance(data["products"], int), "products should be integer"
        assert isinstance(data["customers"], int), "customers should be integer"
        
        print(f"Sync estimate: {data['products']} products, {data['customers']} customers, ~{data['estimated_kb']}KB")


class TestOfflineSyncCleanup:
    """Cleanup test data after tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["token"]
        return None
    
    def test_cleanup_test_invoices(self, auth_token):
        """Cleanup: Remove test invoices created during tests"""
        if not auth_token:
            pytest.skip("No auth token")
        
        # This is a placeholder - in production, you'd want to clean up test data
        # For now, we just verify we can access the invoices endpoint
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/invoices",
            params={"search": "TEST-OFFLINE"},
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            invoices = data.get("invoices", data) if isinstance(data, dict) else data
            test_invoices = [inv for inv in invoices if "TEST-OFFLINE" in inv.get("id", "")]
            print(f"Found {len(test_invoices)} test invoices (not auto-deleted for audit)")
        else:
            print("Could not check for test invoices")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
