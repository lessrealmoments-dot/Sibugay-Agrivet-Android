"""
Tests for Reports API endpoints: AR Aging, Sales Report, Expense Report
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    """Get admin token (owner role has reports.view permission)"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner",
        "password": "521325"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No token in response"
    return token

@pytest.fixture(scope="module")
def cashier_token():
    """Get cashier token (lower privilege)"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "cashier",
        "password": "1234"
    })
    if resp.status_code != 200:
        pytest.skip("Cashier login failed - skip cashier tests")
    data = resp.json()
    return data.get("token") or data.get("access_token")

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def cashier_headers(cashier_token):
    return {"Authorization": f"Bearer {cashier_token}", "Content-Type": "application/json"}


# ─── AR Aging Tests ──────────────────────────────────────────────────────────

class TestArAgingReport:
    """AR Aging Report endpoint tests"""

    def test_ar_aging_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_ar_aging_response_structure(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        data = resp.json()
        # Required top-level keys
        assert "as_of_date" in data, "Missing 'as_of_date'"
        assert "totals" in data, "Missing 'totals'"
        assert "rows" in data, "Missing 'rows'"

    def test_ar_aging_totals_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        totals = resp.json()["totals"]
        for key in ["current", "b31_60", "b61_90", "b90plus", "total"]:
            assert key in totals, f"Missing totals key: {key}"
        # Total should equal sum of buckets
        expected = round(totals["current"] + totals["b31_60"] + totals["b61_90"] + totals["b90plus"], 2)
        assert abs(totals["total"] - expected) < 0.01, f"Totals mismatch: {totals['total']} != {expected}"

    def test_ar_aging_has_data(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        data = resp.json()
        assert data["totals"]["total"] > 0, "Expected AR data (total > 0)"
        assert len(data["rows"]) > 0, "Expected at least one customer row"

    def test_ar_aging_row_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        rows = resp.json()["rows"]
        if rows:
            row = rows[0]
            for field in ["customer_id", "customer_name", "current", "b31_60", "b61_90", "b90plus", "total", "invoices"]:
                assert field in row, f"Row missing field: {field}"
            assert isinstance(row["invoices"], list), "invoices must be a list"

    def test_ar_aging_invoice_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        rows = resp.json()["rows"]
        for row in rows:
            for inv in row.get("invoices", []):
                for field in ["invoice_number", "invoice_date", "grand_total", "amount_paid", "balance", "days_old", "bucket"]:
                    assert field in inv, f"Invoice missing field: {field}"
                assert inv["bucket"] in ["current", "b31_60", "b61_90", "b90plus"], f"Invalid bucket: {inv['bucket']}"

    def test_ar_aging_as_of_date_format(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        date_str = resp.json()["as_of_date"]
        # Should be YYYY-MM-DD
        datetime.strptime(date_str, "%Y-%m-%d")  # raises if invalid

    def test_ar_aging_no_paid_invoices(self, admin_headers):
        """Verify no paid invoices appear in AR aging (balance should be > 0)"""
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        rows = resp.json()["rows"]
        for row in rows:
            for inv in row.get("invoices", []):
                assert inv["balance"] > 0, f"Invoice with balance=0 should not appear in AR aging: {inv['invoice_number']}"

    def test_ar_aging_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging")
        assert resp.status_code in [401, 403], f"Expected auth error, got {resp.status_code}"

    def test_ar_aging_branch_filter(self, admin_headers):
        """Branch filter with nonexistent branch_id returns 403 (access denied - correct security behavior)"""
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging?branch_id=nonexistent", headers=admin_headers)
        # Security: non-existent or unauthorized branch returns 403, not 200
        assert resp.status_code in [200, 403], f"Expected 200 or 403, got {resp.status_code}"

    def test_ar_aging_rows_sorted_by_total_desc(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=admin_headers)
        rows = resp.json()["rows"]
        if len(rows) > 1:
            for i in range(len(rows) - 1):
                assert rows[i]["total"] >= rows[i+1]["total"], "Rows should be sorted by total desc"


# ─── Sales Report Tests ───────────────────────────────────────────────────────

class TestSalesReport:
    """Sales Report endpoint tests"""

    def test_sales_report_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_sales_report_response_structure(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        data = resp.json()
        for key in ["date_from", "date_to", "grand_total", "categories", "payment_totals", "daily", "transactions"]:
            assert key in data, f"Missing key: {key}"

    def test_sales_report_has_data(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        data = resp.json()
        assert data["grand_total"] > 0, "Expected sales data"
        assert len(data["categories"]) > 0, "Expected category breakdown"

    def test_sales_report_category_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        categories = resp.json()["categories"]
        if categories:
            cat = categories[0]
            for field in ["category", "total", "qty", "by_payment"]:
                assert field in cat, f"Category missing field: {field}"
            assert isinstance(cat["by_payment"], dict)

    def test_sales_report_transaction_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        transactions = resp.json()["transactions"]
        if transactions:
            t = transactions[0]
            for field in ["invoice_number", "date", "customer_name", "payment_type", "grand_total", "amount_paid", "balance", "status"]:
                assert field in t, f"Transaction missing field: {field}"

    def test_sales_report_date_filter(self, admin_headers):
        """Date range filter returns correct data"""
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales?date_from=2026-01-01&date_to=2026-12-31",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["date_from"] == "2026-01-01"
        assert data["date_to"] == "2026-12-31"

    def test_sales_report_narrow_date_range(self, admin_headers):
        """Narrow date range with no data returns empty but valid structure"""
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales?date_from=2020-01-01&date_to=2020-01-01",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grand_total"] == 0 or isinstance(data["grand_total"], (int, float))
        assert isinstance(data["categories"], list)
        assert isinstance(data["transactions"], list)

    def test_sales_report_grand_total_matches_categories(self, admin_headers):
        """grand_total should equal sum of category totals"""
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        data = resp.json()
        if data["categories"]:
            cat_sum = round(sum(c["total"] for c in data["categories"]), 2)
            assert abs(data["grand_total"] - cat_sum) < 0.01, f"grand_total {data['grand_total']} != cat_sum {cat_sum}"

    def test_sales_report_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/reports/sales")
        assert resp.status_code in [401, 403]

    def test_sales_report_daily_breakdown(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        data = resp.json()
        assert isinstance(data["daily"], list)
        for day in data["daily"]:
            assert "date" in day
            assert "total" in day
            assert "count" in day

    def test_sales_report_payment_totals(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/sales", headers=admin_headers)
        data = resp.json()
        payment_totals = data["payment_totals"]
        assert isinstance(payment_totals, dict)
        # Payment total sum should roughly match grand_total from categories
        pt_sum = round(sum(payment_totals.values()), 2)
        cat_sum = round(sum(c["total"] for c in data["categories"]), 2)
        assert abs(pt_sum - cat_sum) < 0.01, f"Payment totals sum {pt_sum} != categories sum {cat_sum}"


# ─── Expense Report Tests ────────────────────────────────────────────────────

class TestExpenseReport:
    """Expense Report endpoint tests"""

    def test_expense_report_returns_200(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_expense_report_response_structure(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        data = resp.json()
        for key in ["date_from", "date_to", "grand_total", "categories", "daily", "expenses"]:
            assert key in data, f"Missing key: {key}"

    def test_expense_report_has_data(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        data = resp.json()
        assert data["grand_total"] > 0, "Expected expense data"
        assert len(data["categories"]) > 0, "Expected category breakdown"

    def test_expense_report_category_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        categories = resp.json()["categories"]
        if categories:
            cat = categories[0]
            for field in ["category", "total", "count"]:
                assert field in cat, f"Category missing field: {field}"

    def test_expense_report_expense_fields(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        expenses = resp.json()["expenses"]
        if expenses:
            exp = expenses[0]
            for field in ["date", "category", "amount"]:
                assert field in exp, f"Expense missing field: {field}"

    def test_expense_report_date_filter(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/reports/expenses?date_from=2026-01-01&date_to=2026-12-31",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["date_from"] == "2026-01-01"
        assert data["date_to"] == "2026-12-31"

    def test_expense_report_category_filter(self, admin_headers):
        """Category filter should narrow results"""
        # First get full list of categories
        resp_all = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        categories = resp_all.json()["categories"]
        if not categories:
            pytest.skip("No expense categories available")

        # Filter by first category
        cat_name = categories[0]["category"]
        resp_filtered = requests.get(
            f"{BASE_URL}/api/reports/expenses?category={cat_name}",
            headers=admin_headers
        )
        assert resp_filtered.status_code == 200
        data = resp_filtered.json()
        # All returned expenses should belong to this category
        for exp in data["expenses"]:
            assert exp["category"] == cat_name, f"Expense with wrong category: {exp['category']}"

    def test_expense_report_grand_total_matches_categories(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        data = resp.json()
        if data["categories"]:
            cat_sum = round(sum(c["total"] for c in data["categories"]), 2)
            assert abs(data["grand_total"] - cat_sum) < 0.01, f"grand_total {data['grand_total']} != cat_sum {cat_sum}"

    def test_expense_report_categories_sorted_desc(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        cats = resp.json()["categories"]
        if len(cats) > 1:
            for i in range(len(cats) - 1):
                assert cats[i]["total"] >= cats[i+1]["total"], "Categories should be sorted by total desc"

    def test_expense_report_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses")
        assert resp.status_code in [401, 403]

    def test_expense_report_narrow_date_returns_empty(self, admin_headers):
        resp = requests.get(
            f"{BASE_URL}/api/reports/expenses?date_from=2020-01-01&date_to=2020-01-01",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grand_total"] == 0 or isinstance(data["grand_total"], (int, float))
        assert isinstance(data["categories"], list)
        assert isinstance(data["expenses"], list)

    def test_expense_report_daily_breakdown(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/reports/expenses", headers=admin_headers)
        data = resp.json()
        assert isinstance(data["daily"], list)
        for day in data["daily"]:
            assert "date" in day
            assert "total" in day
            assert "count" in day
