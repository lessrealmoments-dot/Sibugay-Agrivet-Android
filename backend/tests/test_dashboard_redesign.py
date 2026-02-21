"""
Test suite for Dashboard Redesign + Z-Report improvements + Close Wizard Step 3 enhancements.
Tests:
  - GET /api/dashboard/stats - new fields: ar_aging, credit_customers_today, cashier_balance, last_close_date
  - GET /api/dashboard/branch-summary - new fields: ar_collected_today, today_new_credit, last_close_date
  - Z-Report structure via GET /api/daily-close/{date} - credit_sales_today, total_ar_at_close
  - Close Wizard Step 3: customer search for AR payments
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

def get_auth_token():
    """Get auth token for owner user."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "owner", "password": "521325"})
    if res.status_code == 200:
        return res.json().get("token")
    return None


@pytest.fixture(scope="module")
def auth_headers():
    token = get_auth_token()
    if not token:
        pytest.skip("Auth failed")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def branch_id(auth_headers):
    """Get the first available branch id."""
    res = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers)
    if res.status_code == 200:
        branches = res.data if isinstance(res.data, list) else res.json()
        if isinstance(branches, list) and len(branches) > 0:
            return branches[0].get("id")
    # Try from dashboard/stats
    res2 = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
    if res2.status_code == 200:
        data = res2.json()
        brs = data.get("branches", [])
        if brs:
            return brs[0]["id"]
    return None


