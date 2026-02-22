"""
Tests for AgriBooks PO Redesign:
- GET /purchase-orders (list, filter) - was missing @router.get decorator
- GET /purchase-orders/fund-balances - new live fund balance endpoint
- POST /purchase-orders with po_type=draft (no inventory change)
- POST /purchase-orders with po_type=cash (expense + inventory + deduct fund)
- POST /purchase-orders with po_type=terms (AP + inventory, no fund deduct)
- PO with per-line discounts (₱ and %)
- PO with overall discount (₱ and %)
- PO with freight
- PO with VAT
- Insufficient funds handling
- DR# stored on PO
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ── Main Branch - Downtown (DO NOT touch IPIL or SIAY)
MAIN_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"
TEST_PRODUCT_ID = "4dfff4e8-0379-473e-bbba-e9f8212473de"
TEST_PRODUCT_NAME = "updated by cashier"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "owner", "password": "521325"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def make_items(qty=2, unit_price=50, disc_type="amount", disc_val=0):
    return [{
        "product_id": TEST_PRODUCT_ID,
        "product_name": TEST_PRODUCT_NAME,
        "unit": "Box",
        "quantity": qty,
        "unit_price": unit_price,
        "discount_type": disc_type,
        "discount_value": disc_val,
    }]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: GET /purchase-orders (list endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListPurchaseOrders:
    """Test GET /purchase-orders - was missing @router.get decorator"""

    def test_list_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_list_returns_purchase_orders_and_total(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers)
        data = resp.json()
        assert "purchase_orders" in data, "Missing 'purchase_orders' key"
        assert "total" in data, "Missing 'total' key"
        assert isinstance(data["purchase_orders"], list)
        assert isinstance(data["total"], int)

    def test_list_each_po_has_required_fields(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers)
        orders = resp.json()["purchase_orders"]
        if orders:
            po = orders[0]
            for field in ["id", "po_number", "vendor", "status", "items"]:
                assert field in po, f"PO missing field: {field}"

    def test_list_with_limit_param(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["purchase_orders"]) <= 5

    def test_list_with_status_filter_draft(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"status": "draft", "limit": 50})
        assert resp.status_code == 200
        orders = resp.json()["purchase_orders"]
        for po in orders:
            assert po["status"] == "draft"

    def test_list_with_status_filter_received(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"status": "received", "limit": 50})
        assert resp.status_code == 200
        orders = resp.json()["purchase_orders"]
        for po in orders:
            assert po["status"] == "received"

    def test_list_without_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders")
        assert resp.status_code in [401, 403]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: GET /purchase-orders/fund-balances
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundBalances:
    """Test GET /purchase-orders/fund-balances - new endpoint"""

    def test_fund_balances_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/fund-balances",
                            headers=headers,
                            params={"branch_id": MAIN_BRANCH_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_fund_balances_has_cashier_and_safe(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/fund-balances",
                            headers=headers,
                            params={"branch_id": MAIN_BRANCH_ID})
        data = resp.json()
        assert "cashier" in data, "Missing 'cashier' field"
        assert "safe" in data, "Missing 'safe' field"

    def test_fund_balances_are_numeric(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/fund-balances",
                            headers=headers,
                            params={"branch_id": MAIN_BRANCH_ID})
        data = resp.json()
        assert isinstance(data["cashier"], (int, float)), "cashier must be numeric"
        assert isinstance(data["safe"], (int, float)), "safe must be numeric"
        assert data["cashier"] >= 0
        assert data["safe"] >= 0

    def test_fund_balances_without_branch_returns_200(self, headers):
        """Empty branch_id returns 200 (defaults gracefully)"""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/fund-balances",
                            headers=headers)
        assert resp.status_code == 200

    def test_fund_balances_without_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/fund-balances",
                            params={"branch_id": MAIN_BRANCH_ID})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: POST /purchase-orders with po_type=draft
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateDraftPO:
    """Test po_type=draft: save only, no inventory/fund change"""

    @pytest.fixture(scope="class")
    def draft_po(self, headers):
        payload = {
            "vendor": "TEST_DRAFT_Vendor_35",
            "dr_number": "DR-001-TEST",
            "po_number": "",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "notes": "Draft PO test",
            "po_type": "draft",
            "items": make_items(qty=1, unit_price=10),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 10,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200, f"Draft creation failed: {resp.text}"
        po = resp.json()
        yield po
        # Cleanup
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)

    def test_draft_po_has_status_draft(self, draft_po):
        assert draft_po["status"] == "draft", f"Expected draft, got {draft_po['status']}"

    def test_draft_po_has_po_type_draft(self, draft_po):
        assert draft_po.get("po_type") == "draft", f"Expected po_type=draft, got {draft_po.get('po_type')}"

    def test_draft_po_payment_status_unpaid(self, draft_po):
        assert draft_po["payment_status"] == "unpaid"

    def test_draft_po_amount_paid_zero(self, draft_po):
        assert draft_po["amount_paid"] == 0

    def test_draft_po_dr_number_stored(self, draft_po):
        assert draft_po.get("dr_number") == "DR-001-TEST", f"DR# not stored: {draft_po.get('dr_number')}"

    def test_draft_po_grand_total_correct(self, draft_po):
        assert draft_po.get("grand_total") == 10.0 or draft_po.get("subtotal") == 10.0

    def test_draft_po_appears_in_list(self, headers, draft_po):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"limit": 200})
        ids = [p["id"] for p in resp.json()["purchase_orders"]]
        assert draft_po["id"] in ids, "Draft PO not found in list"

    def test_draft_po_in_draft_filter(self, headers, draft_po):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"status": "draft", "limit": 200})
        ids = [p["id"] for p in resp.json()["purchase_orders"]]
        assert draft_po["id"] in ids, "Draft PO not in draft filter"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: POST /purchase-orders with po_type=terms
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateTermsPO:
    """Test po_type=terms: receive immediately + AP created, no fund deduct"""

    @pytest.fixture(scope="class")
    def terms_po(self, headers):
        payload = {
            "vendor": "TEST_TERMS_Vendor_35",
            "dr_number": "DR-TERMS-TEST",
            "po_number": "",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "notes": "Terms PO test",
            "po_type": "terms",
            "terms_days": 30,
            "terms_label": "Net 30",
            "due_date": "2026-03-22",
            "items": make_items(qty=1, unit_price=50),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 50,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200, f"Terms PO creation failed: {resp.text}"
        po = resp.json()
        yield po
        # Cleanup
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)

    def test_terms_po_status_is_received(self, terms_po):
        assert terms_po["status"] == "received", f"Expected received, got {terms_po['status']}"

    def test_terms_po_type_is_terms(self, terms_po):
        assert terms_po.get("po_type") == "terms"

    def test_terms_po_payment_status_unpaid(self, terms_po):
        assert terms_po["payment_status"] == "unpaid"

    def test_terms_po_balance_equals_grand_total(self, terms_po):
        gt = terms_po.get("grand_total", terms_po.get("subtotal", 0))
        assert terms_po["balance"] == gt, f"Balance {terms_po['balance']} != grand_total {gt}"

    def test_terms_po_terms_days_stored(self, terms_po):
        assert terms_po.get("terms_days") == 30

    def test_terms_po_terms_label_stored(self, terms_po):
        assert terms_po.get("terms_label") == "Net 30"

    def test_terms_po_dr_number_stored(self, terms_po):
        assert terms_po.get("dr_number") == "DR-TERMS-TEST"

    def test_terms_po_ap_created(self, headers, terms_po):
        """Verify that an AP record was created in payables"""
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        all_ids = [p["id"] for group in [data["overdue"], data["due_soon"], data["later"]] for p in group]
        # The terms PO should appear in unpaid summary
        assert terms_po["id"] in all_ids, f"Terms PO {terms_po['id']} not in unpaid summary"

    def test_terms_po_appears_in_received_filter(self, headers, terms_po):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"status": "received", "limit": 200})
        ids = [p["id"] for p in resp.json()["purchase_orders"]]
        assert terms_po["id"] in ids, "Terms PO not in received filter"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: POST /purchase-orders with po_type=cash
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateCashPO:
    """Test po_type=cash: receive immediately + expense + deduct fund. Use safe (55000 balance)."""

    @pytest.fixture(scope="class")
    def cash_po(self, headers):
        # Use safe fund (55000 balance) to avoid insufficient funds issue
        # Use very small amount (1 peso) to minimize impact
        payload = {
            "vendor": "TEST_CASH_Vendor_35",
            "dr_number": "DR-CASH-TEST",
            "po_number": "",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "notes": "Cash PO test",
            "po_type": "cash",
            "fund_source": "safe",
            "payment_method_detail": "Cash",
            "items": make_items(qty=1, unit_price=1),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 1,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200, f"Cash PO creation failed: {resp.text}"
        po = resp.json()
        yield po
        # Cleanup (cancel)
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)

    def test_cash_po_status_is_received(self, cash_po):
        assert cash_po["status"] == "received", f"Expected received, got {cash_po['status']}"

    def test_cash_po_type_is_cash(self, cash_po):
        assert cash_po.get("po_type") == "cash"

    def test_cash_po_payment_status_paid(self, cash_po):
        assert cash_po["payment_status"] == "paid"

    def test_cash_po_balance_is_zero(self, cash_po):
        assert cash_po["balance"] == 0.0

    def test_cash_po_amount_paid_equals_grand_total(self, cash_po):
        gt = cash_po.get("grand_total", cash_po.get("subtotal", 0))
        assert cash_po["amount_paid"] == gt

    def test_cash_po_dr_number_stored(self, cash_po):
        assert cash_po.get("dr_number") == "DR-CASH-TEST"

    def test_cash_po_has_po_number(self, cash_po):
        assert cash_po["po_number"], "po_number should be auto-generated"

    def test_cash_po_appears_in_received_filter(self, headers, cash_po):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                            params={"status": "received", "limit": 200})
        ids = [p["id"] for p in resp.json()["purchase_orders"]]
        assert cash_po["id"] in ids


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Per-line discount and overall discount
# ═══════════════════════════════════════════════════════════════════════════════

class TestPODiscounts:
    """Test per-line discount (₱ and %) and overall discount"""

    def test_line_discount_amount_type(self, headers):
        """₱10 discount on 2 × ₱100 = ₱190 subtotal"""
        payload = {
            "vendor": "TEST_DISC_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100, disc_type="amount", disc_val=10),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 190,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        # Clean up
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        # Verify: item total = 2*100 - 10 = 190
        assert po["items"][0]["total"] == 190.0, f"Expected 190, got {po['items'][0]['total']}"
        assert po["items"][0]["discount_amount"] == 10.0

    def test_line_discount_percent_type(self, headers):
        """10% discount on 2 × ₱100 = ₱180 subtotal"""
        payload = {
            "vendor": "TEST_DISC2_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100, disc_type="percent", disc_val=10),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 180,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        # 10% of 200 = 20 discount; total = 180
        assert po["items"][0]["total"] == 180.0, f"Expected 180, got {po['items'][0]['total']}"
        assert po["items"][0]["discount_amount"] == 20.0

    def test_overall_discount_amount(self, headers):
        """Overall ₱50 discount on ₱200 subtotal = ₱150 grand_total"""
        payload = {
            "vendor": "TEST_ODISC_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100),
            "overall_discount_type": "amount",
            "overall_discount_value": 50,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 150,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("overall_discount_amount") == 50.0
        assert po.get("grand_total") == 150.0

    def test_overall_discount_percent(self, headers):
        """Overall 10% discount on ₱200 subtotal = ₱180 grand_total"""
        payload = {
            "vendor": "TEST_ODISC2_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100),
            "overall_discount_type": "percent",
            "overall_discount_value": 10,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 180,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("overall_discount_amount") == 20.0
        assert po.get("grand_total") == 180.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: Freight and VAT
# ═══════════════════════════════════════════════════════════════════════════════

class TestPOFreightAndVAT:
    """Test freight and VAT calculation"""

    def test_po_with_freight(self, headers):
        """₱200 subtotal + ₱50 freight = ₱250 grand_total"""
        payload = {
            "vendor": "TEST_FREIGHT_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 50,
            "tax_rate": 0,
            "grand_total": 250,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("freight") == 50.0
        assert po.get("grand_total") == 250.0

    def test_po_with_vat(self, headers):
        """₱200 subtotal + 12% VAT = ₱224 grand_total"""
        payload = {
            "vendor": "TEST_VAT_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 12,
            "grand_total": 224,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("tax_rate") == 12.0
        assert po.get("tax_amount") == 24.0
        assert po.get("grand_total") == 224.0

    def test_po_with_freight_and_vat(self, headers):
        """₱200 subtotal + ₱50 freight + 12% VAT on ₱250 = ₱280 grand_total"""
        payload = {
            "vendor": "TEST_FV_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=2, unit_price=100),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 50,
            "tax_rate": 12,
            "grand_total": 280,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("freight") == 50.0
        assert po.get("tax_rate") == 12.0
        # pre_tax = 200+50=250; tax=30; grand=280
        assert po.get("grand_total") == 280.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: Insufficient funds handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsufficientFunds:
    """Test insufficient funds error returns proper error structure"""

    def test_cash_po_insufficient_cashier_returns_400(self, headers):
        """Requesting amount > cashier balance returns 400 with insufficient_funds type"""
        payload = {
            "vendor": "TEST_INSUF_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "cash",
            "fund_source": "cashier",
            "payment_method_detail": "Cash",
            "items": make_items(qty=1, unit_price=999999),  # Very large amount
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 999999,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for insufficient funds, got {resp.status_code}"
        detail = resp.json().get("detail", {})
        # Error should have type=insufficient_funds
        if isinstance(detail, dict):
            assert detail.get("type") == "insufficient_funds"
            assert "cashier_balance" in detail
            assert "safe_balance" in detail

    def test_cash_po_insufficient_safe_returns_400(self, headers):
        """Requesting amount > safe balance returns 400"""
        payload = {
            "vendor": "TEST_INSUF2_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "cash",
            "fund_source": "safe",
            "payment_method_detail": "Cash",
            "items": make_items(qty=1, unit_price=9999999),  # Way more than safe balance
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 9999999,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: Backward compatibility (legacy payment_method field)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Test legacy payment_method=cash/credit still works"""

    def test_legacy_credit_payment_method(self, headers):
        """Legacy payment_method=credit should still create terms-type PO"""
        payload = {
            "vendor": "TEST_LEGACY_Vendor_35",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "payment_method": "credit",
            "terms_days": 7,
            "items": make_items(qty=1, unit_price=5),
            "grand_total": 5,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        # Should be treated as terms
        assert po["payment_status"] == "unpaid"
        assert po["balance"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: DR# field
# ═══════════════════════════════════════════════════════════════════════════════

class TestDRNumberField:
    """Test DR# is properly stored and returned"""

    def test_dr_number_stored_on_draft(self, headers):
        payload = {
            "vendor": "TEST_DR_Vendor_35",
            "dr_number": "DR-123456",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=1, unit_price=5),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 5,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po['id']}", headers=headers)
        assert po.get("dr_number") == "DR-123456", f"DR# not stored: {po.get('dr_number')}"

    def test_dr_number_in_list_response(self, headers):
        """DR# should appear in list response"""
        payload = {
            "vendor": "TEST_DR2_Vendor_35",
            "dr_number": "DR-654321",
            "branch_id": MAIN_BRANCH_ID,
            "purchase_date": "2026-02-20",
            "po_type": "draft",
            "items": make_items(qty=1, unit_price=5),
            "overall_discount_type": "amount",
            "overall_discount_value": 0,
            "freight": 0,
            "tax_rate": 0,
            "grand_total": 5,
        }
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json=payload, headers=headers)
        assert resp.status_code == 200
        po = resp.json()
        po_id = po["id"]

        list_resp = requests.get(f"{BASE_URL}/api/purchase-orders", headers=headers,
                                 params={"limit": 200})
        orders = list_resp.json()["purchase_orders"]
        found = next((o for o in orders if o["id"] == po_id), None)
        requests.delete(f"{BASE_URL}/api/purchase-orders/{po_id}", headers=headers)
        assert found is not None, "PO not found in list"
        assert found.get("dr_number") == "DR-654321"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: by-vendor endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestByVendor:
    """Test GET /purchase-orders/by-vendor endpoint"""

    def test_by_vendor_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/by-vendor",
                            headers=headers,
                            params={"vendor": "SUPPLIER 1"})
        assert resp.status_code == 200

    def test_by_vendor_returns_list(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/by-vendor",
                            headers=headers,
                            params={"vendor": "SUPPLIER 1"})
        data = resp.json()
        assert isinstance(data, list)

    def test_by_vendor_all_pos_match_vendor(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/by-vendor",
                            headers=headers,
                            params={"vendor": "SUPPLIER 1"})
        for po in resp.json():
            assert po["vendor"] == "SUPPLIER 1"

    def test_by_vendor_nonexistent_returns_empty_list(self, headers):
        resp = requests.get(f"{BASE_URL}/api/purchase-orders/by-vendor",
                            headers=headers,
                            params={"vendor": "NONEXISTENT_VENDOR_XYZ"})
        assert resp.status_code == 200
        assert resp.json() == []
