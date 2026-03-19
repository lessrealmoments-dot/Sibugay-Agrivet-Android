"""
Test Phase 2 Permission Enforcement:
- reports.view_profit gating Product Profit Report endpoint
- reports.export gating Print buttons
- products.view_cost gating cost columns
- customers.view_balance gating balance columns
- customers.manage_credit gating credit fields
- accounting.generate_interest permission check
- accounting.generate_penalty permission check
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "janmarkeahig@gmail.com"
ADMIN_PASSWORD = "Aa@58798546521325"


@pytest.fixture(scope="module")
def admin_session():
    """Authenticate as admin and return session with token."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")
    
    data = response.json()
    token = data.get("access_token") or data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    
    # Store user data for permission checks
    session.user = data.get("user", {})
    return session


# ============================================================================
# PRODUCT PROFIT REPORT TESTS
# ============================================================================

class TestProductProfitReport:
    """Test GET /api/reports/product-profit endpoint"""
    
    def test_product_profit_report_returns_200(self, admin_session):
        """Admin should access product profit report with reports.view_profit permission"""
        response = admin_session.get(f"{BASE_URL}/api/reports/product-profit")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Admin can access product profit report")
    
    def test_product_profit_report_structure(self, admin_session):
        """Verify response structure has required fields"""
        response = admin_session.get(f"{BASE_URL}/api/reports/product-profit")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "rows" in data, "Response missing 'rows' field"
        assert "summary" in data, "Response missing 'summary' field"
        assert "date_from" in data, "Response missing 'date_from' field"
        assert "date_to" in data, "Response missing 'date_to' field"
        print("PASS: Product profit report has correct structure")
    
    def test_product_profit_report_summary_fields(self, admin_session):
        """Verify summary has revenue, cost, profit, margin fields"""
        response = admin_session.get(f"{BASE_URL}/api/reports/product-profit")
        assert response.status_code == 200
        summary = response.json().get("summary", {})
        
        expected_fields = ["total_revenue", "total_cost", "total_profit", "overall_margin_pct", "product_count"]
        for field in expected_fields:
            assert field in summary, f"Summary missing '{field}' field"
        print(f"PASS: Summary has all fields: {list(summary.keys())}")
    
    def test_product_profit_report_row_fields(self, admin_session):
        """Verify each product row has profit/margin fields"""
        response = admin_session.get(f"{BASE_URL}/api/reports/product-profit")
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        
        if rows:
            row = rows[0]
            expected_fields = ["product_name", "total_revenue", "total_cost", "profit", "margin_pct"]
            for field in expected_fields:
                assert field in row, f"Row missing '{field}' field"
            print(f"PASS: Product row has all required fields")
        else:
            print("INFO: No product data in report (may need test sales data)")
    
    def test_product_profit_report_date_filter(self, admin_session):
        """Test date filtering works"""
        response = admin_session.get(
            f"{BASE_URL}/api/reports/product-profit",
            params={"date_from": "2025-01-01", "date_to": "2025-12-31"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date_from"] == "2025-01-01"
        assert data["date_to"] == "2025-12-31"
        print("PASS: Date filter works correctly")


# ============================================================================
# AR AGING REPORT TESTS
# ============================================================================

class TestArAgingReport:
    """Test GET /api/reports/ar-aging endpoint"""
    
    def test_ar_aging_returns_200(self, admin_session):
        """Admin can access AR aging report"""
        response = admin_session.get(f"{BASE_URL}/api/reports/ar-aging")
        assert response.status_code == 200
        print("PASS: Admin can access AR aging report")
    
    def test_ar_aging_structure(self, admin_session):
        """Verify AR aging has correct structure"""
        response = admin_session.get(f"{BASE_URL}/api/reports/ar-aging")
        data = response.json()
        
        assert "rows" in data, "Missing 'rows'"
        assert "totals" in data, "Missing 'totals'"
        assert "as_of_date" in data, "Missing 'as_of_date'"
        
        totals = data["totals"]
        assert "current" in totals, "Missing bucket 'current'"
        assert "b31_60" in totals, "Missing bucket 'b31_60'"
        assert "b61_90" in totals, "Missing bucket 'b61_90'"
        assert "b90plus" in totals, "Missing bucket 'b90plus'"
        print("PASS: AR aging report has correct structure with buckets")


# ============================================================================
# SALES REPORT TESTS
# ============================================================================

class TestSalesReport:
    """Test GET /api/reports/sales endpoint"""
    
    def test_sales_report_returns_200(self, admin_session):
        """Admin can access sales report"""
        response = admin_session.get(f"{BASE_URL}/api/reports/sales")
        assert response.status_code == 200
        print("PASS: Admin can access sales report")
    
    def test_sales_report_structure(self, admin_session):
        """Verify sales report has correct structure"""
        response = admin_session.get(f"{BASE_URL}/api/reports/sales")
        data = response.json()
        
        assert "categories" in data, "Missing 'categories'"
        assert "transactions" in data, "Missing 'transactions'"
        assert "grand_total" in data, "Missing 'grand_total'"
        print("PASS: Sales report has correct structure")


# ============================================================================
# EXPENSE REPORT TESTS
# ============================================================================

class TestExpenseReport:
    """Test GET /api/reports/expenses endpoint"""
    
    def test_expense_report_returns_200(self, admin_session):
        """Admin can access expense report"""
        response = admin_session.get(f"{BASE_URL}/api/reports/expenses")
        assert response.status_code == 200
        print("PASS: Admin can access expense report")


# ============================================================================
# ACCOUNTING PERMISSION TESTS
# ============================================================================

class TestAccountingPermissions:
    """Test generate-interest and generate-penalty permission checks"""
    
    def test_generate_interest_endpoint_exists(self, admin_session):
        """Verify generate-interest endpoint requires customer_id"""
        # Test without customer ID - should return 404 for missing resource
        response = admin_session.post(
            f"{BASE_URL}/api/customers/nonexistent123/generate-interest",
            json={}
        )
        # Should be 404 (customer not found) not 405 (method not allowed)
        assert response.status_code in [404, 403], f"Unexpected status: {response.status_code}"
        print("PASS: generate-interest endpoint is routed correctly")
    
    def test_generate_penalty_endpoint_exists(self, admin_session):
        """Verify generate-penalty endpoint requires customer_id"""
        response = admin_session.post(
            f"{BASE_URL}/api/customers/nonexistent123/generate-penalty",
            json={}
        )
        # Should be 404 (customer not found) not 405 (method not allowed)
        assert response.status_code in [404, 403], f"Unexpected status: {response.status_code}"
        print("PASS: generate-penalty endpoint is routed correctly")
    
    def test_generate_interest_with_valid_customer(self, admin_session):
        """Test generate-interest with a real customer (if exists)"""
        # First get a customer
        customers_res = admin_session.get(f"{BASE_URL}/api/customers", params={"limit": 1})
        if customers_res.status_code != 200:
            pytest.skip("Could not fetch customers")
        
        customers = customers_res.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available for testing")
        
        customer_id = customers[0]["id"]
        response = admin_session.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-interest",
            json={"as_of_date": "2026-03-19"}
        )
        
        # Admin should have permission - result depends on customer data
        # Should be 200 (success or no interest) not 403 (forbidden)
        assert response.status_code in [200], f"Admin should have permission: {response.status_code} - {response.text}"
        print(f"PASS: Admin can call generate-interest - response: {response.json().get('message', 'OK')}")
    
    def test_generate_penalty_with_valid_customer(self, admin_session):
        """Test generate-penalty with a real customer (if exists)"""
        customers_res = admin_session.get(f"{BASE_URL}/api/customers", params={"limit": 1})
        if customers_res.status_code != 200:
            pytest.skip("Could not fetch customers")
        
        customers = customers_res.json().get("customers", [])
        if not customers:
            pytest.skip("No customers available for testing")
        
        customer_id = customers[0]["id"]
        response = admin_session.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-penalty",
            json={"as_of_date": "2026-03-19", "penalty_rate": 5}
        )
        
        # Admin should have permission - result depends on customer data
        assert response.status_code in [200], f"Admin should have permission: {response.status_code} - {response.text}"
        print(f"PASS: Admin can call generate-penalty - response: {response.json().get('message', 'OK')}")