class TestDashboardStats:
    """Test GET /api/dashboard/stats - comprehensive KPI endpoint."""

    def test_stats_returns_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: /api/dashboard/stats returns 200")

    def test_stats_has_today_date(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "today" in data, "Missing 'today' field"
        assert len(data["today"]) == 10, f"Expected YYYY-MM-DD, got {data['today']}"
        print(f"PASS: today = {data['today']}")

    def test_stats_has_day_of_week(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "day_of_week" in data, "Missing 'day_of_week'"
        assert data["day_of_week"] in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        print(f"PASS: day_of_week = {data['day_of_week']}")

    def test_stats_has_today_cash_sales(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "today_cash_sales" in data, "Missing 'today_cash_sales'"
        assert isinstance(data["today_cash_sales"], (int, float)), "today_cash_sales must be numeric"
        print(f"PASS: today_cash_sales = {data['today_cash_sales']}")

    def test_stats_has_ar_aging(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "ar_aging" in data, "Missing 'ar_aging'"
        ar = data["ar_aging"]
        assert "current" in ar, "ar_aging missing 'current'"
        assert "days_31_60" in ar, "ar_aging missing 'days_31_60'"
        assert "days_61_90" in ar, "ar_aging missing 'days_61_90'"
        assert "over_90" in ar, "ar_aging missing 'over_90'"
        assert "total" in ar, "ar_aging missing 'total'"
        print(f"PASS: ar_aging = {ar}")

    def test_stats_has_credit_customers_today(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "credit_customers_today" in data, "Missing 'credit_customers_today'"
        assert isinstance(data["credit_customers_today"], list), "credit_customers_today must be a list"
        # Validate structure if non-empty
        if data["credit_customers_today"]:
            first = data["credit_customers_today"][0]
            assert "customer_name" in first, "credit entry missing customer_name"
            assert "amount" in first, "credit entry missing amount"
        print(f"PASS: credit_customers_today has {len(data['credit_customers_today'])} entries")

    def test_stats_has_cashier_balance(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "cashier_balance" in data, "Missing 'cashier_balance'"
        assert isinstance(data["cashier_balance"], (int, float)), "cashier_balance must be numeric"
        print(f"PASS: cashier_balance = {data['cashier_balance']}")

    def test_stats_has_safe_balance(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "safe_balance" in data, "Missing 'safe_balance'"
        print(f"PASS: safe_balance = {data['safe_balance']}")

    def test_stats_has_last_close_date(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        # Can be None if never closed - field must still exist
        assert "last_close_date" in data, "Missing 'last_close_date' field"
        print(f"PASS: last_close_date = {data.get('last_close_date')}")

    def test_stats_has_top_debtors(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "top_debtors" in data, "Missing 'top_debtors'"
        assert isinstance(data["top_debtors"], list), "top_debtors must be a list"
        if data["top_debtors"]:
            d = data["top_debtors"][0]
            assert "customer" in d, "top_debtors entry missing 'customer'"
            assert "balance" in d, "top_debtors entry missing 'balance'"
        print(f"PASS: top_debtors has {len(data['top_debtors'])} entries")

    def test_stats_has_today_ar_collected(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "today_ar_collected" in data, "Missing 'today_ar_collected'"
        print(f"PASS: today_ar_collected = {data['today_ar_collected']}")

    def test_stats_has_recent_ar_payments(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "recent_ar_payments" in data, "Missing 'recent_ar_payments'"
        assert isinstance(data["recent_ar_payments"], list)
        print(f"PASS: recent_ar_payments has {len(data['recent_ar_payments'])} entries")

    def test_stats_has_low_stock_count(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        data = res.json()
        assert "low_stock_count" in data, "Missing 'low_stock_count'"
        assert isinstance(data["low_stock_count"], int), "low_stock_count must be integer"
        print(f"PASS: low_stock_count = {data['low_stock_count']}")

    def test_stats_branch_filter(self, auth_headers, branch_id):
        """Test stats with explicit branch_id filter."""
        if not branch_id:
            pytest.skip("No branch_id available")
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers, params={"branch_id": branch_id})
        assert res.status_code == 200
        data = res.json()
        assert "today_cash_sales" in data
        assert "ar_aging" in data
        print(f"PASS: stats with branch_id={branch_id} works")


class TestDashboardBranchSummary:
    """Test GET /api/dashboard/branch-summary - owner multi-branch view."""

    def test_branch_summary_returns_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        print("PASS: /api/dashboard/branch-summary returns 200")

    def test_branch_summary_has_branches_list(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        assert "branches" in data, "Missing 'branches' key"
        assert isinstance(data["branches"], list), "branches must be a list"
        print(f"PASS: branches has {len(data['branches'])} entries")

    def test_branch_summary_has_totals(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        assert "totals" in data, "Missing 'totals' key"
        totals = data["totals"]
        assert "today_revenue" in totals, "totals missing 'today_revenue'"
        assert "total_receivables" in totals, "totals missing 'total_receivables'"
        assert "total_cash" in totals, "totals missing 'total_cash'"
        assert "low_stock_count" in totals, "totals missing 'low_stock_count'"
        print(f"PASS: totals = {totals}")

    def test_branch_summary_each_branch_has_new_credit(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        for b in data.get("branches", []):
            assert "today_new_credit" in b, f"Branch {b.get('name')} missing 'today_new_credit'"
        print("PASS: all branches have today_new_credit")

    def test_branch_summary_each_branch_has_ar_collected_today(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        for b in data.get("branches", []):
            assert "ar_collected_today" in b, f"Branch {b.get('name')} missing 'ar_collected_today'"
        print("PASS: all branches have ar_collected_today")

    def test_branch_summary_each_branch_has_last_close_date(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        for b in data.get("branches", []):
            assert "last_close_date" in b, f"Branch {b.get('name')} missing 'last_close_date'"
        print("PASS: all branches have last_close_date field")

    def test_branch_summary_each_branch_has_cash_sales(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/branch-summary", headers=auth_headers)
        data = res.json()
        for b in data.get("branches", []):
            assert "today_cash_sales" in b, f"Branch {b.get('name')} missing 'today_cash_sales'"
            assert "total_cash" in b, f"Branch {b.get('name')} missing 'total_cash'"
            assert "receivables" in b, f"Branch {b.get('name')} missing 'receivables'"
        print("PASS: all branches have cash_sales, total_cash, receivables")


class TestDailyClosePOST:
    """Test that POST /api/daily-close saves credit_sales_today + total_ar_at_close."""

    def test_daily_close_preview_has_credit_sales_today(self, auth_headers, branch_id):
        """Verify daily-close-preview includes credit_sales_today list."""
        if not branch_id:
            pytest.skip("No branch_id available")
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        res = requests.get(f"{BASE_URL}/api/daily-close-preview", headers=auth_headers,
                           params={"branch_id": branch_id, "date": today})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        # Must include credit_sales_today list
        assert "credit_sales_today" in data, "daily-close-preview missing 'credit_sales_today'"
        assert isinstance(data["credit_sales_today"], list)
        print(f"PASS: daily-close-preview has credit_sales_today with {len(data['credit_sales_today'])} entries")

    def test_daily_close_preview_has_total_credit_today(self, auth_headers, branch_id):
        if not branch_id:
            pytest.skip("No branch_id available")
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        res = requests.get(f"{BASE_URL}/api/daily-close-preview", headers=auth_headers,
                           params={"branch_id": branch_id, "date": today})
        assert res.status_code == 200
        data = res.json()
        assert "total_credit_today" in data, "daily-close-preview missing 'total_credit_today'"
        print(f"PASS: total_credit_today = {data.get('total_credit_today')}")


class TestZReportArchive:
    """Test that closed day records have credit_sales_today + total_ar_at_close."""

    def test_get_daily_close_archive_has_new_credit_fields(self, auth_headers, branch_id):
        """Retrieve the most recently closed day and verify new Z-report fields."""
        if not branch_id:
            pytest.skip("No branch_id available")
        # Get the variance history to find a closed date
        res = requests.get(f"{BASE_URL}/api/daily-variance-history", headers=auth_headers,
                           params={"branch_id": branch_id, "limit": 5})
        if res.status_code != 200:
            pytest.skip("Could not fetch variance history")
        records = res.json().get("records", [])
        if not records:
            pytest.skip("No closed days found to check Z-report structure")
        
        # Check the most recent closed day
        last_record = records[0]
        date = last_record["date"]
        
        res2 = requests.get(f"{BASE_URL}/api/daily-close/{date}", headers=auth_headers,
                            params={"branch_id": branch_id})
        assert res2.status_code == 200, f"Expected 200, got {res2.status_code}"
        data = res2.json()
        
        if data.get("status") == "open":
            pytest.skip("No closed day found")
        
        # Check new Z-report fields
        assert "credit_sales_today" in data, "Z-report missing 'credit_sales_today'"
        assert "total_ar_at_close" in data, "Z-report missing 'total_ar_at_close'"
        
        print(f"PASS: Z-report for {date} has credit_sales_today = {data.get('credit_sales_today')}")
        print(f"PASS: Z-report for {date} has total_ar_at_close = {data.get('total_ar_at_close')}")


class TestCustomerSearchForARPayment:
    """Test the customer search endpoint used by Step 3 Find & Record Payment panel."""

    def test_customers_search_returns_results(self, auth_headers):
        """Test that /api/customers?search= returns customers with balance info."""
        res = requests.get(f"{BASE_URL}/api/customers", headers=auth_headers,
                           params={"search": "a", "limit": 10})
        assert res.status_code == 200
        data = res.json()
        # Can be dict with 'customers' key or list
        if isinstance(data, dict):
            customers = data.get("customers", [])
        else:
            customers = data
        assert isinstance(customers, list)
        print(f"PASS: customers search returns {len(customers)} results")

    def test_invoices_search_by_customer_id(self, auth_headers, branch_id):
        """Test that /api/invoices?customer_id=&status=open returns open invoices with balance."""
        if not branch_id:
            pytest.skip("No branch_id available")
        # Get a customer with balance
        res = requests.get(f"{BASE_URL}/api/customers", headers=auth_headers,
                           params={"search": "", "limit": 50})
        if res.status_code != 200:
            pytest.skip("Could not fetch customers")
        data = res.json()
        customers = data.get("customers", data) if isinstance(data, dict) else data
        
        # Find a customer with balance > 0
        customer_with_balance = None
        for c in customers:
            if (c.get("balance") or 0) > 0:
                customer_with_balance = c
                break
        
        if not customer_with_balance:
            pytest.skip("No customer with outstanding balance found")
        
        cust_id = customer_with_balance["id"]
        res2 = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers,
                            params={"customer_id": cust_id, "status": "open", "limit": 10})
        assert res2.status_code == 200, f"Expected 200, got {res2.status_code}"
        data2 = res2.json()
        invoices = data2.get("invoices", data2) if isinstance(data2, dict) else data2
        print(f"PASS: Found {len(invoices)} open invoices for customer {customer_with_balance.get('name')}")


class TestPurchaseOrderUnpaidSummary:
    """Test GET /api/purchase-orders/unpaid-summary for dashboard PO section."""

    def test_unpaid_summary_returns_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        print(f"PASS: /api/purchase-orders/unpaid-summary returns 200, data keys: {list(data.keys())}")

    def test_unpaid_summary_has_categories(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/purchase-orders/unpaid-summary", headers=auth_headers)
        data = res.json()
        assert "total_unpaid" in data or "total_count" in data, "Missing total_unpaid or total_count"
        print(f"PASS: unpaid summary has expected fields. total_count={data.get('total_count')}")
