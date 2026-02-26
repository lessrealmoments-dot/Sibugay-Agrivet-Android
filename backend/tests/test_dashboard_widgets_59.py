"""
Test suite for Dashboard Widgets - Iteration 59
Tests the new dashboard endpoints:
- /api/dashboard/sales-analytics (GET with periods)
- /api/dashboard/accounts-payable (GET)
Also validates existing dashboard stats endpoint.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSalesAnalyticsEndpoint:
    """Tests for GET /api/dashboard/sales-analytics"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        self.token = login_res.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_01_sales_analytics_this_month(self):
        """Test sales analytics for this_month period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "this_month"},
            headers=self.headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "period" in data, "Response missing 'period' field"
        assert data["period"] == "this_month"
        assert "start_date" in data
        assert "end_date" in data
        assert "daily" in data, "Response missing 'daily' array"
        assert "branches" in data, "Response missing 'branches' array"
        assert "summary" in data, "Response missing 'summary' object"
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_revenue" in summary
        assert "total_transactions" in summary
        assert "avg_transaction" in summary
        assert "total_cash" in summary
        assert "total_digital" in summary
        assert "total_credit" in summary
        assert "days_with_sales" in summary
        
        print(f"PASS: sales-analytics this_month - {summary['total_revenue']} revenue, {summary['total_transactions']} txns")
    
    def test_02_sales_analytics_last_month(self):
        """Test sales analytics for last_month period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "last_month"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "last_month"
        print(f"PASS: sales-analytics last_month - {data['summary']['total_revenue']} revenue")
    
    def test_03_sales_analytics_this_quarter(self):
        """Test sales analytics for this_quarter period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "this_quarter"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "this_quarter"
        print(f"PASS: sales-analytics this_quarter - {data['summary']['total_revenue']} revenue")
    
    def test_04_sales_analytics_last_quarter(self):
        """Test sales analytics for last_quarter period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "last_quarter"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "last_quarter"
        print(f"PASS: sales-analytics last_quarter")
    
    def test_05_sales_analytics_this_year(self):
        """Test sales analytics for this_year period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "this_year"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "this_year"
        print(f"PASS: sales-analytics this_year - {data['summary']['total_revenue']} revenue")
    
    def test_06_sales_analytics_last_year(self):
        """Test sales analytics for last_year period"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "last_year"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "last_year"
        print(f"PASS: sales-analytics last_year")
    
    def test_07_sales_analytics_daily_data_structure(self):
        """Verify daily data structure has all required fields"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "this_month"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        if data["daily"]:
            daily_entry = data["daily"][0]
            assert "date" in daily_entry, "Daily entry missing 'date'"
            assert "revenue" in daily_entry, "Daily entry missing 'revenue'"
            assert "cash" in daily_entry, "Daily entry missing 'cash'"
            assert "digital" in daily_entry, "Daily entry missing 'digital'"
            assert "credit" in daily_entry, "Daily entry missing 'credit'"
            assert "count" in daily_entry, "Daily entry missing 'count'"
            print(f"PASS: Daily entry structure verified - {daily_entry}")
        else:
            print("PASS: Daily array empty (no sales data), structure test skipped")
    
    def test_08_sales_analytics_branch_breakdown_structure(self):
        """Verify branch breakdown has required fields"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/sales-analytics",
            params={"period": "this_month"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        if data["branches"]:
            branch = data["branches"][0]
            assert "branch_id" in branch, "Branch entry missing 'branch_id'"
            assert "name" in branch, "Branch entry missing 'name'"
            assert "revenue" in branch, "Branch entry missing 'revenue'"
            assert "count" in branch, "Branch entry missing 'count'"
            print(f"PASS: Branch breakdown structure - {len(data['branches'])} branches")
        else:
            print("PASS: Branches array empty, structure test skipped")


class TestAccountsPayableEndpoint:
    """Tests for GET /api/dashboard/accounts-payable"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert login_res.status_code == 200
        self.token = login_res.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_01_accounts_payable_endpoint_works(self):
        """Test accounts-payable endpoint returns 200"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/accounts-payable",
            headers=self.headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "total_payable" in data, "Missing 'total_payable'"
        assert "overdue_total" in data, "Missing 'overdue_total'"
        assert "overdue_count" in data, "Missing 'overdue_count'"
        assert "due_this_week_total" in data, "Missing 'due_this_week_total'"
        assert "due_this_week" in data, "Missing 'due_this_week' array"
        assert "overdue" in data, "Missing 'overdue' array"
        assert "upcoming_count" in data, "Missing 'upcoming_count'"
        assert "upcoming_total" in data, "Missing 'upcoming_total'"
        
        print(f"PASS: accounts-payable - Total: {data['total_payable']}, Overdue: {data['overdue_total']}, This week: {data['due_this_week_total']}")
    
    def test_02_accounts_payable_overdue_structure(self):
        """Verify overdue items have correct structure"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/accounts-payable",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        if data["overdue"]:
            overdue_item = data["overdue"][0]
            assert "po_id" in overdue_item, "Overdue missing 'po_id'"
            assert "po_number" in overdue_item, "Overdue missing 'po_number'"
            assert "vendor" in overdue_item, "Overdue missing 'vendor'"
            assert "balance" in overdue_item, "Overdue missing 'balance'"
            assert "due_date" in overdue_item, "Overdue missing 'due_date'"
            assert "days_left" in overdue_item, "Overdue missing 'days_left'"
            print(f"PASS: Overdue structure verified - {overdue_item['po_number']}")
        else:
            print("PASS: No overdue items (empty array)")
    
    def test_03_accounts_payable_due_this_week_structure(self):
        """Verify due_this_week items have correct structure"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/accounts-payable",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        if data["due_this_week"]:
            item = data["due_this_week"][0]
            assert "po_id" in item
            assert "po_number" in item
            assert "vendor" in item
            assert "balance" in item
            assert "due_date" in item
            print(f"PASS: Due this week structure - {item['po_number']}")
        else:
            print("PASS: No due_this_week items")


class TestExistingDashboardEndpoints:
    """Tests for existing dashboard endpoints to ensure no regression"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert login_res.status_code == 200
        self.token = login_res.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_01_dashboard_stats_still_works(self):
        """Verify /api/dashboard/stats still works after changes"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        # Verify essential KPI fields still exist
        assert "today_revenue" in data
        assert "today_sales_count" in data
        assert "today_cash_sales" in data
        assert "today_credit_sales" in data
        assert "total_receivables" in data
        assert "ar_aging" in data
        
        print(f"PASS: dashboard/stats - Revenue: {data['today_revenue']}, Sales: {data['today_sales_count']}")
    
    def test_02_branch_summary_still_works(self):
        """Verify /api/dashboard/branch-summary still works"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/branch-summary",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "branches" in data
        assert "totals" in data
        
        print(f"PASS: branch-summary - {len(data['branches'])} branches")
    
    def test_03_pending_reviews_still_works(self):
        """Verify /api/dashboard/pending-reviews still works"""
        res = requests.get(
            f"{BASE_URL}/api/dashboard/pending-reviews",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "items" in data
        assert "total_count" in data
        
        print(f"PASS: pending-reviews - {data['total_count']} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
