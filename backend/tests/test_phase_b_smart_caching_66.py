"""
Test Suite for Iteration 66: Phase B Smart Data Caching
========================================================
Tests:
1. Backend: Delta sync endpoint returns fewer products when last_sync is recent
2. Backend: Full sync still works without last_sync param
3. Backend: Delta sync includes is_delta=true flag
4. Backend: sync_time is returned for client to store
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "sibugayagrivetsupply@gmail.com"
ADMIN_PASSWORD = "521325"


class TestPhaseBDeltaSync:
    """Backend tests for Phase B smart caching - delta sync improvements"""
    
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
    def test_full_sync_returns_is_delta_false(self, headers):
        """GET /sync/pos-data without last_sync returns is_delta=false"""
        response = requests.get(f"{BASE_URL}/api/sync/pos-data", headers=headers)
        
        assert response.status_code == 200, f"Full sync failed: {response.text}"
        data = response.json()
        
        # Verify is_delta flag is false for full sync
        assert "is_delta" in data, "Response missing is_delta field"
        assert data["is_delta"] == False, f"Expected is_delta=False, got {data['is_delta']}"
        
        # Verify sync_time is present
        assert "sync_time" in data, "Response missing sync_time"
        
        # Store full sync count for comparison
        self.__class__.full_sync_count = len(data["products"])
        print(f"Full sync: {len(data['products'])} products, is_delta={data['is_delta']}")
        
    def test_full_sync_returns_required_fields(self, headers):
        """Full sync response contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/sync/pos-data", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["products", "customers", "price_schemes", "inventory", "sync_time", "is_delta"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Delta Sync (with last_sync parameter - recent timestamp)
    # ─────────────────────────────────────────────────────────────────────────
    def test_delta_sync_returns_is_delta_true(self, headers):
        """GET /sync/pos-data with last_sync returns is_delta=true"""
        # Use a timestamp from 5 minutes ago (simulating recent sync)
        last_sync = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"last_sync": last_sync},
            headers=headers
        )
        
        assert response.status_code == 200, f"Delta sync failed: {response.text}"
        data = response.json()
        
        # Verify is_delta flag is true for delta sync
        assert data["is_delta"] == True, f"Expected is_delta=True, got {data['is_delta']}"
        
        # Store delta count for comparison
        self.__class__.delta_sync_count = len(data["products"])
        print(f"Delta sync (5 min): {len(data['products'])} products, is_delta={data['is_delta']}")

    def test_delta_sync_returns_fewer_products_recent(self, headers):
        """Delta sync with recent timestamp should return fewer or equal products"""
        full_count = getattr(self.__class__, 'full_sync_count', None)
        delta_count = getattr(self.__class__, 'delta_sync_count', None)
        
        if full_count is None or delta_count is None:
            pytest.skip("Previous tests needed for comparison")
        
        # Delta sync should return fewer or equal products
        assert delta_count <= full_count, \
            f"Delta should return <= full: {delta_count} > {full_count}"
        
        print(f"Product count comparison: delta={delta_count} <= full={full_count}")

    def test_delta_sync_very_recent_timestamp(self, headers):
        """Delta sync with very recent timestamp (30 seconds ago) returns minimal data"""
        # Use a very recent timestamp (30 seconds ago)
        last_sync = (datetime.utcnow() - timedelta(seconds=30)).isoformat() + "Z"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"last_sync": last_sync},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_delta"] == True
        very_recent_count = len(data["products"])
        
        # Very recent sync should have very few or zero updated products
        print(f"Very recent delta sync (30s): {very_recent_count} products")
        # Not asserting exact count since it depends on system activity

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: Delta Sync with branch filter
    # ─────────────────────────────────────────────────────────────────────────
    def test_delta_sync_with_branch_id(self, headers, branch_id):
        """Delta sync with branch_id filters correctly"""
        if not branch_id:
            pytest.skip("No branch available")
        
        last_sync = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/pos-data",
            params={"branch_id": branch_id, "last_sync": last_sync},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_delta"] == True
        assert "branch_prices" in data
        
        # Verify inventory is branch-scoped
        if data["inventory"]:
            for inv in data["inventory"]:
                assert inv.get("branch_id") == branch_id or "branch_id" not in inv
        
        print(f"Delta sync with branch: {len(data['products'])} products, {len(data['inventory'])} inventory")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST: sync_time returned for client storage
    # ─────────────────────────────────────────────────────────────────────────
    def test_sync_time_format_valid(self, headers):
        """sync_time is a valid ISO timestamp for client to store"""
        response = requests.get(f"{BASE_URL}/api/sync/pos-data", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        sync_time = data.get("sync_time")
        assert sync_time is not None, "sync_time is missing"
        
        # Verify it's a valid ISO format timestamp
        try:
            # Try parsing with various ISO formats
            if sync_time.endswith("Z"):
                datetime.fromisoformat(sync_time.replace("Z", "+00:00"))
            else:
                datetime.fromisoformat(sync_time)
            print(f"sync_time is valid ISO: {sync_time}")
        except ValueError as e:
            pytest.fail(f"sync_time is not valid ISO format: {sync_time} - {e}")


class TestPhaseBSyncEstimate:
    """Test sync estimate endpoint (used for pre-download size check)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["token"]
        return None
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
    
    def test_sync_estimate_returns_counts(self, headers):
        """GET /sync/estimate returns product/customer counts"""
        response = requests.get(f"{BASE_URL}/api/sync/estimate", headers=headers)
        
        assert response.status_code == 200, f"Sync estimate failed: {response.text}"
        data = response.json()
        
        assert "products" in data
        assert "customers" in data
        assert "estimated_kb" in data
        
        assert isinstance(data["products"], int)
        assert isinstance(data["customers"], int)
        assert isinstance(data["estimated_kb"], int)
        
        print(f"Sync estimate: {data['products']} products, {data['customers']} customers, ~{data['estimated_kb']}KB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