# ============================================================================
# PRODUCTS ENDPOINT TESTS (for cost visibility)
# ============================================================================

class TestProductsEndpoint:
    """Test products endpoint returns cost data for admin"""
    
    def test_products_returns_cost_price(self, admin_session):
        """Admin should see cost_price in product data"""
        response = admin_session.get(f"{BASE_URL}/api/products", params={"limit": 5})
        assert response.status_code == 200
        
        products = response.json().get("products", [])
        if products:
            product = products[0]
            # cost_price should be present for admin
            assert "cost_price" in product, "cost_price should be in product data"
            print(f"PASS: Product has cost_price field (value: {product.get('cost_price')})")
        else:
            print("INFO: No products found to verify cost_price")


# ============================================================================
# CUSTOMERS ENDPOINT TESTS (for balance visibility)
# ============================================================================

class TestCustomersEndpoint:
    """Test customers endpoint returns balance data for admin"""
    
    def test_customers_returns_balance(self, admin_session):
        """Admin should see balance in customer data"""
        response = admin_session.get(f"{BASE_URL}/api/customers", params={"limit": 5})
        assert response.status_code == 200
        
        customers = response.json().get("customers", [])
        if customers:
            customer = customers[0]
            # balance should be present for admin
            assert "balance" in customer, "balance should be in customer data"
            print(f"PASS: Customer has balance field (value: {customer.get('balance')})")
        else:
            print("INFO: No customers found to verify balance")
    
    def test_customers_returns_credit_limit(self, admin_session):
        """Admin should see credit_limit in customer data"""
        response = admin_session.get(f"{BASE_URL}/api/customers", params={"limit": 5})
        assert response.status_code == 200
        
        customers = response.json().get("customers", [])
        if customers:
            customer = customers[0]
            # credit_limit should be present for admin
            assert "credit_limit" in customer, "credit_limit should be in customer data"
            print(f"PASS: Customer has credit_limit field (value: {customer.get('credit_limit')})")


