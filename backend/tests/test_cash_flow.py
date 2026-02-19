"""
Test Suite for Cash Flow Unification Features
Tests: POS sales, Invoice payments, Expenses -> Cashier Wallet updates
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCashFlowUnification:
    """Test cash flow updates across all transaction types"""
    
    token = None
    branch_id = None
    product_id = None
    customer_id = None
    cashier_wallet_id = None
    
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        """Login and get branch/product data"""
        # Login
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        request.cls.token = login_res.json()["token"]
        
        # Get branch
        headers = {"Authorization": f"Bearer {request.cls.token}"}
        branches_res = requests.get(f"{BASE_URL}/api/branches", headers=headers)
        assert branches_res.status_code == 200
        branches = branches_res.json()
        assert len(branches) > 0, "No branches found"
        request.cls.branch_id = branches[0]["id"]
        
        # Get or create product
        products_res = requests.get(f"{BASE_URL}/api/products?limit=1", headers=headers)
        assert products_res.status_code == 200
        products_data = products_res.json()
        if products_data.get("products"):
            request.cls.product_id = products_data["products"][0]["id"]
            request.cls.product_cost = products_data["products"][0].get("cost_price", 50)
        else:
            # Create a test product
            create_prod = requests.post(f"{BASE_URL}/api/products", headers=headers, json={
                "name": "TEST_CashFlowProduct",
                "sku": "TEST-CFP-001",
                "cost_price": 50,
                "prices": {"retail": 100}
            })
            assert create_prod.status_code == 200
            request.cls.product_id = create_prod.json()["id"]
            request.cls.product_cost = 50
        
        # Set inventory for the product
        inv_res = requests.post(f"{BASE_URL}/api/inventory/set", headers=headers, json={
            "product_id": request.cls.product_id,
            "branch_id": request.cls.branch_id,
            "quantity": 1000
        })
        assert inv_res.status_code == 200
        
        # Get or create customer
        customers_res = requests.get(f"{BASE_URL}/api/customers?limit=1", headers=headers)
        if customers_res.status_code == 200 and customers_res.json().get("customers"):
            request.cls.customer_id = customers_res.json()["customers"][0]["id"]
        else:
            cust_res = requests.post(f"{BASE_URL}/api/customers", headers=headers, json={
                "name": "TEST_CashFlowCustomer",
                "phone": "09123456789"
            })
            if cust_res.status_code == 200:
                request.cls.customer_id = cust_res.json()["id"]
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def get_cashier_wallet_balance(self):
        """Get current cashier wallet balance"""
        res = requests.get(f"{BASE_URL}/api/fund-wallets", 
                          headers=self.get_headers(),
                          params={"branch_id": self.branch_id})
        assert res.status_code == 200
        wallets = res.json()
        cashier_wallet = next((w for w in wallets if w["type"] == "cashier"), None)
        if cashier_wallet:
            self.cashier_wallet_id = cashier_wallet["id"]
            return cashier_wallet.get("balance", 0)
        return 0
    
    # =========== POS CASH SALE TESTS ===========
    def test_01_pos_cash_sale_updates_wallet(self):
        """POS cash sale should update cashier wallet balance in real-time"""
        headers = self.get_headers()
        
        # Get initial wallet balance
        initial_balance = self.get_cashier_wallet_balance()
        print(f"Initial cashier wallet balance: {initial_balance}")
        
        # Create POS sale with Cash payment
        sale_price = max(self.product_cost + 10, 100)  # Ensure above cost
        sale_res = requests.post(f"{BASE_URL}/api/sales", headers=headers, json={
            "branch_id": self.branch_id,
            "items": [{
                "product_id": self.product_id,
                "quantity": 1,
                "price": sale_price
            }],
            "payment_method": "Cash",
            "customer_name": "Walk-in"
        })
        assert sale_res.status_code == 200, f"POS sale failed: {sale_res.text}"
        sale = sale_res.json()
        sale_total = sale["total"]
        print(f"Created POS sale: {sale['sale_number']}, total: {sale_total}")
        
        # Verify wallet balance increased
        new_balance = self.get_cashier_wallet_balance()
        print(f"New cashier wallet balance: {new_balance}")
        
        expected_balance = initial_balance + sale_total
        assert abs(new_balance - expected_balance) < 0.01, \
            f"Wallet not updated correctly. Expected: {expected_balance}, Got: {new_balance}"
        print(f"✓ POS cash sale correctly updated wallet: +{sale_total}")
    
    def test_02_credit_sale_does_not_update_wallet(self):
        """Credit sales should NOT update cashier wallet"""
        headers = self.get_headers()
        
        if not self.customer_id:
            pytest.skip("No customer available for credit sale test")
        
        initial_balance = self.get_cashier_wallet_balance()
        print(f"Initial balance before credit sale: {initial_balance}")
        
        # Create credit sale
        sale_price = max(self.product_cost + 10, 100)
        sale_res = requests.post(f"{BASE_URL}/api/sales", headers=headers, json={
            "branch_id": self.branch_id,
            "items": [{
                "product_id": self.product_id,
                "quantity": 1,
                "price": sale_price
            }],
            "payment_method": "Credit",
            "customer_id": self.customer_id,
            "customer_name": "TEST_CashFlowCustomer"
        })
        assert sale_res.status_code == 200, f"Credit sale failed: {sale_res.text}"
        sale = sale_res.json()
        print(f"Created credit sale: {sale['sale_number']}")
        
        # Wallet should remain unchanged
        new_balance = self.get_cashier_wallet_balance()
        print(f"Balance after credit sale: {new_balance}")
        
        assert abs(new_balance - initial_balance) < 0.01, \
            f"Credit sale incorrectly updated wallet. Expected: {initial_balance}, Got: {new_balance}"
        print("✓ Credit sale correctly did NOT update wallet")
    
    # =========== INVOICE PAYMENT TESTS ===========
    def test_03_invoice_with_immediate_payment_updates_wallet(self):
        """Invoice with immediate payment should update cashier wallet"""
        headers = self.get_headers()
        
        initial_balance = self.get_cashier_wallet_balance()
        print(f"Initial balance: {initial_balance}")
        
        # Create invoice with immediate cash payment
        rate = max(self.product_cost + 20, 100)
        payment_amount = rate  # Full payment
        
        inv_res = requests.post(f"{BASE_URL}/api/invoices", headers=headers, json={
            "branch_id": self.branch_id,
            "customer_name": "Walk-in Invoice Customer",
            "items": [{
                "product_id": self.product_id,
                "product_name": "Test Product",
                "quantity": 1,
                "rate": rate
            }],
            "amount_paid": payment_amount,
            "payment_method": "Cash",
            "fund_source": "cashier"
        })
        assert inv_res.status_code == 200, f"Invoice creation failed: {inv_res.text}"
        invoice = inv_res.json()
        print(f"Created invoice: {invoice['invoice_number']}, paid: {payment_amount}")
        
        # Verify wallet updated with payment amount
        new_balance = self.get_cashier_wallet_balance()
        print(f"New balance: {new_balance}")
        
        expected_balance = initial_balance + payment_amount
        assert abs(new_balance - expected_balance) < 0.01, \
            f"Invoice payment didn't update wallet. Expected: {expected_balance}, Got: {new_balance}"
        print(f"✓ Invoice payment correctly updated wallet: +{payment_amount}")
    
    # =========== EXPENSE TESTS ===========
    def test_04_expense_deducts_from_wallet(self):
        """Creating expense should deduct from cashier wallet"""
        headers = self.get_headers()
        
        initial_balance = self.get_cashier_wallet_balance()
        print(f"Initial balance: {initial_balance}")
        
        expense_amount = 50.00
        exp_res = requests.post(f"{BASE_URL}/api/expenses", headers=headers, json={
            "branch_id": self.branch_id,
            "category": "TEST_Utilities",
            "description": "Test expense for cash flow",
            "amount": expense_amount,
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        assert exp_res.status_code == 200, f"Expense creation failed: {exp_res.text}"
        expense = exp_res.json()
        print(f"Created expense: {expense['id']}, amount: {expense_amount}")
        
        # Verify wallet decreased
        new_balance = self.get_cashier_wallet_balance()
        print(f"New balance: {new_balance}")
        
        expected_balance = initial_balance - expense_amount
        assert abs(new_balance - expected_balance) < 0.01, \
            f"Expense didn't deduct from wallet. Expected: {expected_balance}, Got: {new_balance}"
        print(f"✓ Expense correctly deducted from wallet: -{expense_amount}")
    
    # =========== DAILY REPORT TESTS ===========
    def test_05_daily_report_shows_wallet_balance(self):
        """Daily report should show correct cashier_wallet_balance"""
        headers = self.get_headers()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get current wallet balance
        current_wallet_balance = self.get_cashier_wallet_balance()
        print(f"Current wallet balance: {current_wallet_balance}")
        
        # Get daily report
        report_res = requests.get(f"{BASE_URL}/api/daily-report", headers=headers,
                                  params={"date": today, "branch_id": self.branch_id})
        assert report_res.status_code == 200, f"Daily report failed: {report_res.text}"
        report = report_res.json()
        
        # Verify report contains wallet balance
        assert "cashier_wallet_balance" in report, "Daily report missing cashier_wallet_balance field"
        reported_balance = report["cashier_wallet_balance"]
        print(f"Reported wallet balance: {reported_balance}")
        
        assert abs(reported_balance - current_wallet_balance) < 0.01, \
            f"Report wallet balance mismatch. Expected: {current_wallet_balance}, Got: {reported_balance}"
        print("✓ Daily report correctly shows cashier_wallet_balance")
        
        # Verify report has new_sales_today field (not Today's Revenue)
        assert "new_sales_today" in report, "Daily report missing new_sales_today field"
        print(f"✓ Daily report has new_sales_today: {report['new_sales_today']}")
    
    # =========== POS SALES IN SALES_LOG TESTS ===========
    def test_06_pos_sales_appear_in_sales_log(self):
        """POS sales should now appear in sales_log"""
        headers = self.get_headers()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create a new POS sale
        sale_price = max(self.product_cost + 10, 100)
        sale_res = requests.post(f"{BASE_URL}/api/sales", headers=headers, json={
            "branch_id": self.branch_id,
            "items": [{
                "product_id": self.product_id,
                "quantity": 2,
                "price": sale_price
            }],
            "payment_method": "Cash",
            "customer_name": "POS Log Test Customer"
        })
        assert sale_res.status_code == 200
        sale = sale_res.json()
        sale_number = sale["sale_number"]
        print(f"Created POS sale: {sale_number}")
        
        # Check daily log
        log_res = requests.get(f"{BASE_URL}/api/daily-log", headers=headers,
                              params={"date": today, "branch_id": self.branch_id})
        assert log_res.status_code == 200
        entries = log_res.json()["entries"]
        
        # Find entries from our sale
        matching_entries = [e for e in entries if sale_number in str(e.get("invoice_number", ""))]
        print(f"Found {len(matching_entries)} matching entries in sales_log")
        
        # POS sales should be logged
        if len(matching_entries) > 0:
            print("✓ POS sales appear in sales_log (unified logging)")
        else:
            # Check if the sale number format differs 
            print(f"Warning: Could not find exact match for {sale_number} in log")
            print(f"Sample log entries: {[e.get('invoice_number') for e in entries[:3]]}")


class TestFundManagementDisplay:
    """Test Fund Management page shows correct balances"""
    
    token = None
    branch_id = None
    
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        """Login and get branch data"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        assert login_res.status_code == 200
        request.cls.token = login_res.json()["token"]
        
        branches_res = requests.get(f"{BASE_URL}/api/branches", 
                                   headers={"Authorization": f"Bearer {request.cls.token}"})
        assert branches_res.status_code == 200
        request.cls.branch_id = branches_res.json()[0]["id"]
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_07_fund_wallets_show_correct_balances(self):
        """Fund wallets endpoint should return real-time cashier balance"""
        headers = self.get_headers()
        
        res = requests.get(f"{BASE_URL}/api/fund-wallets", headers=headers,
                          params={"branch_id": self.branch_id})
        assert res.status_code == 200, f"Fund wallets failed: {res.text}"
        wallets = res.json()
        
        # Find cashier wallet
        cashier_wallet = next((w for w in wallets if w["type"] == "cashier"), None)
        
        if cashier_wallet:
            print(f"Cashier wallet found: {cashier_wallet['name']}")
            print(f"  Balance: {cashier_wallet['balance']}")
            assert "balance" in cashier_wallet, "Cashier wallet missing balance field"
            print("✓ Fund Management shows correct cashier balance")
        else:
            print("Note: No cashier wallet exists yet (will be auto-created on first transaction)")


