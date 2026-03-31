"""
Tests for Phase 1-3 Security Alert Notification Enrichment (iteration 145)
- Phase 1: Authenticated PIN alerts with user_role, user_email, branch_name
- Phase 2: QR Terminal alerts with terminal_label, doc_number, counterparty, doc_id
- Phase 3: Frontend SecurityAlertDetail component (tested via Playwright)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Login helpers ─────────────────────────────────────────────────────────────

def login(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    return None


@pytest.fixture(scope="module")
def admin_token():
    token = login("janmarkeahig@gmail.com", "Aa@58798546521325")
    if not token:
        pytest.skip("Admin login failed")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Backend: Notifications API ────────────────────────────────────────────────

class TestNotificationsAPI:
    """Test GET /api/notifications returns security_alert notifications"""

    def test_notifications_endpoint_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "notifications" in data, "Response missing 'notifications' key"
        print(f"PASS: Notifications endpoint 200 — total={data.get('total', '?')}, unread={data.get('unread_count', '?')}")

    def test_notifications_has_security_category_counts(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        counts = data.get("category_counts", {})
        assert "security" in counts, f"'security' key missing from category_counts: {list(counts.keys())}"
        sec_count = counts["security"].get("total", 0)
        assert sec_count >= 2, f"Expected >=2 security notifications, got {sec_count}"
        print(f"PASS: Security category count = {sec_count} total, {counts['security'].get('unread', 0)} unread")

    def test_security_filter_returns_security_alerts_only(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", params={"category": "security"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        notifs = data.get("notifications", [])
        assert len(notifs) >= 2, f"Expected >=2 security notifications, got {len(notifs)}"
        for n in notifs:
            assert n["category"] == "security", f"Non-security notif in filter: {n['category']}"
            assert n["type"] == "security_alert", f"Non-security_alert type: {n['type']}"
        print(f"PASS: Security filter returns {len(notifs)} security_alert notifications, all correct category/type")

    def test_demo_auth_notification_present(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", params={"category": "security"}, headers=admin_headers)
        assert resp.status_code == 200
        notifs = resp.json().get("notifications", [])
        ids = [n["id"] for n in notifs]
        assert "demo_sec_auth_001" in ids, f"demo_sec_auth_001 not found in: {ids}"
        print("PASS: demo_sec_auth_001 present in security notifications")

    def test_demo_qr_notification_present(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", params={"category": "security"}, headers=admin_headers)
        assert resp.status_code == 200
        notifs = resp.json().get("notifications", [])
        ids = [n["id"] for n in notifs]
        assert "demo_sec_qr_001" in ids, f"demo_sec_qr_001 not found in: {ids}"
        print("PASS: demo_sec_qr_001 present in security notifications")


# ── Phase 1: Authenticated PIN alert enrichment ────────────────────────────────

class TestPhase1AuthenticatedPINAlert:
    """Phase 1: auth alerts must include user_role, user_email, branch_name in metadata"""

    def _get_auth_notif(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", params={"category": "security"}, headers=admin_headers)
        assert resp.status_code == 200
        notifs = resp.json().get("notifications", [])
        for n in notifs:
            if n["id"] == "demo_sec_auth_001":
                return n
        pytest.skip("demo_sec_auth_001 not found")

    def test_auth_alert_has_alert_source_authenticated_pin(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("alert_source") == "authenticated_pin", f"Expected 'authenticated_pin', got '{m.get('alert_source')}'"
        print("PASS: alert_source = authenticated_pin")

    def test_auth_alert_has_user_role(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("user_role") == "manager", f"Expected 'manager', got '{m.get('user_role')}'"
        print(f"PASS: user_role = {m.get('user_role')}")

    def test_auth_alert_has_user_email(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("user_email") == "testmanager@test.com", f"Got: {m.get('user_email')}"
        print(f"PASS: user_email = {m.get('user_email')}")

    def test_auth_alert_has_branch_name(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("branch_name") == "Branch 1", f"Got: {m.get('branch_name')}"
        print(f"PASS: branch_name = {m.get('branch_name')}")

    def test_auth_alert_has_user_name(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("user_name") == "Test Manager", f"Got: {m.get('user_name')}"
        print(f"PASS: user_name = {m.get('user_name')}")

    def test_auth_alert_has_failure_count(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert isinstance(m.get("failure_count"), int), f"failure_count should be int, got: {type(m.get('failure_count'))}"
        assert m.get("failure_count") >= 1, f"failure_count should be >=1, got: {m.get('failure_count')}"
        print(f"PASS: failure_count = {m.get('failure_count')}")

    def test_auth_alert_has_action_label(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("action_label") == "Transaction Verification", f"Got: {m.get('action_label')}"
        print(f"PASS: action_label = {m.get('action_label')}")

    def test_auth_alert_message_contains_role(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        msg = n.get("message", "")
        # Message should reference role in message text
        assert "Manager" in msg or "manager" in msg, f"Role not in message: {msg}"
        print(f"PASS: Message contains role indicator: {msg[:100]}")

    def test_auth_alert_severity_is_warning(self, admin_headers):
        n = self._get_auth_notif(admin_headers)
        assert n.get("severity") == "warning", f"Expected 'warning', got '{n.get('severity')}'"
        print("PASS: severity = warning (failure_count=6, below lock threshold)")


# ── Phase 2: QR Terminal alert enrichment ──────────────────────────────────────

class TestPhase2QRTerminalAlert:
    """Phase 2: QR alerts must identify terminal, include doc enrichment"""

    def _get_qr_notif(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/notifications", params={"category": "security"}, headers=admin_headers)
        assert resp.status_code == 200
        notifs = resp.json().get("notifications", [])
        for n in notifs:
            if n["id"] == "demo_sec_qr_001":
                return n
        pytest.skip("demo_sec_qr_001 not found")

    def test_qr_alert_has_alert_source_qr_terminal(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("alert_source") == "qr_terminal", f"Expected 'qr_terminal', got '{m.get('alert_source')}'"
        print("PASS: alert_source = qr_terminal")

    def test_qr_alert_has_terminal_label_not_unknown_ip(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        terminal_label = m.get("terminal_label", "")
        assert terminal_label, "terminal_label is empty"
        assert "Unknown IP" not in terminal_label, f"terminal_label still says 'Unknown IP': {terminal_label}"
        assert "AgriSmart Terminal" in terminal_label, f"Expected 'AgriSmart Terminal' in: {terminal_label}"
        print(f"PASS: terminal_label = '{terminal_label}'")

    def test_qr_alert_terminal_label_includes_branch(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert "Branch 1" in m.get("terminal_label", ""), f"Branch 1 not in terminal_label: {m.get('terminal_label')}"
        print(f"PASS: terminal_label includes branch: {m.get('terminal_label')}")

    def test_qr_alert_has_doc_id(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        doc_id = m.get("doc_id", "")
        assert doc_id, "doc_id is empty"
        assert len(doc_id) > 10, f"doc_id looks too short: {doc_id}"
        print(f"PASS: doc_id = {doc_id}")

    def test_qr_alert_has_doc_number(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("doc_number") == "PO-B1-001010", f"Got: {m.get('doc_number')}"
        print(f"PASS: doc_number = {m.get('doc_number')}")

    def test_qr_alert_has_counterparty(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("counterparty") == "Test Supplier", f"Got: {m.get('counterparty')}"
        print(f"PASS: counterparty = {m.get('counterparty')}")

    def test_qr_alert_has_doc_amount(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("doc_amount") is not None, "doc_amount is None"
        assert float(m.get("doc_amount")) == 1000.0, f"Got: {m.get('doc_amount')}"
        print(f"PASS: doc_amount = {m.get('doc_amount')}")

    def test_qr_alert_has_locked_true(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("locked") is True, f"Expected locked=True, got: {m.get('locked')}"
        print("PASS: locked = True (failure_count=10 >= lock threshold)")

    def test_qr_alert_severity_is_critical(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        assert n.get("severity") == "critical", f"Expected 'critical', got '{n.get('severity')}'"
        print("PASS: severity = critical (locked state)")

    def test_qr_alert_message_mentions_agrismart_terminal(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        msg = n.get("message", "")
        assert "AgriSmart Terminal" in msg, f"'AgriSmart Terminal' not in message: {msg}"
        print(f"PASS: Message contains 'AgriSmart Terminal': {msg[:100]}")

    def test_qr_alert_message_mentions_doc_number(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        msg = n.get("message", "")
        assert "PO-B1-001010" in msg, f"'PO-B1-001010' not in message: {msg}"
        print(f"PASS: Message contains doc_number: {msg[:100]}")

    def test_qr_alert_has_action_label_receive_payment(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("action_label") == "Receive Payment", f"Got: {m.get('action_label')}"
        print(f"PASS: action_label = {m.get('action_label')}")

    def test_qr_alert_has_branch_name(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("branch_name") == "Branch 1", f"Got: {m.get('branch_name')}"
        print(f"PASS: branch_name = {m.get('branch_name')}")

    def test_qr_alert_failure_count_is_10(self, admin_headers):
        n = self._get_qr_notif(admin_headers)
        m = n.get("metadata", {})
        assert m.get("failure_count") == 10, f"Expected 10, got: {m.get('failure_count')}"
        print(f"PASS: failure_count = {m.get('failure_count')}")