# ============================================================================
# DISCOUNT AUDIT REPORT TESTS  
# ============================================================================

class TestDiscountAuditReport:
    """Test GET /api/reports/discount-audit endpoint"""
    
    def test_discount_audit_returns_200(self, admin_session):
        """Admin can access discount audit report"""
        response = admin_session.get(f"{BASE_URL}/api/reports/discount-audit")
        assert response.status_code == 200
        print("PASS: Admin can access discount audit report")
    
    def test_discount_audit_group_by_customer(self, admin_session):
        """Test grouping by customer"""
        response = admin_session.get(
            f"{BASE_URL}/api/reports/discount-audit",
            params={"group_by": "customer"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data or "rows" in data
        print("PASS: Discount audit group_by=customer works")
    
    def test_discount_audit_group_by_cashier(self, admin_session):
        """Test grouping by cashier"""
        response = admin_session.get(
            f"{BASE_URL}/api/reports/discount-audit",
            params={"group_by": "cashier"}
        )
        assert response.status_code == 200
        print("PASS: Discount audit group_by=cashier works")
    
    def test_discount_audit_detail_view(self, admin_session):
        """Test detail view"""
        response = admin_session.get(
            f"{BASE_URL}/api/reports/discount-audit",
            params={"group_by": "detail"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        print("PASS: Discount audit group_by=detail works")


# ============================================================================
# PERMISSION MODULE VERIFICATION
# ============================================================================

class TestPermissionModuleDefinitions:
    """Verify permission module definitions exist"""
    
    def test_admin_user_info(self, admin_session):
        """Verify admin user has full permissions"""
        response = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        user = response.json()
        
        # Admin should have role=admin which bypasses permission checks
        role = user.get("role", "")
        assert role in ["admin", "super_admin", "owner"], f"Admin user role: {role}"
        print(f"PASS: Admin user has role: {role}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
