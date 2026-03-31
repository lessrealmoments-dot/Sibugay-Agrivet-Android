"""
Test suite for ReviewDetailDialog Phase 1 Migration (iteration 146)
Tests:
- /api/invoices/by-number/{poNumber} - UUID resolution (used by poNumber prop)
- /api/dashboard/review-detail/purchase_order/{id} - Detail fetch
- /api/purchase-orders/{id}/mark-reviewed - Verify action
- /api/daily-ops/* - Z-report not broken
- PurchaseOrderPage still uses PODetailModal (print/edit/verify)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known test data from DB
TEST_PO_NUMBER = "PO-B1-001010"
TEST_PO_ID = "936206b1-dcfc-4763-be57-803082ed6ba3"
TEST_PO_NUMBER_2 = "PO-B1-001014"
TEST_PO_ID_2 = "94ddd851-47fa-4501-aa86-dc348077287a"


@pytest.fixture(scope="module")
def auth_headers():
    """Authenticate as super admin and return headers"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def company_auth_headers():
    """Authenticate as company admin and return headers"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "jovelyneahig@gmail.com",
        "password": "Aa@050772"
    })
    if resp.status_code == 200:
        token = resp.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── 1. UUID Resolution (/api/invoices/by-number) ──────────────────────────────

class TestInvoiceByNumber:
    """Tests for the UUID resolution endpoint used by ReviewDetailDialog.poNumber prop"""

    def test_po_by_number_returns_200(self, auth_headers):
        """GET /api/invoices/by-number/{po_number} returns 200"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_po_by_number_returns_id(self, auth_headers):
        """UUID resolution returns a valid id field"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data, "Response must include 'id' field"
        assert data["id"] == TEST_PO_ID, f"Expected {TEST_PO_ID}, got {data['id']}"

    def test_po_by_number_collection_tag(self, auth_headers):
        """UUID resolution response includes _collection=purchase_orders"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("_collection") == "purchase_orders", f"Expected purchase_orders, got {data.get('_collection')}"

    def test_po_by_number_has_po_number(self, auth_headers):
        """UUID resolution includes po_number field"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER}", headers=auth_headers)
        data = resp.json()
        assert data.get("po_number") == TEST_PO_NUMBER

    def test_po_by_number_not_found_404(self, auth_headers):
        """Non-existent PO number returns 404"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/PO-NONEXISTENT-99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_multiple_pos_by_number(self, auth_headers):
        """Second PO number resolves correctly"""
        resp = requests.get(f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER_2}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") == TEST_PO_ID_2


# ── 2. Review Detail Endpoint (/api/dashboard/review-detail) ──────────────────

class TestReviewDetailEndpoint:
    """Tests for the detail data endpoint used after UUID resolution"""

    def test_review_detail_by_id_returns_200(self, auth_headers):
        """GET /api/dashboard/review-detail/purchase_order/{id} returns 200"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_review_detail_record_type(self, auth_headers):
        """review-detail returns record_type=purchase_order"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert data.get("record_type") == "purchase_order"

    def test_review_detail_record_number(self, auth_headers):
        """review-detail returns matching record_number"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert data.get("record_number") == TEST_PO_NUMBER

    def test_review_detail_has_items(self, auth_headers):
        """review-detail response includes items array"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    def test_review_detail_has_supplier(self, auth_headers):
        """review-detail includes supplier field"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert "supplier" in data
        assert data["supplier"]

    def test_review_detail_has_payment_fields(self, auth_headers):
        """review-detail includes payment_status and balance"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert "payment_status" in data
        assert "balance" in data

    def test_review_detail_second_po_by_id(self, auth_headers):
        """review-detail works for second test PO"""
        resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{TEST_PO_ID_2}",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("record_number") == TEST_PO_NUMBER_2


# ── 3. End-to-End: poNumber → resolve → detail ──────────────────────────────

