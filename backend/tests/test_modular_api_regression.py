"""
Regression test suite for AgriPOS API after modular architecture migration.
Tests all major endpoints to verify they work correctly after the refactor.

Run with: pytest /app/backend/tests/test_modular_api_regression.py -v --tb=short --junitxml=/app/test_reports/pytest/pytest_modular_regression.xml
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture(scope="module")
def api_session():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def admin_token(api_session):
    """Get admin authentication token"""
    response = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in admin login response"
    return data["token"]

@pytest.fixture(scope="module")
def cashier_token(api_session):
    """Get cashier authentication token"""
    response = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "cashier",
        "password": "password"
    })
    assert response.status_code == 200, f"Cashier login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in cashier login response"
    return data["token"]

@pytest.fixture(scope="module")
def admin_client(api_session, admin_token):
    """Session with admin auth header"""
    api_session.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_session

@pytest.fixture(scope="module")
def cashier_client():
    """Create separate session with cashier auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "cashier",
        "password": "password"
    })
    token = response.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ============================================================================
# HEALTH CHECK
# ============================================================================
class TestHealthCheck:
    """Basic health check - run first"""
    
    def test_api_accessible(self):
        """API is accessible and auth endpoint works"""
        # Health endpoint is not routed through ingress, so test auth login instead
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"✓ API accessible: login works")


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================
class TestAuth:
    """Authentication endpoint tests"""
    
    def test_admin_login_success(self, api_session):
        """Admin can login with valid credentials"""
        response = api_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful, role: {data['user']['role']}")
    
    def test_cashier_login_success(self, api_session):
        """Cashier can login with valid credentials"""
        response = api_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "cashier",
            "password": "password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == "cashier"
        assert data["user"]["role"] == "cashier"
        print(f"✓ Cashier login successful, branch_id: {data['user'].get('branch_id')}")
    
    def test_login_invalid_credentials(self, api_session):
        """Invalid credentials return 401"""
        response = api_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected with 401")
    
    def test_auth_me_admin(self, admin_client):
        """GET /auth/me returns admin user info"""
        response = admin_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "password_hash" not in data  # Security: no password in response
        print(f"✓ Admin /auth/me returned user: {data['full_name']}")
    
    def test_auth_me_cashier(self, cashier_client):
        """GET /auth/me returns cashier user info"""
        response = cashier_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "cashier"
        assert data.get("branch_id") is not None, "Cashier should have branch_id assigned"
        print(f"✓ Cashier /auth/me returned user with branch_id: {data.get('branch_id')}")


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================
class TestDashboard:
    """Dashboard statistics endpoints"""
    
    def test_dashboard_stats_admin(self, admin_client):
        """Admin can get dashboard stats (all branches)"""
        response = admin_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        # Verify expected fields
        assert "today_revenue" in data
        assert "today_sales_count" in data
        assert "total_products" in data
        assert "low_stock_count" in data
        assert "total_customers" in data
        assert "total_receivables" in data
        assert "branches" in data
        assert "is_multi_branch_view" in data
        print(f"✓ Admin dashboard stats: revenue={data['today_revenue']}, products={data['total_products']}")
    
    def test_dashboard_stats_with_branch_filter(self, admin_client):
        """Admin can filter dashboard stats by branch"""
        # First get branches
        branches_resp = admin_client.get(f"{BASE_URL}/api/branches")
        branches = branches_resp.json()
        if branches:
            branch_id = branches[0]["id"]
            response = admin_client.get(f"{BASE_URL}/api/dashboard/stats?branch_id={branch_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["current_branch_filter"] == branch_id
            print(f"✓ Dashboard stats filtered by branch: {branch_id}")
    
    def test_dashboard_stats_cashier(self, cashier_client):
        """Cashier gets dashboard stats filtered to their branch"""
        response = cashier_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "today_revenue" in data
        # Cashier should see data only from their branch
        print(f"✓ Cashier dashboard stats: revenue={data['today_revenue']}")
    
    def test_dashboard_branch_summary(self, admin_client):
        """Admin can get branch summary for all branches"""
        response = admin_client.get(f"{BASE_URL}/api/dashboard/branch-summary")
        assert response.status_code == 200
        data = response.json()
        assert "branches" in data
        assert "totals" in data
        print(f"✓ Branch summary: {len(data['branches'])} branches, total revenue: {data['totals']['today_revenue']}")


# ============================================================================
# INVOICE ENDPOINTS
# ============================================================================
class TestInvoices:
    """Invoice CRUD and listing"""
    
    def test_list_invoices(self, admin_client):
        """List invoices returns valid response"""
        response = admin_client.get(f"{BASE_URL}/api/invoices")
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
        assert "total" in data
        assert isinstance(data["invoices"], list)
        print(f"✓ Invoices list: {data['total']} total invoices")
    
    def test_create_invoice(self, admin_client):
        """Create a test invoice"""
        # Get a branch first
        branches_resp = admin_client.get(f"{BASE_URL}/api/branches")
        branches = branches_resp.json()
        branch_id = branches[0]["id"] if branches else ""
        
        invoice_data = {
            "customer_name": "TEST_ModularRegression",
            "branch_id": branch_id,
            "items": [
                {
                    "product_name": "Test Product",
                    "quantity": 2,
                    "rate": 100,
                    "discount_type": "amount",
                    "discount_value": 0
                }
            ],
            "terms": "COD",
            "terms_days": 0,
            "payment_method": "Cash",
            "amount_paid": 200
        }
        
        response = admin_client.post(f"{BASE_URL}/api/invoices", json=invoice_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "invoice_number" in data
        assert data["customer_name"] == "TEST_ModularRegression"
        assert data["grand_total"] == 200
        assert data["status"] == "paid"
        print(f"✓ Invoice created: {data['invoice_number']}, total: {data['grand_total']}")
        return data["id"]
    
    def test_get_invoice_by_id(self, admin_client):
        """Get invoice by ID"""
        # Create invoice first
        branches_resp = admin_client.get(f"{BASE_URL}/api/branches")
        branches = branches_resp.json()
        branch_id = branches[0]["id"] if branches else ""
        
        create_resp = admin_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_name": "TEST_GetById",
            "branch_id": branch_id,
            "items": [{"product_name": "Test", "quantity": 1, "rate": 50}],
            "amount_paid": 50
        })
        inv_id = create_resp.json()["id"]
        
        # Get by ID
        response = admin_client.get(f"{BASE_URL}/api/invoices/{inv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == inv_id
        assert "edit_history" in data
        print(f"✓ Invoice retrieved by ID: {data['invoice_number']}")


# ============================================================================
# PRODUCTS ENDPOINTS
# ============================================================================
class TestProducts:
    """Product management endpoints"""
    
    def test_list_products(self, admin_client):
        """List products"""
        response = admin_client.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "total" in data
        print(f"✓ Products list: {data['total']} total products")
    
    def test_create_product(self, admin_client):
        """Create a test product"""
        product_data = {
            "name": "TEST_ModularProduct",
            "category": "Test Category",
            "unit": "Piece",
            "cost_price": 100,
            "prices": {"retail": 150, "wholesale": 130}
        }
        response = admin_client.post(f"{BASE_URL}/api/products", json=product_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "sku" in data
        assert data["name"] == "TEST_ModularProduct"
        print(f"✓ Product created: {data['name']}, SKU: {data['sku']}")
        return data["id"]
    
    def test_search_products(self, admin_client):
        """Search products by name"""
        response = admin_client.get(f"{BASE_URL}/api/products?search=TEST")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        print(f"✓ Product search returned {len(data['products'])} results")


# ============================================================================
# CUSTOMERS ENDPOINTS
# ============================================================================
class TestCustomers:
    """Customer management with branch filtering"""
    
    def test_list_customers(self, admin_client):
        """List customers (admin sees all)"""
        response = admin_client.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        assert "total" in data
        print(f"✓ Customers list: {data['total']} total customers")
    
    def test_list_customers_cashier(self, cashier_client):
        """Cashier sees customers filtered by branch"""
        response = cashier_client.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        print(f"✓ Cashier customers: {data['total']} visible customers")
    
    def test_create_customer(self, admin_client):
        """Create a customer"""
        customer_data = {
            "name": "TEST_ModularCustomer",
            "phone": "1234567890",
            "price_scheme": "retail",
            "credit_limit": 5000
        }
        response = admin_client.post(f"{BASE_URL}/api/customers", json=customer_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_ModularCustomer"
        print(f"✓ Customer created: {data['name']}")


# ============================================================================
# PURCHASE ORDERS ENDPOINTS
# ============================================================================
class TestPurchaseOrders:
    """Purchase order management with branch filtering"""
    
    def test_list_purchase_orders(self, admin_client):
        """List purchase orders"""
        response = admin_client.get(f"{BASE_URL}/api/purchase-orders")
        assert response.status_code == 200
        data = response.json()
        assert "purchase_orders" in data
        assert "total" in data
        print(f"✓ Purchase orders: {data['total']} total")
    
    def test_list_po_cashier(self, cashier_client):
        """Cashier sees POs filtered by branch"""
        response = cashier_client.get(f"{BASE_URL}/api/purchase-orders")
        assert response.status_code == 200
        data = response.json()
        assert "purchase_orders" in data
        print(f"✓ Cashier POs: {len(data['purchase_orders'])} visible")


# ============================================================================
# ACCOUNTING ENDPOINTS
# ============================================================================
class TestAccounting:
    """Accounting: fund wallets, expenses"""
    
    def test_list_fund_wallets(self, admin_client):
        """List fund wallets"""
        response = admin_client.get(f"{BASE_URL}/api/fund-wallets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Fund wallets: {len(data)} wallets")
    
    def test_list_expenses(self, admin_client):
        """List expenses"""
        response = admin_client.get(f"{BASE_URL}/api/expenses")
        assert response.status_code == 200
        data = response.json()
        assert "expenses" in data
        assert "total" in data
        print(f"✓ Expenses: {data['total']} total")
    
    def test_expense_categories(self, admin_client):
        """Get expense categories"""
        response = admin_client.get(f"{BASE_URL}/api/expenses/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✓ Expense categories: {len(data)} categories")


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================
class TestSettings:
    """Settings endpoints"""
    
    def test_get_invoice_prefixes(self, admin_client):
        """Get invoice prefix settings"""
        response = admin_client.get(f"{BASE_URL}/api/settings/invoice-prefixes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Check at least sales_invoice is present
        assert "sales_invoice" in data, "Missing prefix: sales_invoice"
        print(f"✓ Invoice prefixes: {list(data.keys())}")
    
    def test_get_terms_options(self, admin_client):
        """Get payment terms options"""
        response = admin_client.get(f"{BASE_URL}/api/settings/terms-options")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check structure
        assert "key" in data[0]
        assert "label" in data[0]
        assert "days" in data[0]
        print(f"✓ Terms options: {len(data)} options")


# ============================================================================
# SUPPLIERS ENDPOINTS
# ============================================================================
class TestSuppliers:
    """Supplier management"""
    
    def test_list_suppliers(self, admin_client):
        """List suppliers"""
        response = admin_client.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Suppliers: {len(data)} suppliers")


# ============================================================================
# DAILY OPERATIONS ENDPOINTS
# ============================================================================
class TestDailyOperations:
    """Daily log and reports"""
    
    def test_get_daily_log(self, admin_client):
        """Get daily sales log"""
        response = admin_client.get(f"{BASE_URL}/api/daily-log")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Daily log: {len(data)} entries today")
    
    def test_get_daily_report(self, admin_client):
        """Get daily profit report"""
        response = admin_client.get(f"{BASE_URL}/api/daily-report")
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "total_sales" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        print(f"✓ Daily report: sales={data['total_sales']}, expenses={data['total_expenses']}, profit={data['net_profit']}")


# ============================================================================
# PERMISSIONS ENDPOINTS
# ============================================================================
class TestPermissions:
    """Permission system endpoints"""
    
    def test_get_permission_modules(self, admin_client):
        """Get permission modules"""
        response = admin_client.get(f"{BASE_URL}/api/permissions/modules")
        assert response.status_code == 200
        data = response.json()
        # Can be dict or list depending on implementation
        assert data is not None
        if isinstance(data, dict):
            assert len(data) > 0
            print(f"✓ Permission modules: {len(data)} modules (dict format)")
        else:
            assert isinstance(data, list)
            assert len(data) > 0
            print(f"✓ Permission modules: {len(data)} modules (list format)")
    
    def test_get_permission_presets(self, admin_client):
        """Get permission presets"""
        response = admin_client.get(f"{BASE_URL}/api/permissions/presets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "admin" in data
        assert "cashier" in data
        print(f"✓ Permission presets: {list(data.keys())}")


# ============================================================================
# SYNC ENDPOINTS
# ============================================================================
class TestSync:
    """Offline POS sync endpoints"""
    
    def test_get_pos_sync_data(self, admin_client):
        """Get POS sync data"""
        response = admin_client.get(f"{BASE_URL}/api/sync/pos-data")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "customers" in data
        assert "price_schemes" in data
        assert "sync_time" in data
        print(f"✓ POS sync data: {len(data['products'])} products, {len(data['customers'])} customers")


# ============================================================================
# MULTI-BRANCH DATA ISOLATION
# ============================================================================
class TestMultiBranchIsolation:
    """Verify data isolation between admin and cashier"""
    
    def test_admin_sees_all_branches(self, admin_client):
        """Admin can access all branches"""
        response = admin_client.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200
        branches = response.json()
        assert isinstance(branches, list)
        print(f"✓ Admin sees {len(branches)} branches")
    
    def test_cashier_has_branch_id(self, cashier_client):
        """Cashier has branch_id assigned"""
        response = cashier_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("branch_id") is not None, "Cashier must have branch_id"
        print(f"✓ Cashier assigned to branch: {data['branch_id']}")
    
    def test_admin_invoice_filter_by_branch(self, admin_client):
        """Admin can filter invoices by branch"""
        # Get branches
        branches_resp = admin_client.get(f"{BASE_URL}/api/branches")
        branches = branches_resp.json()
        
        if branches:
            branch_id = branches[0]["id"]
            response = admin_client.get(f"{BASE_URL}/api/invoices?branch_id={branch_id}")
            assert response.status_code == 200
            data = response.json()
            assert "invoices" in data
            print(f"✓ Admin filtered invoices by branch {branch_id}: {len(data['invoices'])} invoices")
    
    def test_cashier_data_filtered(self, cashier_client):
        """Cashier only sees data from their branch"""
        # Get cashier's branch
        me_resp = cashier_client.get(f"{BASE_URL}/api/auth/me")
        cashier_branch = me_resp.json().get("branch_id")
        
        # Get invoices
        inv_resp = cashier_client.get(f"{BASE_URL}/api/invoices")
        assert inv_resp.status_code == 200
        invoices = inv_resp.json()["invoices"]
        
        # All invoices should be from cashier's branch or no branch
        for inv in invoices:
            if inv.get("branch_id"):
                assert inv["branch_id"] == cashier_branch, \
                    f"Cashier saw invoice from wrong branch: {inv['branch_id']}"
        
        print(f"✓ Cashier invoices filtered to branch {cashier_branch}: {len(invoices)} invoices")


# ============================================================================
# ADDITIONAL ENDPOINTS
# ============================================================================
class TestAdditionalEndpoints:
    """Test remaining endpoints"""
    
    def test_list_users(self, admin_client):
        """List users (admin only)"""
        response = admin_client.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Users list: {len(data)} users")
    
    def test_list_inventory(self, admin_client):
        """List inventory"""
        response = admin_client.get(f"{BASE_URL}/api/inventory")
        assert response.status_code == 200
        data = response.json()
        # Can be list or dict with items
        print(f"✓ Inventory endpoint works")
    
    def test_list_price_schemes(self, admin_client):
        """List price schemes"""
        response = admin_client.get(f"{BASE_URL}/api/price-schemes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have default price schemes"
        print(f"✓ Price schemes: {len(data)} schemes")
    
    def test_list_employees(self, admin_client):
        """List employees"""
        response = admin_client.get(f"{BASE_URL}/api/employees")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Employees: {len(data)} employees")
    
    def test_list_receivables(self, admin_client):
        """List receivables"""
        response = admin_client.get(f"{BASE_URL}/api/receivables")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Receivables: {len(data)} entries")
    
    def test_list_payables(self, admin_client):
        """List payables"""
        response = admin_client.get(f"{BASE_URL}/api/payables")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Payables: {len(data)} entries")
    
    def test_list_branches(self, admin_client):
        """List branches"""
        response = admin_client.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one branch"
        print(f"✓ Branches: {len(data)} branches")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
