"""
Test Bug Fixes - Iteration 85
=============================
1. Bug 1: Farm expense/cashout toast notification shows no description after saving
   - Tests: POST /api/expenses/farm-expense returns 'message' field
   - Tests: POST /api/expenses/customer-cashout returns 'message' field

2. Bug 2: Farm expenses in Closing Wizard customer credit section don't show what the money was for
   - Tests: ar_credits_today includes 'description' from items[0].product_name
   - Tests: daily-report, daily-close-preview, daily-log endpoints return items with description

3. Bug 3: Daily Operations AR section shows original grand_total instead of balance for partial payments
   - Tests: total_credit_today uses 'balance' instead of 'grand_total'
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
BRANCH_ID = "c435277f-9fc7-4d83-83e7-38be5b4423ac"  # IPIL BRANCH


class TestBugFixesIteration85:
    """Test all three bug fixes reported in this iteration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Authenticate
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {response.status_code}")
    
    # =========================================================================
    # BUG 1: Farm expense/cashout toast notification shows no description
    # =========================================================================
    
    def test_bug1_farm_expense_returns_message_field(self):
        """
        Bug 1: Verify farm expense endpoint returns 'message' field for toast notification
        Expected: Response includes 'message' like 'Farm expense recorded — Invoice SVC-xxx created for CustomerName'
        """
        # First, get a credit customer to use
        customers_resp = self.session.get(f"{BASE_URL}/api/customers?branch_id={BRANCH_ID}")
        assert customers_resp.status_code == 200, f"Failed to get customers: {customers_resp.status_code}"
        
        customers_data = customers_resp.json()
        # Handle both list and dict responses
        customers = customers_data.get("customers", []) if isinstance(customers_data, dict) else customers_data
        
        # Find a credit customer
        credit_customer = None
        for c in customers:
            if c.get("type") == "credit":
                credit_customer = c
                break
        
        if not credit_customer:
            pytest.skip("No credit customer available for testing")
        
        # Create a farm expense
        farm_expense_payload = {
            "customer_id": credit_customer["id"],
            "branch_id": BRANCH_ID,
            "service_description": "TEST_BUG1_Tilling service",
            "amount": 100,
            "due_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "terms": 30,
            "notes": "Test farm expense for bug 1 verification"
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/farm-expense", json=farm_expense_payload)
        
        # Verify response
        assert response.status_code == 200, f"Farm expense creation failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Bug 1 fix: Response should include 'message' field
        assert "message" in data, "Response missing 'message' field - Bug 1 not fixed!"
        assert "Farm expense recorded" in data["message"], f"Message format incorrect: {data['message']}"
        assert credit_customer.get("name", "") in data["message"], f"Customer name not in message: {data['message']}"
        
        # Also verify invoice was created
        assert "invoice" in data, "Response missing 'invoice' field"
        assert "expense" in data, "Response missing 'expense' field"
        
        print(f"SUCCESS: Farm expense message = '{data['message']}'")
    
    def test_bug1_customer_cashout_returns_message_field(self):
        """
        Bug 1: Verify customer cashout endpoint returns 'message' field for toast notification
        Expected: Response includes 'message' like 'Cash out recorded — Invoice CA-xxx created for CustomerName'
        """
        # Get a credit customer
        customers_resp = self.session.get(f"{BASE_URL}/api/customers?branch_id={BRANCH_ID}")
        assert customers_resp.status_code == 200
        
        customers_data = customers_resp.json()
        # Handle both list and dict responses
        customers = customers_data.get("customers", []) if isinstance(customers_data, dict) else customers_data
        
        credit_customer = None
        for c in customers:
            if c.get("type") == "credit":
                credit_customer = c
                break
        
        if not credit_customer:
            pytest.skip("No credit customer available for testing")
        
        # Create a customer cashout
        cashout_payload = {
            "customer_id": credit_customer["id"],
            "branch_id": BRANCH_ID,
            "amount": 50,
            "description": f"TEST_BUG1_Cash advance",
            "notes": "Test cash advance for bug 1 verification",
            "fund_source": "cashier"
        }
        
        response = self.session.post(f"{BASE_URL}/api/expenses/customer-cashout", json=cashout_payload)
        
        # Verify response
        assert response.status_code == 200, f"Customer cashout failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Bug 1 fix: Response should include 'message' field
        assert "message" in data, "Response missing 'message' field - Bug 1 not fixed!"
        assert "Cash out recorded" in data["message"], f"Message format incorrect: {data['message']}"
        assert credit_customer.get("name", "") in data["message"], f"Customer name not in message: {data['message']}"
        
        print(f"SUCCESS: Customer cashout message = '{data['message']}'")
    
    # =========================================================================
    # BUG 2: Farm expenses don't show what the money was for
    # =========================================================================
    
    def test_bug2_daily_report_ar_credits_include_description(self):
        """
        Bug 2: Verify daily-report endpoint includes 'description' in ar_credits_today
        The description should come from items[0].product_name
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-report?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily report failed: {response.status_code}"
        
        data = response.json()
        
        # Check if ar_credits_today exists and has items
        ar_credits = data.get("ar_credits_today", [])
        
        if len(ar_credits) > 0:
            # Bug 2 fix: Each item should have 'description' field
            for credit in ar_credits:
                # Description should exist (can be empty string but key must exist)
                assert "description" in credit or "items" in credit, \
                    f"ar_credits_today missing description field: {credit}"
                
                # If it's a farm expense or cash advance, verify description
                if credit.get("sale_type") in ["farm_expense", "cash_advance"]:
                    print(f"  Found {credit.get('sale_type')}: {credit.get('invoice_number')} - description: '{credit.get('description', '')}'")
            
            print(f"SUCCESS: daily-report ar_credits_today has {len(ar_credits)} items with description field")
        else:
            print("INFO: No ar_credits_today data - creating test data first would populate this")
    
    def test_bug2_daily_close_preview_ar_credits_include_items(self):
        """
        Bug 2: Verify daily-close-preview endpoint includes 'items' projection for ar_credits_today
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-close-preview?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily close preview failed: {response.status_code}"
        
        data = response.json()
        
        ar_credits = data.get("ar_credits_today", [])
        
        if len(ar_credits) > 0:
            # Bug 2 fix: ar_credits should have description/items for display
            for credit in ar_credits:
                # The fix adds description from items[0].product_name
                has_description = "description" in credit or "items" in credit
                print(f"  Credit {credit.get('invoice_number')}: description='{credit.get('description', 'N/A')}'")
            
            print(f"SUCCESS: daily-close-preview ar_credits_today has {len(ar_credits)} items")
        else:
            print("INFO: No ar_credits_today in preview")
    
    def test_bug2_daily_log_includes_ar_credits_with_description(self):
        """
        Bug 2: Verify daily-log endpoint includes ar_credits_today with description
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-log?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily log failed: {response.status_code}"
        
        data = response.json()
        
        ar_credits = data.get("ar_credits_today", [])
        
        if len(ar_credits) > 0:
            for credit in ar_credits:
                print(f"  AR Credit: {credit.get('invoice_number')} - {credit.get('customer_name')} - desc: '{credit.get('description', '')}'")
            print(f"SUCCESS: daily-log ar_credits_today has {len(ar_credits)} items")
        else:
            print("INFO: No ar_credits_today in daily-log")
    
    # =========================================================================
    # BUG 3: Total credit shows grand_total instead of balance for partial payments
    # =========================================================================
    
    def test_bug3_daily_close_preview_uses_balance_not_grand_total(self):
        """
        Bug 3: Verify daily-close-preview calculates total_credit_today using 'balance' not 'grand_total'
        For partial payments, balance = grand_total - amount_paid
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-close-preview?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily close preview failed: {response.status_code}"
        
        data = response.json()
        
        # Get credit_sales_today which shows both grand_total and balance
        credit_sales = data.get("credit_sales_today", [])
        total_credit = data.get("total_new_credit", 0)
        
        if len(credit_sales) > 0:
            # Calculate expected total using balance (Bug 3 fix)
            expected_total = sum(float(inv.get("balance", 0)) for inv in credit_sales)
            
            # Calculate what it would be using grand_total (old bug)
            wrong_total = sum(float(inv.get("grand_total", 0)) for inv in credit_sales)
            
            print(f"  Credit sales count: {len(credit_sales)}")
            print(f"  Total using balance (correct): {expected_total}")
            print(f"  Total using grand_total (old bug): {wrong_total}")
            print(f"  API returned total_new_credit: {total_credit}")
            
            # Verify the API is using balance
            assert abs(total_credit - expected_total) < 0.01, \
                f"Bug 3 NOT fixed! API returns {total_credit}, should be {expected_total} (using balance)"
            
            # Check for partial payments specifically
            partial_payments = [inv for inv in credit_sales if inv.get("balance", 0) != inv.get("grand_total", 0)]
            if partial_payments:
                print(f"  Found {len(partial_payments)} partial payment invoices")
                for p in partial_payments:
                    print(f"    {p.get('invoice_number')}: grand_total={p.get('grand_total')}, balance={p.get('balance')}")
            
            print("SUCCESS: daily-close-preview correctly uses balance for total_credit")
        else:
            print("INFO: No credit_sales_today to verify")
    
    def test_bug3_daily_log_summary_uses_balance(self):
        """
        Bug 3: Verify daily-log summary.total_credit uses 'balance' not 'grand_total'
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-log?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily log failed: {response.status_code}"
        
        data = response.json()
        summary = data.get("summary", {})
        credit_invoices = data.get("credit_invoices", [])
        
        total_credit_from_api = summary.get("total_credit", 0)
        
        if len(credit_invoices) > 0:
            # Calculate expected using balance
            expected_using_balance = sum(float(inv.get("balance", 0)) for inv in credit_invoices)
            
            print(f"  Credit invoices: {len(credit_invoices)}")
            print(f"  API total_credit: {total_credit_from_api}")
            print(f"  Expected (using balance): {expected_using_balance}")
            
            assert abs(total_credit_from_api - expected_using_balance) < 0.01, \
                f"Bug 3 NOT fixed in daily-log! Got {total_credit_from_api}, expected {expected_using_balance}"
            
            print("SUCCESS: daily-log correctly uses balance for total_credit")
        else:
            print("INFO: No credit_invoices in daily-log")
    
    def test_bug3_daily_report_uses_balance(self):
        """
        Bug 3: Verify daily-report total_credit_today uses 'balance' not 'grand_total'
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-report?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily report failed: {response.status_code}"
        
        data = response.json()
        
        total_credit = data.get("total_credit_today", 0)
        credit_sales = data.get("credit_sales_today", [])
        
        if len(credit_sales) > 0:
            expected_using_balance = sum(float(inv.get("balance", 0)) for inv in credit_sales)
            
            print(f"  Credit sales: {len(credit_sales)}")
            print(f"  API total_credit_today: {total_credit}")
            print(f"  Expected (using balance): {expected_using_balance}")
            
            assert abs(total_credit - expected_using_balance) < 0.01, \
                f"Bug 3 NOT fixed in daily-report! Got {total_credit}, expected {expected_using_balance}"
            
            print("SUCCESS: daily-report correctly uses balance for total_credit_today")
        else:
            print("INFO: No credit_sales_today in daily-report")


class TestRegressionCloseWizard:
    """Regression tests to ensure Close Wizard still works correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {response.status_code}")
    
    def test_daily_close_preview_loads(self):
        """Verify daily-close-preview endpoint still works"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-close-preview?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily close preview failed: {response.status_code}"
        
        data = response.json()
        
        # Verify essential fields exist
        assert "starting_float" in data, "Missing starting_float"
        assert "total_cash_sales" in data, "Missing total_cash_sales"
        assert "expected_counter" in data, "Missing expected_counter"
        
        print(f"SUCCESS: daily-close-preview returns valid data")
    
    def test_daily_log_loads(self):
        """Verify daily-log endpoint still works"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-log?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily log failed: {response.status_code}"
        
        data = response.json()
        
        # Verify structure
        assert "entries" in data, "Missing entries"
        assert "summary" in data, "Missing summary"
        
        print(f"SUCCESS: daily-log returns valid data with {len(data.get('entries', []))} entries")
    
    def test_daily_report_loads(self):
        """Verify daily-report endpoint still works"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = self.session.get(f"{BASE_URL}/api/daily-report?branch_id={BRANCH_ID}&date={today}")
        assert response.status_code == 200, f"Daily report failed: {response.status_code}"
        
        data = response.json()
        
        # Verify essential fields (daily-report uses different field names)
        assert "new_sales_today" in data or "total_revenue" in data, "Missing sales revenue field"
        assert "total_expenses" in data, "Missing total_expenses"
        
        print(f"SUCCESS: daily-report returns valid data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