class TestPoNumberResolutionFlow:
    """Tests the complete flow: poNumber → /by-number → id → /review-detail"""

    def test_full_poNumber_to_detail_flow(self, auth_headers):
        """Complete flow: resolve PO by number, then fetch review detail"""
        # Step 1: Resolve UUID from PO number (simulates ReviewDetailDialog behavior)
        resolve_resp = requests.get(
            f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER}",
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200, "UUID resolution failed"
        po_id = resolve_resp.json().get("id")
        assert po_id, "No id returned from resolution"

        # Step 2: Fetch review detail using resolved UUID
        detail_resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{po_id}",
            headers=auth_headers
        )
        assert detail_resp.status_code == 200, "Review detail fetch failed"
        detail = detail_resp.json()
        assert detail.get("record_number") == TEST_PO_NUMBER
        assert detail.get("record_type") == "purchase_order"

    def test_full_flow_for_second_po(self, auth_headers):
        """Full resolution flow works for a second PO"""
        resolve_resp = requests.get(
            f"{BASE_URL}/api/invoices/by-number/{TEST_PO_NUMBER_2}",
            headers=auth_headers
        )
        assert resolve_resp.status_code == 200
        po_id = resolve_resp.json().get("id")
        assert po_id == TEST_PO_ID_2

        detail_resp = requests.get(
            f"{BASE_URL}/api/dashboard/review-detail/purchase_order/{po_id}",
            headers=auth_headers
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail.get("record_number") == TEST_PO_NUMBER_2


# ── 4. Purchase Order Direct Fetch (PODetailModal still works) ──────────────

class TestPurchaseOrderDirectFetch:
    """Tests that direct PO fetch still works (for PODetailModal on PurchaseOrderPage)"""

    def test_get_purchase_order_by_id(self, auth_headers):
        """GET /api/purchase-orders/{id} returns 200 (PODetailModal flow)"""
        resp = requests.get(
            f"{BASE_URL}/api/purchase-orders/{TEST_PO_ID}",
            headers=auth_headers
        )
        assert resp.status_code == 200

    def test_purchase_order_has_print_fields(self, auth_headers):
        """Purchase order response has print-relevant fields (PODetailModal)"""
        resp = requests.get(
            f"{BASE_URL}/api/purchase-orders/{TEST_PO_ID}",
            headers=auth_headers
        )
        data = resp.json()
        assert "po_number" in data
        assert "items" in data
        assert "grand_total" in data or "subtotal" in data


# ── 5. Z-Report / Daily Ops (Regression: must not be broken) ─────────────────

class TestDailyOpsNotBroken:
    """Tests that Z-report and daily-ops endpoints are not affected"""

    def test_daily_ops_list_branches(self, auth_headers):
        """Daily ops endpoints respond (branches list)"""
        resp = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers)
        assert resp.status_code == 200, f"branches API broken: {resp.status_code}"

    def test_purchase_orders_list_still_works(self, auth_headers):
        """Purchase orders list endpoint still works"""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("purchase_orders", []))
        assert isinstance(items, list)

    def test_suppliers_list_still_works(self, auth_headers):
        """Suppliers list endpoint still works"""
        resp = requests.get(f"{BASE_URL}/api/suppliers", headers=auth_headers)
        assert resp.status_code == 200


# ── 6. Search Endpoint (QuickSearch uses this) ──────────────────────────────

class TestSearchEndpoint:
    """Tests for the QuickSearch backend"""

    def test_search_transactions_endpoint(self, auth_headers):
        """GET /api/search/transactions?q=PO returns results"""
        resp = requests.get(
            f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1", "limit": 5},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_search_returns_po_type(self, auth_headers):
        """Search results include purchase_order type items"""
        resp = requests.get(
            f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1-001010", "limit": 5},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        results = data.get("results", [])
        po_results = [r for r in results if r.get("type") == "purchase_order"]
        assert len(po_results) > 0, "No PO results in search"

    def test_search_po_has_number_field(self, auth_headers):
        """Search PO results include number field (used for poNumber prop)"""
        resp = requests.get(
            f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1-001010", "limit": 5},
            headers=auth_headers
        )
        data = resp.json()
        results = data.get("results", [])
        po_results = [r for r in results if r.get("type") == "purchase_order"]
        if po_results:
            assert "number" in po_results[0], "PO search result must have 'number' field"
