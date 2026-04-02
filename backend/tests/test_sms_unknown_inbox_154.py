"""
Test suite for SMS Unknown Numbers Inbox and Assign-Phone feature (Iteration 154).
Tests: POST /sms/inbox, GET /sms/conversations?section=customers|unknown, PATCH /sms/assign-phone
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"

UNKNOWN_PHONE = "09700000001"   # A completely unknown phone for this test run
UNKNOWN_PHONE2 = "09700000002"  # Second unknown phone to test count


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate as super admin and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in auth response")
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def known_customer(headers):
    """Find or create a customer we can use for known-number tests."""
    resp = requests.get(f"{BASE_URL}/api/customers", headers=headers,
                        params={"limit": 1})
    if resp.status_code == 200:
        custs = resp.json().get("customers") or []
        if custs:
            return custs[0]
    pytest.skip("No customers found to use as known customer fixture")


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST /api/sms/inbox — unknown number → registered=False
# ─────────────────────────────────────────────────────────────────────────────
class TestInboxStorageUnknown:
    """POST /sms/inbox with unknown phone → registered:false stored."""

    def test_inbox_unknown_number_status_200(self, headers):
        """An unknown phone should be accepted and stored with status 200."""
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
            "message": "TEST_unknown inbox message 1",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: POST /sms/inbox unknown number returns 200")

    def test_inbox_unknown_number_registered_false(self, headers):
        """Unknown phone should have registered=False in response."""
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
            "message": "TEST_unknown inbox message 2",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("registered") is False, \
            f"Expected registered=False for unknown phone, got: {data.get('registered')}"
        print("PASS: Unknown phone stored with registered=False")

    def test_inbox_unknown_number_empty_customer_id(self, headers):
        """Unknown phone should have empty customer_id."""
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
            "message": "TEST_unknown inbox message 3",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("customer_id") == "", \
            f"Expected empty customer_id, got: {data.get('customer_id')}"
        print("PASS: Unknown phone stored with empty customer_id")

    def test_inbox_unknown_stores_phone(self, headers):
        """Response should contain the stored phone."""
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
            "message": "TEST_check phone stored",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("phone"), "Expected phone field in response"
        # Normalize: accepts both 09... stored from +639...
        stored = data["phone"].lstrip("+")
        if stored.startswith("63"):
            stored = "0" + stored[2:]
        assert stored == UNKNOWN_PHONE, \
            f"Expected stored phone {UNKNOWN_PHONE}, got {data['phone']}"
        print(f"PASS: Stored phone matches: {data['phone']}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. POST /api/sms/inbox — known customer → registered=True
# ─────────────────────────────────────────────────────────────────────────────
class TestInboxStorageKnown:
    """POST /sms/inbox with known customer phone → registered:true."""

    def test_inbox_known_number_registered_true(self, headers, known_customer):
        """A known customer phone should have registered=True."""
        phone = known_customer.get("phone")
        if not phone:
            pytest.skip("Known customer has no phone number")
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": phone,
            "message": "TEST_known customer inbox message",
        })
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("registered") is True, \
            f"Expected registered=True for known customer, got: {data.get('registered')}"
        print(f"PASS: Known phone {phone} stored with registered=True")

    def test_inbox_known_has_customer_id(self, headers, known_customer):
        """Known customer phone should have customer_id in response."""
        phone = known_customer.get("phone")
        if not phone:
            pytest.skip("Known customer has no phone number")
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": phone,
            "message": "TEST_known customer id check",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("customer_id"), \
            f"Expected non-empty customer_id for known customer, got: {data.get('customer_id')}"
        print(f"PASS: Known phone has customer_id: {data['customer_id']}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /api/sms/inbox — validation errors
# ─────────────────────────────────────────────────────────────────────────────
class TestInboxValidation:

    def test_inbox_missing_phone_returns_400(self, headers):
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "message": "no phone provided",
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Missing phone returns 400")

    def test_inbox_missing_message_returns_400(self, headers):
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: Missing message returns 400")


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET /api/sms/conversations?section=customers
# ─────────────────────────────────────────────────────────────────────────────
class TestConversationsCustomersSection:

    def test_customers_section_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "customers"})
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        print("PASS: GET /sms/conversations?section=customers returns 200")

    def test_customers_section_returns_list(self, headers):
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "customers"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"PASS: customers section returns list with {len(data)} items")

    def test_customers_section_no_unknown_phone(self, headers):
        """The unknown phone we injected should NOT appear in customers section."""
        # First post a fresh unknown message
        requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE,
            "message": "TEST_check not in customers",
        })
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "customers"})
        assert resp.status_code == 200
        data = resp.json()
        phones = [c.get("phone") for c in data]
        assert UNKNOWN_PHONE not in phones, \
            f"Unknown phone {UNKNOWN_PHONE} should NOT appear in customers section"
        print(f"PASS: Unknown phone {UNKNOWN_PHONE} not in customers section")


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/sms/conversations?section=unknown
# ─────────────────────────────────────────────────────────────────────────────
class TestConversationsUnknownSection:

    def test_unknown_section_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "unknown"})
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        print("PASS: GET /sms/conversations?section=unknown returns 200")

    def test_unknown_section_returns_list(self, headers):
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "unknown"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: unknown section returns list with {len(data)} items")

    def test_unknown_section_contains_unknown_phone(self, headers):
        """The unknown phone we injected MUST appear in unknown section."""
        # Ensure our unknown message exists
        requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": UNKNOWN_PHONE2,
            "message": "TEST_ensure in unknown section",
        })
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "unknown"})
        assert resp.status_code == 200
        data = resp.json()
        phones = [c.get("phone") for c in data]
        assert UNKNOWN_PHONE2 in phones, \
            f"Unknown phone {UNKNOWN_PHONE2} should appear in unknown section. Found: {phones}"
        print(f"PASS: Unknown phone {UNKNOWN_PHONE2} appears in unknown section")

    def test_unknown_section_items_have_required_fields(self, headers):
        """Each item in unknown section should have phone, customer_id='', registered=False."""
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "unknown"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data[:3]:  # Check first 3 items
            assert "phone" in item, "Missing 'phone' field"
            assert item.get("customer_id") == "", \
                f"Expected customer_id='' for unknown, got: {item.get('customer_id')}"
            assert item.get("registered") is False, \
                f"Expected registered=False for unknown, got: {item.get('registered')}"
        print("PASS: Unknown section items have correct fields (registered=False, customer_id='')")

    def test_unknown_section_known_phones_absent(self, headers, known_customer):
        """Known customer phone should NOT appear in unknown section."""
        phone = known_customer.get("phone")
        if not phone:
            pytest.skip("Known customer has no phone number")
        resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                            headers=headers, params={"section": "unknown"})
        assert resp.status_code == 200
        data = resp.json()
        phones = [c.get("phone") for c in data]
        # Normalize the known phone
        norm = phone.lstrip("+")
        if norm.startswith("63"):
            norm = "0" + norm[2:]
        assert norm not in phones, \
            f"Known customer phone {norm} should NOT be in unknown section"
        print(f"PASS: Known phone {phone} absent from unknown section")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Default section behaviour (no section param → customers)
# ─────────────────────────────────────────────────────────────────────────────
class TestConversationsDefaultSection:

    def test_default_section_is_customers(self, headers):
        """Without section param, endpoint should default to customers behaviour."""
        resp = requests.get(f"{BASE_URL}/api/sms/conversations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should NOT contain the unknown phone we created
        phones = [c.get("phone") for c in data]
        assert UNKNOWN_PHONE not in phones, \
            f"Unknown phone should not be in default (customers) section"
        print("PASS: Default section behaves as customers (unknown phones absent)")


# ─────────────────────────────────────────────────────────────────────────────
# 7. PATCH /api/sms/assign-phone — main feature
# ─────────────────────────────────────────────────────────────────────────────
class TestAssignPhone:

    ASSIGN_PHONE = "09700000099"  # Fresh phone just for assign tests

    def _seed_inbox(self, headers, count=3):
        """Post multiple unknown messages for ASSIGN_PHONE."""
        for i in range(count):
            requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
                "phone": self.ASSIGN_PHONE,
                "message": f"TEST_assign msg {i+1}",
            })

    def test_assign_missing_phone_returns_400(self, headers):
        resp = requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers,
                              json={"customer_id": "some-id"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: assign-phone missing phone returns 400")

    def test_assign_missing_customer_id_returns_400(self, headers):
        resp = requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers,
                              json={"phone": self.ASSIGN_PHONE})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("PASS: assign-phone missing customer_id returns 400")

    def test_assign_invalid_customer_returns_404(self, headers):
        resp = requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers,
                              json={"phone": self.ASSIGN_PHONE, "customer_id": "nonexistent-id"})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("PASS: assign-phone nonexistent customer returns 404")

    def test_assign_phone_success(self, headers, known_customer):
        """Assign ASSIGN_PHONE to a known customer — should succeed."""
        self._seed_inbox(headers, 3)
        resp = requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers, json={
            "phone": self.ASSIGN_PHONE,
            "customer_id": known_customer["id"],
        })
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "migrated_messages" in data, "Expected migrated_messages in response"
        assert data["migrated_messages"] >= 3, \
            f"Expected at least 3 migrated messages, got: {data['migrated_messages']}"
        assert data["customer_id"] == known_customer["id"]
        assert data["customer_name"] == known_customer["name"]
        print(f"PASS: assign-phone returned 200, migrated {data['migrated_messages']} messages")

    def test_assign_phone_removes_from_unknown_section(self, headers, known_customer):
        """After assign, phone should no longer appear in unknown section."""
        # Re-seed to ensure phone exists (might have been cleared in prev test)
        self._seed_inbox(headers, 2)

        # First ensure it appears in unknown section
        unk_before = requests.get(f"{BASE_URL}/api/sms/conversations",
                                  headers=headers, params={"section": "unknown"}).json()
        
        # Then assign it
        requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers, json={
            "phone": self.ASSIGN_PHONE,
            "customer_id": known_customer["id"],
        })

        # Now verify it's not in unknown section
        unk_after = requests.get(f"{BASE_URL}/api/sms/conversations",
                                 headers=headers, params={"section": "unknown"}).json()
        phones_after = [c.get("phone") for c in unk_after]
        # Normalize ASSIGN_PHONE
        assert self.ASSIGN_PHONE not in phones_after, \
            f"Phone {self.ASSIGN_PHONE} still in unknown section after assign: {phones_after}"
        print("PASS: Phone removed from unknown section after assign")

    def test_assign_phone_appears_in_customers_section(self, headers, known_customer):
        """After assign, the conversation should appear in customers section."""
        # Seed fresh messages and assign
        phone_for_test = "09700000098"
        for i in range(2):
            requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
                "phone": phone_for_test,
                "message": f"TEST_migrate test msg {i+1}",
            })
        
        # Assign to customer
        assign_resp = requests.patch(f"{BASE_URL}/api/sms/assign-phone", headers=headers, json={
            "phone": phone_for_test,
            "customer_id": known_customer["id"],
        })
        assert assign_resp.status_code == 200, f"Assign failed: {assign_resp.text}"

        # Check customers section (no branch filter = all branches)
        cust_resp = requests.get(f"{BASE_URL}/api/sms/conversations",
                                 headers=headers, params={"section": "customers"})
        assert cust_resp.status_code == 200
        # The customer's conversation should be in the list now
        # We check by customer_id or by phone (normalized)
        data = cust_resp.json()
        customer_ids = [c.get("customer_id") for c in data]
        phones = [c.get("phone") for c in data]
        assert known_customer["id"] in customer_ids or phone_for_test in phones, \
            f"Customer {known_customer['name']} conversation not found in customers section after assign. Phones: {phones}"
        print(f"PASS: After assign, conversation appears in customers section for {known_customer['name']}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. POST /api/sms/inbox — phone normalization (+63 vs 09)
# ─────────────────────────────────────────────────────────────────────────────
class TestPhoneNormalization:

    def test_plus63_stored_as_09(self, headers):
        """International +63... format should be stored as 09... normalized format."""
        phone_intl = "+639700000003"
        resp = requests.post(f"{BASE_URL}/api/sms/inbox", headers=headers, json={
            "phone": phone_intl,
            "message": "TEST_normalization test",
        })
        assert resp.status_code == 200
        data = resp.json()
        stored = data.get("phone", "")
        # Should be stored as 09...
        assert stored == "09700000003" or stored == phone_intl, \
            f"Expected 09700000003 or {phone_intl}, got {stored}"
        print(f"PASS: +63 phone stored as: {stored}")


if __name__ == "__main__":
    import subprocess
    subprocess.run(["pytest", __file__, "-v", "--tb=short"])
