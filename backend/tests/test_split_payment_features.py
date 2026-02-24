"""
Tests for AgriBooks 4 new features:
1. Split payment (Cash + GCash in single transaction)
2. Digital payment in Close Wizard Z-report
3. Digital wallet audit section in Audit Center
4. Backend: split payment routes to both cashier and digital wallet

Tests POST /api/unified-sale with payment_type=split
Tests GET /api/daily-close-preview for digital fields
Tests GET /api/audit/compute for digital section
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ──────────────── Auth fixtures ────────────────

@pytest.fixture(scope="module")
def owner_token():
    """Get owner auth token."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "owner", "password": "521325"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}


# ──────────────── Helper: get a product for testing ────────────────

@pytest.fixture(scope="module")
def test_product(auth_headers):
    """Get a valid product from IPIL branch with stock and selling price above cost."""
    # Fetch products from inventory for IPIL branch
    res = requests.get(
        f"{BASE_URL}/api/inventory",
        params={"branch_id": IPIL_BRANCH_ID, "limit": 20},
        headers=auth_headers,
    )
    assert res.status_code == 200, f"Inventory fetch failed: {res.text}"
    inv_items = res.json().get("items", [])

    for item in inv_items:
        if item.get("is_repack"):
            continue
        cost = float(item.get("cost_price", 0))
        # Try retail price from prices dict
        prices = item.get("prices", {})
        retail = float(prices.get("retail") or prices.get("Retail") or 0)
        branch_stock_map = item.get("branch_stock", {})
        branch_qty = float(branch_stock_map.get(IPIL_BRANCH_ID, item.get("total_stock", 0)) or 0)

        if retail > cost and branch_qty >= 2:
            return {
                "product_id": item["id"],
                "product_name": item["name"],
                "price": retail,
            }

    pytest.skip("No suitable test product found with stock > 2 and retail > cost in IPIL branch")


# ──────────────── Tests: unified-sale split payment ────────────────

class TestUnifiedSaleSplitPayment:
    """Test POST /api/unified-sale with payment_type=split routes correctly."""

    def test_split_payment_api_call_succeeds(self, auth_headers, test_product):
        """POST /api/unified-sale with payment_type=split should return 200."""
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.5, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_SPLIT_REF_001",
            "digital_sender": "Test Sender",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Split sale failed: {res.status_code} - {res.text}"
        print(f"PASS: Split payment returned 200")
        return res.json()

    def test_split_payment_invoice_has_fund_source_split(self, auth_headers, test_product):
        """Invoice created via split payment must have fund_source='split'."""
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.4, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_SPLIT_FUND_002",
            "digital_sender": "",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Split sale failed: {res.text}"

        invoice = res.json()
        fund_source = invoice.get("fund_source")
        assert fund_source == "split", f"Expected fund_source='split', got '{fund_source}'"
        print(f"PASS: fund_source = {fund_source}")

    def test_split_payment_invoice_has_cash_and_digital_amounts(self, auth_headers, test_product):
        """Invoice must store cash_amount and digital_amount fields."""
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.3, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "Maya",
            "digital_ref_number": "TEST_SPLIT_AMOUNTS_003",
            "digital_sender": "Tester",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Split sale failed: {res.text}"

        invoice = res.json()
        stored_cash = invoice.get("cash_amount")
        stored_digital = invoice.get("digital_amount")
        assert stored_cash == cash_amt, f"Expected cash_amount={cash_amt}, got {stored_cash}"
        assert stored_digital == digital_amt, f"Expected digital_amount={digital_amt}, got {stored_digital}"
        print(f"PASS: cash_amount={stored_cash}, digital_amount={stored_digital}")

    def test_split_payment_invoice_has_digital_platform_and_ref(self, auth_headers, test_product):
        """Invoice must store digital_platform and digital_ref_number for split payment."""
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.6, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_GC_REF_2026_004",
            "digital_sender": "Juan Dela Cruz",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Split sale failed: {res.text}"

        invoice = res.json()
        dp = invoice.get("digital_platform")
        dr = invoice.get("digital_ref_number")
        assert dp == "GCash", f"Expected digital_platform='GCash', got '{dp}'"
        assert dr == "TEST_GC_REF_2026_004", f"Expected ref 'TEST_GC_REF_2026_004', got '{dr}'"
        print(f"PASS: digital_platform={dp}, digital_ref_number={dr}")

    def test_split_payment_two_payment_entries(self, auth_headers, test_product):
        """Invoice payments array must have 2 entries for split: one cash, one digital."""
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.5, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_TWO_PAYMENTS_005",
            "digital_sender": "",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Split sale failed: {res.text}"

        invoice = res.json()
        payments = invoice.get("payments", [])
        assert len(payments) == 2, f"Expected 2 payment entries for split, got {len(payments)}: {payments}"

        fund_sources = [p.get("fund_source") for p in payments]
        assert "cashier" in fund_sources, f"No cashier entry in payments: {payments}"
        assert "digital" in fund_sources, f"No digital entry in payments: {payments}"
        print(f"PASS: 2 payment entries found, fund_sources={fund_sources}")


