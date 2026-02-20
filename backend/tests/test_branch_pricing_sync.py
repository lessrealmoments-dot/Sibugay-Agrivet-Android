"""
Branch Pricing, Sync Estimate, and Offline Features Backend Tests
=================================================================
Tests for:
- GET /sync/estimate - sync size estimate endpoint
- GET /branch-prices - list branch price overrides
- PUT /branch-prices/{product_id} - upsert branch price override
- DELETE /branch-prices/{product_id} - remove branch price override
- Product search-detail with branch-specific prices
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Branch IDs from the test DB
MAIN_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"
SAMPOLI_BRANCH_ID = "de3b347f-6166-446e-9ab7-2b4ab1836176"
# Known product with existing override for Main Branch (retail: 95.5, wholesale: 82.0)
TEST_PRODUCT_ID = "4dfff4e8-0379-473e-bbba-e9f8212473de"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for owner user."""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner",
        "password": "521325"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSyncEstimate:
    """Tests for GET /sync/estimate endpoint."""

    def test_estimate_with_valid_branch_returns_200(self, api_client, auth_headers):
        """Sync estimate endpoint should return 200 with branch_id."""
        response = api_client.get(
            f"{BASE_URL}/api/sync/estimate",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_estimate_with_branch_returns_required_fields(self, api_client, auth_headers):
        """Response must include products, customers, inventory, estimated_kb."""
        response = api_client.get(
            f"{BASE_URL}/api/sync/estimate",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        assert "products" in data, "Missing 'products' field"
        assert "customers" in data, "Missing 'customers' field"
        assert "inventory" in data, "Missing 'inventory' field"
        assert "estimated_kb" in data, "Missing 'estimated_kb' field"

    def test_estimate_products_count_positive(self, api_client, auth_headers):
        """Product count should be > 0 (seeded data exists)."""
        response = api_client.get(
            f"{BASE_URL}/api/sync/estimate",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        assert isinstance(data["products"], int)
        assert data["products"] > 0, "Expected at least 1 product"

    def test_estimate_without_branch_no_inventory(self, api_client, auth_headers):
        """Without branch_id, inventory should be 0."""
        response = api_client.get(
            f"{BASE_URL}/api/sync/estimate",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["inventory"] == 0, "inventory should be 0 without branch_id"

    def test_estimate_kb_is_positive_number(self, api_client, auth_headers):
        """estimated_kb should be a positive numeric value."""
        response = api_client.get(
            f"{BASE_URL}/api/sync/estimate",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        assert isinstance(data["estimated_kb"], (int, float))
        assert data["estimated_kb"] > 0

    def test_estimate_unauthorized_returns_401(self, api_client):
        """Estimate endpoint should require authentication."""
        response = api_client.get(f"{BASE_URL}/api/sync/estimate")
        assert response.status_code == 401


class TestBranchPricesGet:
    """Tests for GET /branch-prices endpoint."""

    def test_list_by_product_id_returns_200(self, api_client, auth_headers):
        """GET /branch-prices?product_id should return overrides list."""
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_list_by_product_id_returns_list(self, api_client, auth_headers):
        """Response should be a list."""
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        assert isinstance(response.json(), list)

    def test_list_by_branch_id_returns_200(self, api_client, auth_headers):
        """GET /branch-prices?branch_id should return overrides for a branch."""
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_main_branch_has_existing_override(self, api_client, auth_headers):
        """Main branch should have the known override for TEST_PRODUCT_ID."""
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        data = response.json()
        main_override = next((o for o in data if o["branch_id"] == MAIN_BRANCH_ID), None)
        assert main_override is not None, "Expected an override for Main Branch"
        assert "prices" in main_override
        assert "retail" in main_override["prices"]
        # Pre-existing override: retail=95.5
        assert float(main_override["prices"]["retail"]) == 95.5

    def test_override_structure_has_required_fields(self, api_client, auth_headers):
        """Each override doc must have product_id, branch_id, prices."""
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        data = response.json()
        if data:
            o = data[0]
            assert "product_id" in o
            assert "branch_id" in o
            assert "prices" in o
            # _id must be excluded
            assert "_id" not in o, "MongoDB _id should be excluded"

    def test_unauthorized_returns_401(self, api_client):
        """Branch prices endpoint should require authentication."""
        response = api_client.get(f"{BASE_URL}/api/branch-prices")
        assert response.status_code == 401


class TestBranchPricesPut:
    """Tests for PUT /branch-prices/{product_id} endpoint."""

    def test_upsert_branch_price_returns_200(self, api_client, auth_headers):
        """PUT should succeed and return the saved document."""
        response = api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={
                "branch_id": SAMPOLI_BRANCH_ID,
                "prices": {"retail": 99.0, "wholesale": 85.0},
                "cost_price": 72.0,
            },
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_upsert_returns_correct_data(self, api_client, auth_headers):
        """PUT response should reflect the set prices."""
        response = api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={
                "branch_id": SAMPOLI_BRANCH_ID,
                "prices": {"retail": 99.0, "wholesale": 85.0},
                "cost_price": 72.0,
            },
            headers=auth_headers
        )
        data = response.json()
        assert data["product_id"] == TEST_PRODUCT_ID
        assert data["branch_id"] == SAMPOLI_BRANCH_ID
        assert float(data["prices"]["retail"]) == 99.0
        assert float(data["prices"]["wholesale"]) == 85.0
        assert float(data["cost_price"]) == 72.0
        assert "_id" not in data

    def test_upsert_persists_to_db(self, api_client, auth_headers):
        """After PUT, GET should return the new override."""
        # First set it
        api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"branch_id": SAMPOLI_BRANCH_ID, "prices": {"retail": 99.0}},
            headers=auth_headers
        )
        # Then verify
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        data = response.json()
        sampoli_override = next((o for o in data if o["branch_id"] == SAMPOLI_BRANCH_ID), None)
        assert sampoli_override is not None, "Sampoli override not found after PUT"
        assert float(sampoli_override["prices"]["retail"]) == 99.0

    def test_upsert_without_branch_id_returns_400(self, api_client, auth_headers):
        """PUT without branch_id should return 400."""
        response = api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"prices": {"retail": 99.0}},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_upsert_negative_price_returns_400(self, api_client, auth_headers):
        """PUT with negative price should return 400."""
        response = api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"branch_id": SAMPOLI_BRANCH_ID, "prices": {"retail": -10.0}},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_upsert_invalid_product_returns_404(self, api_client, auth_headers):
        """PUT for non-existent product should return 404."""
        response = api_client.put(
            f"{BASE_URL}/api/branch-prices/non-existent-product-id",
            json={"branch_id": MAIN_BRANCH_ID, "prices": {"retail": 99.0}},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestBranchPricesDelete:
    """Tests for DELETE /branch-prices/{product_id} endpoint."""

    def test_delete_existing_override_returns_200(self, api_client, auth_headers):
        """DELETE an existing override should succeed."""
        # First ensure Sampoli override exists
        api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"branch_id": SAMPOLI_BRANCH_ID, "prices": {"retail": 99.0}},
            headers=auth_headers
        )
        # Now delete it
        response = api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_delete_returns_message(self, api_client, auth_headers):
        """DELETE response should contain success message."""
        # Ensure override exists first
        api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"branch_id": SAMPOLI_BRANCH_ID, "prices": {"retail": 99.0}},
            headers=auth_headers
        )
        response = api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        assert "message" in data

    def test_delete_removes_from_db(self, api_client, auth_headers):
        """After DELETE, GET should not return the deleted override."""
        # Ensure override exists
        api_client.put(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            json={"branch_id": SAMPOLI_BRANCH_ID, "prices": {"retail": 99.0}},
            headers=auth_headers
        )
        # Delete it
        api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        # Verify it's gone
        response = api_client.get(
            f"{BASE_URL}/api/branch-prices",
            params={"product_id": TEST_PRODUCT_ID},
            headers=auth_headers
        )
        data = response.json()
        sampoli = next((o for o in data if o["branch_id"] == SAMPOLI_BRANCH_ID), None)
        assert sampoli is None, "Sampoli override should have been deleted"

    def test_delete_non_existent_override_returns_404(self, api_client, auth_headers):
        """DELETE for non-existent override should return 404."""
        # Ensure Sampoli is deleted first
        api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        # Try to delete again (should 404)
        response = api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestProductSearchDetailWithBranchPrices:
    """Tests for GET /products/search-detail with branch-specific prices."""

    def test_search_returns_products(self, api_client, auth_headers):
        """Search-detail should return results for a valid query."""
        response = api_client.get(
            f"{BASE_URL}/api/products/search-detail",
            params={"q": "VITMIN", "branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_search_applies_branch_price_override(self, api_client, auth_headers):
        """When branch has an override, search-detail should return override prices."""
        # Main branch override: retail=95.5, wholesale=82.0 (pre-existing)
        response = api_client.get(
            f"{BASE_URL}/api/products/search-detail",
            params={"q": "VITMIN", "branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        vitmin = next((p for p in data if p["id"] == TEST_PRODUCT_ID), None)
        assert vitmin is not None, "VITMIN product not in search results"
        # Should have override prices, not global
        assert float(vitmin["prices"].get("retail", 0)) == 95.5, (
            f"Expected override retail=95.5, got {vitmin['prices'].get('retail')}"
        )

    def test_search_uses_global_price_when_no_override(self, api_client, auth_headers):
        """When branch has no override, search-detail should use global prices."""
        # Ensure Sampoli has no override for this product
        api_client.delete(
            f"{BASE_URL}/api/branch-prices/{TEST_PRODUCT_ID}",
            params={"branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        response = api_client.get(
            f"{BASE_URL}/api/products/search-detail",
            params={"q": "VITMIN", "branch_id": SAMPOLI_BRANCH_ID},
            headers=auth_headers
        )
        data = response.json()
        vitmin = next((p for p in data if p["id"] == TEST_PRODUCT_ID), None)
        assert vitmin is not None
        # Should use global prices (retail=370, wholesale=340)
        assert float(vitmin["prices"].get("retail", 0)) == 370.0, (
            f"Expected global retail=370, got {vitmin['prices'].get('retail')}"
        )

    def test_search_without_query_returns_empty(self, api_client, auth_headers):
        """Empty query should return empty list."""
        response = api_client.get(
            f"{BASE_URL}/api/products/search-detail",
            params={"q": ""},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data == [] or isinstance(data, list)


class TestProductDetailPage:
    """Tests for GET /products/{id}/detail endpoint."""

    def test_product_detail_returns_200(self, api_client, auth_headers):
        """Product detail should return 200 for a valid product."""
        response = api_client.get(
            f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}/detail",
            params={"branch_id": MAIN_BRANCH_ID},
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_product_detail_has_required_keys(self, api_client, auth_headers):
        """Product detail response must have product, inventory, cost, repacks, vendors."""
        response = api_client.get(
            f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}/detail",
            headers=auth_headers
        )
        data = response.json()
        for key in ["product", "inventory", "cost", "repacks", "vendors"]:
            assert key in data, f"Missing '{key}' in product detail response"

    def test_product_detail_inventory_on_hand_map(self, api_client, auth_headers):
        """Inventory should have on_hand dict with branch_id keys."""
        response = api_client.get(
            f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}/detail",
            headers=auth_headers
        )
        data = response.json()
        inv = data["inventory"]
        assert "on_hand" in inv, "Missing on_hand in inventory"
        assert isinstance(inv["on_hand"], dict)

    def test_product_detail_no_mongo_id(self, api_client, auth_headers):
        """Product detail should not expose MongoDB _id."""
        response = api_client.get(
            f"{BASE_URL}/api/products/{TEST_PRODUCT_ID}/detail",
            headers=auth_headers
        )
        data = response.json()
        assert "_id" not in data
        assert "_id" not in data.get("product", {})

    def test_invalid_product_returns_404(self, api_client, auth_headers):
        """Invalid product ID should return 404."""
        response = api_client.get(
            f"{BASE_URL}/api/products/invalid-product-id/detail",
            headers=auth_headers
        )
        assert response.status_code == 404