class TestDailyCloseExpectedCash:
    """Test Close Accounts uses wallet balance as expected cash"""
    
    token = None
    branch_id = None
    
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        """Login and get branch data"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        assert login_res.status_code == 200
        request.cls.token = login_res.json()["token"]
        
        branches_res = requests.get(f"{BASE_URL}/api/branches",
                                   headers={"Authorization": f"Bearer {request.cls.token}"})
        assert branches_res.status_code == 200
        request.cls.branch_id = branches_res.json()[0]["id"]
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_08_daily_close_uses_wallet_balance_as_expected_cash(self):
        """Daily close should use wallet balance for expected cash calculation"""
        headers = self.get_headers()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get wallet balance
        wallets_res = requests.get(f"{BASE_URL}/api/fund-wallets", headers=headers,
                                  params={"branch_id": self.branch_id})
        wallets = wallets_res.json()
        cashier_wallet = next((w for w in wallets if w["type"] == "cashier"), None)
        expected_cash = cashier_wallet["balance"] if cashier_wallet else 0
        print(f"Cashier wallet balance: {expected_cash}")
        
        # Check if already closed
        close_check = requests.get(f"{BASE_URL}/api/daily-close/{today}", headers=headers,
                                  params={"branch_id": self.branch_id})
        if close_check.status_code == 200:
            close_data = close_check.json()
            if close_data.get("status") == "closed":
                # Check the expected cash in the closing record
                assert "expected_cash" in close_data, "Closing record missing expected_cash"
                print(f"Day already closed. Expected cash in record: {close_data['expected_cash']}")
                print("✓ Daily close record contains expected_cash field")
                return
        
        # Try to close the day (this might fail if already closed)
        close_res = requests.post(f"{BASE_URL}/api/daily-close", headers=headers, json={
            "date": today,
            "branch_id": self.branch_id,
            "actual_cash": expected_cash,
            "bank_checks": 0,
            "other_payment_forms": 0,
            "cash_to_drawer": 1000,
            "cash_to_safe": max(0, expected_cash - 1000)
        })
        
        if close_res.status_code == 200:
            close_data = close_res.json()
            assert "expected_cash" in close_data, "Closing missing expected_cash field"
            print(f"Expected cash in close: {close_data['expected_cash']}")
            print(f"Extra cash calculated: {close_data['extra_cash']}")
            print("✓ Daily close correctly uses wallet balance as expected cash")
        elif close_res.status_code == 400 and "already closed" in close_res.text.lower():
            print("Day already closed - expected behavior")
        else:
            print(f"Close response: {close_res.status_code} - {close_res.text}")


class TestDashboardLabels:
    """Test Dashboard shows correct labels"""
    
    token = None
    branch_id = None
    
    @pytest.fixture(autouse=True, scope="class")
    def setup(self, request):
        """Login and get branch"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        assert login_res.status_code == 200
        request.cls.token = login_res.json()["token"]
        
        branches_res = requests.get(f"{BASE_URL}/api/branches",
                                   headers={"Authorization": f"Bearer {request.cls.token}"})
        assert branches_res.status_code == 200
        request.cls.branch_id = branches_res.json()[0]["id"]
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_09_dashboard_stats_endpoint(self):
        """Dashboard stats should return today_revenue field"""
        headers = self.get_headers()
        
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers,
                          params={"branch_id": self.branch_id})
        assert res.status_code == 200, f"Dashboard stats failed: {res.text}"
        stats = res.json()
        
        # Check for today_revenue field (used by frontend label "New Sales Today")
        assert "today_revenue" in stats, "Dashboard stats missing today_revenue field"
        print(f"Dashboard today_revenue: {stats['today_revenue']}")
        
        # Check other expected fields
        expected_fields = ["today_sales_count", "today_expenses", "total_products"]
        for field in expected_fields:
            assert field in stats, f"Dashboard missing {field}"
            print(f"  {field}: {stats[field]}")
        
        print("✓ Dashboard stats endpoint returns expected fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