# ──────────────── Tests: digital payment via unified-sale ────────────────

class TestUnifiedSaleDigitalPayment:
    """Test POST /api/unified-sale with payment_type=digital."""

    def test_digital_payment_succeeds(self, auth_headers, test_product):
        """Digital payment should succeed and return 200."""
        grand_total = test_product["price"] * 1

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "digital",
            "payment_method": "GCash",
            "fund_source": "digital",
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_DIGITAL_006",
            "digital_sender": "Digital Tester",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Digital sale failed: {res.status_code} - {res.text}"
        invoice = res.json()
        print(f"PASS: Digital payment returned 200, invoice={invoice.get('invoice_number')}")

    def test_digital_payment_fund_source_digital(self, auth_headers, test_product):
        """Digital payment invoice must have fund_source='digital'."""
        grand_total = test_product["price"] * 1

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "digital",
            "payment_method": "Maya",
            "fund_source": "digital",
            "digital_platform": "Maya",
            "digital_ref_number": "TEST_MAYA_FUND_007",
            "digital_sender": "",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Digital sale failed: {res.text}"
        invoice = res.json()
        fs = invoice.get("fund_source")
        assert fs == "digital", f"Expected fund_source='digital', got '{fs}'"
        print(f"PASS: fund_source = {fs}")


# ──────────────── Tests: daily-close-preview digital section ────────────────

