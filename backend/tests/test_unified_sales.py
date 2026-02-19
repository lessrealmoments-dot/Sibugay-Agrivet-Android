"""
Unified Sales Page Backend Tests
Tests for:
- /unified-sale endpoint (cash, partial, credit sales)
- /auth/verify-manager-pin endpoint
- /customers/{id}/transactions endpoint
- /dashboard/stats total_receivables
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUnifiedSalesBackend:
    """Tests for the new Unified Sales system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and test data"""
        # Login
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        self.token = login_res.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Get branch
        branches_res = requests.get(f"{BASE_URL}/api/branches", headers=self.headers)
        assert branches_res.status_code == 200
        self.branch_id = branches_res.json()[0]["id"]
        
        # Get a product with stock
        inventory_res = requests.get(
            f"{BASE_URL}/api/inventory?branch_id={self.branch_id}",
            headers=self.headers
        )
        assert inventory_res.status_code == 200
        items = inventory_res.json().get("items", [])
        # Find a product with stock > 5 and not a repack
        for item in items:
            if item.get("total_stock", 0) > 5 and not item.get("is_repack", False):
                self.test_product = item
                break
        else:
            # Fallback to first item with stock
            for item in items:
                if item.get("total_stock", 0) > 1:
                    self.test_product = item
                    break
        
        # Get a customer with balance
        customers_res = requests.get(f"{BASE_URL}/api/customers?limit=10", headers=self.headers)
        assert customers_res.status_code == 200
        customers = customers_res.json().get("customers", [])
        self.test_customer = customers[0] if customers else None
    
    # ==================== Manager PIN Verification Tests ====================
    
    def test_verify_manager_pin_valid(self):
        """Test valid manager PIN (1234) returns valid=true"""
        res = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            json={"pin": "1234"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] == True
        assert "manager_id" in data
        assert "manager_name" in data
        print(f"✓ Valid PIN approved by {data['manager_name']}")
    
    def test_verify_manager_pin_invalid(self):
        """Test invalid PIN returns valid=false"""
        res = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            json={"pin": "9999"},
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] == False
        print("✓ Invalid PIN correctly rejected")
    
    def test_verify_manager_pin_empty(self):
        """Test empty PIN returns 400 error"""
        res = requests.post(
            f"{BASE_URL}/api/auth/verify-manager-pin",
            json={"pin": ""},
            headers=self.headers
        )
        assert res.status_code == 400
        print("✓ Empty PIN returns 400 error")
    
    # ==================== Unified Sale - Cash Sale Tests ====================
    
    def test_unified_sale_cash_full_payment(self):
        """Test cash sale with full payment creates paid invoice"""
        if not self.test_product:
            pytest.skip("No product with stock available")
        
        rate = self.test_product.get("prices", {}).get("retail", 100)
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_id": None,
                "customer_name": "TEST_CashSale Walk-in",
                "items": [{"product_id": self.test_product["id"], "quantity": 1, "rate": rate}],
                "payment_type": "cash",
                "amount_paid": rate
            },
            headers=self.headers
        )
        assert res.status_code == 200, f"Unified sale failed: {res.text}"
        data = res.json()
        
        assert "invoice_number" in data
        assert data["grand_total"] == rate
        assert data["amount_paid"] == rate
        assert data["balance"] == 0
        assert data["status"] == "paid"
        assert data["payment_type"] == "cash"
        print(f"✓ Cash sale created invoice {data['invoice_number']}, status=paid")
    
    def test_unified_sale_no_branch(self):
        """Test unified sale without branch returns 400"""
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "customer_name": "Test",
                "items": [{"product_id": "test", "quantity": 1, "rate": 100}],
                "payment_type": "cash",
                "amount_paid": 100
            },
            headers=self.headers
        )
        assert res.status_code == 400
        assert "Branch ID required" in res.json().get("detail", "")
        print("✓ Missing branch_id returns 400 error")
    
    def test_unified_sale_no_items(self):
        """Test unified sale without items returns 400"""
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_name": "Test",
                "items": [],
                "payment_type": "cash",
                "amount_paid": 0
            },
            headers=self.headers
        )
        assert res.status_code == 400
        assert "No items" in res.json().get("detail", "")
        print("✓ Empty items returns 400 error")
    
    # ==================== Unified Sale - Partial Payment Tests ====================
    
    def test_unified_sale_partial_payment(self):
        """Test partial payment creates open invoice with balance"""
        if not self.test_product or not self.test_customer:
            pytest.skip("No product or customer available")
        
        rate = self.test_product.get("prices", {}).get("retail", 100)
        partial_amount = rate // 2  # Pay half
        
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_id": self.test_customer["id"],
                "customer_name": self.test_customer["name"],
                "items": [{"product_id": self.test_product["id"], "quantity": 1, "rate": rate}],
                "payment_type": "partial",
                "amount_paid": partial_amount
            },
            headers=self.headers
        )
        assert res.status_code == 200, f"Partial sale failed: {res.text}"
        data = res.json()
        
        assert data["grand_total"] == rate
        assert data["amount_paid"] == partial_amount
        assert data["balance"] == rate - partial_amount
        assert data["status"] == "partial"
        assert data["payment_type"] == "partial"
        print(f"✓ Partial sale created invoice {data['invoice_number']}, balance={data['balance']}")
    
    # ==================== Unified Sale - Credit Sale Tests ====================
    
    def test_unified_sale_credit_full(self):
        """Test credit sale creates open invoice with full balance"""
        if not self.test_product or not self.test_customer:
            pytest.skip("No product or customer available")
        
        rate = self.test_product.get("prices", {}).get("retail", 100)
        
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_id": self.test_customer["id"],
                "customer_name": self.test_customer["name"],
                "items": [{"product_id": self.test_product["id"], "quantity": 1, "rate": rate}],
                "payment_type": "credit",
                "amount_paid": 0,
                "approved_by": "Administrator"  # Manager approved
            },
            headers=self.headers
        )
        assert res.status_code == 200, f"Credit sale failed: {res.text}"
        data = res.json()
        
        assert data["grand_total"] == rate
        assert data["amount_paid"] == 0
        assert data["balance"] == rate
        assert data["status"] == "open"
        assert data["payment_type"] == "credit"
        assert data["approved_by"] == "Administrator"
        print(f"✓ Credit sale created invoice {data['invoice_number']}, balance={data['balance']}")
    
    # ==================== Customer Transactions Tests ====================
    
    def test_customer_transactions_endpoint(self):
        """Test customer transactions endpoint returns invoices and summary"""
        if not self.test_customer:
            pytest.skip("No customer available")
        
        res = requests.get(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/transactions",
            headers=self.headers
        )
        assert res.status_code == 200, f"Transactions fetch failed: {res.text}"
        data = res.json()
        
        # Check structure
        assert "customer" in data
        assert "invoices" in data
        assert "receivables" in data
        assert "summary" in data
        
        # Check summary fields
        summary = data["summary"]
        assert "total_invoiced" in summary
        assert "total_paid" in summary
        assert "total_balance" in summary
        assert "invoice_count" in summary
        assert "open_invoices" in summary
        
        print(f"✓ Customer transactions: {summary['invoice_count']} invoices, balance={summary['total_balance']}")
    
    def test_customer_transactions_invalid_customer(self):
        """Test customer transactions with invalid customer ID"""
        res = requests.get(
            f"{BASE_URL}/api/customers/invalid-customer-id/transactions",
            headers=self.headers
        )
        assert res.status_code == 200  # Returns empty data, not 404
        data = res.json()
        assert data["customer"] is None
        print("✓ Invalid customer returns null customer with empty invoices")
    
    # ==================== Dashboard Receivables Tests ====================
    
    def test_dashboard_stats_total_receivables(self):
        """Test dashboard stats includes total_receivables from both invoices and receivables"""
        res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert res.status_code == 200, f"Dashboard stats failed: {res.text}"
        data = res.json()
        
        assert "total_receivables" in data
        assert isinstance(data["total_receivables"], (int, float))
        assert data["total_receivables"] >= 0
        
        # Check other expected fields
        assert "today_revenue" in data
        assert "today_sales_count" in data
        assert "total_products" in data
        assert "total_customers" in data
        assert "recent_sales" in data
        
        print(f"✓ Dashboard total_receivables: {data['total_receivables']}")
    
    # ==================== Mode Toggle Test ====================
    
    def test_unified_sale_quick_mode(self):
        """Test unified sale with mode='quick'"""
        if not self.test_product:
            pytest.skip("No product available")
        
        rate = self.test_product.get("prices", {}).get("retail", 100)
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_name": "TEST_QuickMode Walk-in",
                "items": [{"product_id": self.test_product["id"], "quantity": 1, "rate": rate}],
                "payment_type": "cash",
                "amount_paid": rate,
                "mode": "quick"
            },
            headers=self.headers
        )
        assert res.status_code == 200, f"Quick mode sale failed: {res.text}"
        data = res.json()
        assert data.get("mode") == "quick"
        print(f"✓ Quick mode sale created: {data['invoice_number']}")
    
    def test_unified_sale_order_mode(self):
        """Test unified sale with mode='order'"""
        if not self.test_product:
            pytest.skip("No product available")
        
        rate = self.test_product.get("prices", {}).get("retail", 100)
        res = requests.post(
            f"{BASE_URL}/api/unified-sale",
            json={
                "branch_id": self.branch_id,
                "customer_name": "TEST_OrderMode Walk-in",
                "items": [{"product_id": self.test_product["id"], "quantity": 1, "rate": rate}],
                "payment_type": "cash",
                "amount_paid": rate,
                "mode": "order",
                "terms": "COD",
                "customer_po": "PO-TEST-001"
            },
            headers=self.headers
        )
        assert res.status_code == 200, f"Order mode sale failed: {res.text}"
        data = res.json()
        assert data.get("mode") == "order"
        assert data.get("customer_po") == "PO-TEST-001"
        print(f"✓ Order mode sale created: {data['invoice_number']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
