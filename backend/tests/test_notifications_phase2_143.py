"""
Notification System Phase 2 Tests - Iteration 143
Tests: category_counts, category filter, severity/category fields, mark-all-read
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "janmarkeahig@gmail.com"
ADMIN_PASS = "Aa@58798546521325"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token in auth response")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestNotificationsAPI:
    """Core notification endpoint tests for Phase 2 overhaul"""

    def test_get_notifications_returns_200(self, auth_headers):
        """GET /api/notifications returns 200"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        print("PASS: GET /api/notifications returns 200")

    def test_get_notifications_has_required_keys(self, auth_headers):
        """Response has notifications, unread_count, total, category_counts"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications" in data, "Missing 'notifications' key"
        assert "unread_count" in data, "Missing 'unread_count' key"
        assert "total" in data, "Missing 'total' key"
        assert "category_counts" in data, "Missing 'category_counts' key"
        print("PASS: Response has all required top-level keys")

    def test_category_counts_has_all_5_categories(self, auth_headers):
        """category_counts includes security, action, approvals, operations, finance"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        counts = data.get("category_counts", {})
        required_cats = ["security", "action", "approvals", "operations", "finance"]
        for cat in required_cats:
            assert cat in counts, f"Missing category '{cat}' in category_counts"
        print(f"PASS: category_counts has all 5 categories: {list(counts.keys())}")

    def test_category_counts_structure(self, auth_headers):
        """Each category count entry has total, unread, label fields"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        counts = data.get("category_counts", {})
        for cat, cat_data in counts.items():
            assert "total" in cat_data, f"Category '{cat}' missing 'total'"
            assert "unread" in cat_data, f"Category '{cat}' missing 'unread'"
            assert "label" in cat_data, f"Category '{cat}' missing 'label'"
            assert isinstance(cat_data["total"], int), f"'{cat}'.total should be int"
            assert isinstance(cat_data["unread"], int), f"'{cat}'.unread should be int"
        print("PASS: All category counts have total, unread, label fields")

    def test_notifications_have_is_read_field(self, auth_headers):
        """Each notification in response has is_read field"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        notifications = data.get("notifications", [])
        assert len(notifications) > 0, "No notifications returned — DB may be empty"
        for n in notifications[:5]:
            assert "is_read" in n, f"Notification {n.get('id')} missing 'is_read'"
            assert isinstance(n["is_read"], bool), f"'is_read' should be bool, got {type(n['is_read'])}"
        print(f"PASS: {len(notifications)} notifications all have is_read field")

    def test_notifications_have_category_field(self, auth_headers):
        """Each notification has a category field"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        notifications = data.get("notifications", [])
        assert len(notifications) > 0, "No notifications returned"
        valid_categories = {"security", "action", "approvals", "operations", "finance"}
        for n in notifications[:5]:
            assert "category" in n, f"Notification missing 'category' field"
            assert n["category"] in valid_categories, \
                f"Invalid category '{n['category']}', expected one of {valid_categories}"
        print("PASS: All notifications have valid category field")

    def test_notifications_have_severity_field(self, auth_headers):
        """Each notification has a severity field"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        notifications = data.get("notifications", [])
        assert len(notifications) > 0, "No notifications returned"
        valid_severities = {"critical", "warning", "info"}
        for n in notifications[:5]:
            assert "severity" in n, f"Notification missing 'severity' field"
            assert n["severity"] in valid_severities, \
                f"Invalid severity '{n['severity']}', expected one of {valid_severities}"
        print("PASS: All notifications have valid severity field")

    def test_category_filter_security(self, auth_headers):
        """GET /api/notifications?category=security returns security notifications"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers,
                           params={"category": "security", "limit": 20})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        notifications = data.get("notifications", [])
        # If any are returned, verify they are security category
        for n in notifications:
            assert n.get("category") == "security" or n.get("type") == "security_alert", \
                f"Non-security notification in security filter: type={n.get('type')}, cat={n.get('category')}"
        print(f"PASS: Category filter=security returns {len(notifications)} notifications, all correct category")

    def test_category_filter_approvals(self, auth_headers):
        """GET /api/notifications?category=approvals returns approvals notifications"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers,
                           params={"category": "approvals", "limit": 20})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        notifications = data.get("notifications", [])
        approvals_types = {
            "credit_sale", "price_override", "discount_given", "below_cost_sale",
            "admin_action", "return_pullout_loss", "employee_advance", "reservation_expired"
        }
        for n in notifications:
            is_approvals = n.get("category") == "approvals" or n.get("type") in approvals_types
            assert is_approvals, \
                f"Non-approvals notification in approvals filter: type={n.get('type')}, cat={n.get('category')}"
        print(f"PASS: Category filter=approvals returns {len(notifications)} notifications, all correct category")

    def test_category_filter_operations(self, auth_headers):
        """GET /api/notifications?category=operations returns operations notifications"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers,
                           params={"category": "operations", "limit": 20})
        assert resp.status_code == 200
        data = resp.json()
        notifications = data.get("notifications", [])
        operations_types = {"transfer_incoming", "transfer_accepted", "ap_payment"}
        for n in notifications:
            is_ops = n.get("category") == "operations" or n.get("type") in operations_types
            assert is_ops, \
                f"Non-operations notification in operations filter: type={n.get('type')}, cat={n.get('category')}"
        print(f"PASS: Category filter=operations returns {len(notifications)} notifications, all correct category")

    def test_total_count_is_positive(self, auth_headers):
        """There are notifications in DB (479 expected)"""
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", 0)
        assert total > 0, f"Expected >0 total notifications, got {total}"
        print(f"PASS: Total notifications in DB: {total}")

    def test_mark_all_read_endpoint(self, auth_headers):
        """PUT /api/notifications/mark-all-read returns 200"""
        resp = requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "message" in data, "Response should have 'message' key"
        print(f"PASS: mark-all-read: {data}")

    def test_after_mark_all_read_unread_count_zero(self, auth_headers):
        """After marking all read, unread_count should be 0"""
        # Mark all read
        requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=auth_headers)
        # Then get notifications
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        unread = data.get("unread_count", -1)
        assert unread == 0, f"Expected unread_count=0 after mark-all-read, got {unread}"
        print(f"PASS: unread_count=0 after mark-all-read")

    def test_pagination_skip_limit(self, auth_headers):
        """Pagination: skip and limit params work correctly"""
        # Get first 10
        r1 = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 10, "skip": 0})
        assert r1.status_code == 200
        first_10 = r1.json().get("notifications", [])
        # Get next 10
        r2 = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers, params={"limit": 10, "skip": 10})
        assert r2.status_code == 200
        next_10 = r2.json().get("notifications", [])
        if len(first_10) == 10 and len(next_10) > 0:
            first_ids = {n["id"] for n in first_10}
            next_ids = {n["id"] for n in next_10}
            assert first_ids.isdisjoint(next_ids), "Skip pagination returned overlapping results"
        print(f"PASS: Pagination works - first page: {len(first_10)}, second page: {len(next_10)}")