class TestDailyClosePreviewDigital:
    """Test GET /api/daily-close-preview returns digital fields."""

    def test_close_preview_returns_total_digital_today(self, auth_headers):
        """GET /api/daily-close-preview must return total_digital_today field."""
        res = requests.get(
            f"{BASE_URL}/api/daily-close-preview",
            params={"branch_id": IPIL_BRANCH_ID, "date": TODAY},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Close preview failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "total_digital_today" in data, f"Missing total_digital_today in response: {list(data.keys())}"
        print(f"PASS: total_digital_today = {data['total_digital_today']}")

    def test_close_preview_returns_digital_by_platform(self, auth_headers):
        """GET /api/daily-close-preview must return digital_by_platform field."""
        res = requests.get(
            f"{BASE_URL}/api/daily-close-preview",
            params={"branch_id": IPIL_BRANCH_ID, "date": TODAY},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Close preview failed: {res.text}"
        data = res.json()
        assert "digital_by_platform" in data, f"Missing digital_by_platform in response: {list(data.keys())}"
        print(f"PASS: digital_by_platform = {data['digital_by_platform']}")

    def test_close_preview_digital_includes_split_payments(self, auth_headers, test_product):
        """
        Split payment invoices (fund_source='split') must be included in total_digital_today.
        This tests that the close preview queries fund_source in ['digital','split'].
        """
        # First create a split invoice
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.5, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_SPLIT_PREVIEW_008",
            "digital_sender": "",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        # Get pre-sale digital total
        pre_res = requests.get(
            f"{BASE_URL}/api/daily-close-preview",
            params={"branch_id": IPIL_BRANCH_ID, "date": TODAY},
            headers=auth_headers,
        )
        pre_total = pre_res.json().get("total_digital_today", 0) if pre_res.status_code == 200 else 0

        # Create split invoice
        sale_res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        if sale_res.status_code != 200:
            pytest.skip(f"Skipping: could not create split invoice for this test - {sale_res.text}")

        # Get post-sale digital total
        post_res = requests.get(
            f"{BASE_URL}/api/daily-close-preview",
            params={"branch_id": IPIL_BRANCH_ID, "date": TODAY},
            headers=auth_headers,
        )
        assert post_res.status_code == 200, f"Close preview failed after split invoice: {post_res.text}"
        post_data = post_res.json()
        post_total = post_data.get("total_digital_today", 0)

        # The digital portion of split invoice should be reflected
        assert post_total >= pre_total + digital_amt, (
            f"Split invoice digital_amt={digital_amt} not reflected in close preview. "
            f"pre_total={pre_total}, post_total={post_total}"
        )
        print(f"PASS: Close preview total_digital_today increased by {post_total - pre_total} (expected {digital_amt})")


# ──────────────── Tests: audit/compute digital section ────────────────

class TestAuditComputeDigitalSection:
    """Test GET /api/audit/compute returns digital section."""

    def test_audit_compute_returns_200(self, auth_headers):
        """GET /api/audit/compute with branch_id must return 200."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Audit compute failed: {res.status_code} - {res.text}"
        print(f"PASS: audit/compute returned 200")

    def test_audit_compute_has_digital_section(self, auth_headers):
        """GET /api/audit/compute must include result.digital section."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Audit compute failed: {res.text}"
        data = res.json()
        assert "digital" in data, f"Missing 'digital' section in audit result. Keys: {list(data.keys())}"
        print(f"PASS: 'digital' section present in audit result")

    def test_audit_compute_digital_has_total_digital_collected(self, auth_headers):
        """Digital section must have total_digital_collected field."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200
        digital = res.json().get("digital", {})
        assert "total_digital_collected" in digital, (
            f"Missing total_digital_collected in digital section: {list(digital.keys())}"
        )
        print(f"PASS: total_digital_collected = {digital['total_digital_collected']}")

    def test_audit_compute_digital_has_by_platform(self, auth_headers):
        """Digital section must have by_platform dict."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200
        digital = res.json().get("digital", {})
        assert "by_platform" in digital, f"Missing by_platform: {list(digital.keys())}"
        print(f"PASS: by_platform = {digital['by_platform']}")

    def test_audit_compute_digital_has_missing_ref_count(self, auth_headers):
        """Digital section must have missing_ref_count (critical severity flag)."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200
        digital = res.json().get("digital", {})
        assert "missing_ref_count" in digital, f"Missing missing_ref_count: {list(digital.keys())}"
        print(f"PASS: missing_ref_count = {digital['missing_ref_count']}")

    def test_audit_compute_digital_has_severity(self, auth_headers):
        """Digital section must have severity field."""
        res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert res.status_code == 200
        digital = res.json().get("digital", {})
        assert "severity" in digital, f"Missing severity: {list(digital.keys())}"
        sev = digital.get("severity")
        assert sev in ("ok", "warning", "critical"), f"Unexpected severity value: {sev}"
        print(f"PASS: severity = {sev}")

    def test_audit_compute_digital_includes_split_in_count(self, auth_headers, test_product):
        """
        Split invoices (fund_source='split') must be counted in digital section.
        Create a split invoice with ref, verify transaction_count increases.
        """
        # Get pre-state
        pre_res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        pre_count = pre_res.json().get("digital", {}).get("transaction_count", 0) if pre_res.status_code == 200 else 0

        # Create split invoice
        grand_total = test_product["price"] * 1
        cash_amt = round(grand_total * 0.5, 2)
        digital_amt = round(grand_total - cash_amt, 2)

        payload = {
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 1,
                "rate": test_product["price"],
                "price": test_product["price"],
                "total": test_product["price"],
                "discount_type": "amount",
                "discount_value": 0,
                "discount_amount": 0,
            }],
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": cash_amt,
            "digital_amount": digital_amt,
            "digital_platform": "GCash",
            "digital_ref_number": "TEST_AUDIT_DIGITAL_009",
            "digital_sender": "",
            "amount_paid": grand_total,
            "balance": 0,
            "grand_total": grand_total,
            "subtotal": grand_total,
            "order_date": TODAY,
            "invoice_date": TODAY,
        }

        sale_res = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=auth_headers)
        if sale_res.status_code != 200:
            pytest.skip(f"Cannot create split invoice for audit test: {sale_res.text}")

        # Get post-state
        post_res = requests.get(
            f"{BASE_URL}/api/audit/compute",
            params={"branch_id": IPIL_BRANCH_ID},
            headers=auth_headers,
        )
        assert post_res.status_code == 200
        post_digital = post_res.json().get("digital", {})
        post_count = post_digital.get("transaction_count", 0)

        assert post_count >= pre_count + 1, (
            f"transaction_count did not increase after split invoice. pre={pre_count}, post={post_count}"
        )
        print(f"PASS: transaction_count increased from {pre_count} to {post_count}")
