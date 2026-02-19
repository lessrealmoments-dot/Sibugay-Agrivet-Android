import requests
import sys
import json
from datetime import datetime

class AgriPOSAPITester:
    def __init__(self, base_url="https://multibranch-pos-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user = None
        self.branch_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}: PASSED {details}")
        else:
            self.failed_tests.append({"test": test_name, "details": details})
            print(f"❌ {test_name}: FAILED - {details}")

    def make_request(self, method, endpoint, data=None, expected_status=200):
        """Make HTTP request with proper headers"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            
            success = response.status_code == expected_status
            result_data = {}
            
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    result_data = response.json()
                except:
                    pass
            
            return success, response.status_code, result_data
            
        except Exception as e:
            return False, 0, {"error": str(e)}

    def test_login(self):
        """Test login with admin/admin123"""
        print("\n🔐 Testing Authentication...")
        success, status, data = self.make_request('POST', 'auth/login', {
            "username": "admin",
            "password": "admin123"
        })
        
        if success and 'token' in data:
            self.token = data['token']
            self.user = data.get('user', {})
            self.log_result("Admin Login", True, f"Token obtained, Role: {self.user.get('role')}")
            return True
        else:
            self.log_result("Admin Login", False, f"Status: {status}, Data: {data}")
            return False

    def test_branches(self):
        """Test branch operations"""
        print("\n🏢 Testing Branches...")
        
        # Get branches
        success, status, data = self.make_request('GET', 'branches')
        if success and isinstance(data, list):
            if data:
                self.branch_id = data[0]['id']  # Use first branch for subsequent tests
                self.log_result("Get Branches", True, f"Found {len(data)} branches")
            else:
                self.log_result("Get Branches", False, "No branches found")
                return False
        else:
            self.log_result("Get Branches", False, f"Status: {status}")
            return False
        
        # Create new branch
        new_branch_data = {
            "name": f"Test Branch {datetime.now().strftime('%H%M%S')}",
            "address": "Test Address", 
            "phone": "1234567890"
        }
        success, status, data = self.make_request('POST', 'branches', new_branch_data, 200)  # Try with 200
        if success and 'id' in data:
            self.log_result("Create Branch", True, f"Created branch: {data.get('name')}")
        else:
            self.log_result("Create Branch", False, f"Status: {status}, Data: {data}")
        
        return True

    def test_products(self):
        """Test product operations including parent and repack"""
        print("\n📦 Testing Products...")
        
        # Create parent product
        parent_product = {
            "sku": "LAN-250G",
            "name": "Lannate 250g",
            "category": "Pesticides",
            "unit": "Box",
            "cost_price": 100,
            "prices": {"retail": 150, "wholesale": 130}
        }
        
        success, status, data = self.make_request('POST', 'products', parent_product, 200)  # Try with 200
        if success and 'id' in data:
            parent_id = data.get('id')
            self.log_result("Create Parent Product", True, f"SKU: {data.get('sku')}")
            
            # Generate repack
            repack_data = {
                "name": "R Lannate 250g",
                "unit": "Sachet",
                "units_per_parent": 10,
                "cost_price": 10,
                "prices": {"retail": 15, "wholesale": 13}
            }
            
            success, status, repack_result = self.make_request('POST', f'products/{parent_id}/generate-repack', repack_data, 200)
            if success and 'id' in repack_result:
                self.log_result("Generate Repack", True, f"Repack SKU: {repack_result.get('sku')}")
                return parent_id, repack_result.get('id')
            else:
                self.log_result("Generate Repack", False, f"Status: {status}, Data: {repack_result}")
        else:
            self.log_result("Create Parent Product", False, f"Status: {status}, Data: {data}")
        
        return None, None

    def test_inventory(self, parent_id, repack_id):
        """Test inventory operations"""
        print("\n📊 Testing Inventory...")
        
        if not parent_id or not self.branch_id:
            self.log_result("Inventory Setup", False, "Missing parent_id or branch_id")
            return False
        
        # Adjust parent stock
        adjust_data = {
            "product_id": parent_id,
            "branch_id": self.branch_id,
            "quantity": 10,
            "reason": "Initial stock"
        }
        
        success, status, data = self.make_request('POST', 'inventory/adjust', adjust_data)
        if success:
            self.log_result("Adjust Parent Stock", True, f"Added 10 units")
        else:
            self.log_result("Adjust Parent Stock", False, f"Status: {status}")
        
        # Adjust repack stock
        if repack_id:
            repack_adjust = {
                "product_id": repack_id,
                "branch_id": self.branch_id,
                "quantity": 100,
                "reason": "Initial repack stock"
            }
            
            success, status, data = self.make_request('POST', 'inventory/adjust', repack_adjust)
            if success:
                self.log_result("Adjust Repack Stock", True, f"Added 100 units")
            else:
                self.log_result("Adjust Repack Stock", False, f"Status: {status}")
        
        # Get inventory
        success, status, data = self.make_request('GET', f'inventory?branch_id={self.branch_id}')
        if success and 'items' in data:
            self.log_result("Get Inventory", True, f"Found {len(data['items'])} items")
        else:
            self.log_result("Get Inventory", False, f"Status: {status}")
        
        return True

    def test_customers(self):
        """Test customer operations"""
        print("\n👥 Testing Customers...")
        
        # Create customer
        customer_data = {
            "name": "Test Customer",
            "phone": "1234567890",
            "email": "test@example.com",
            "price_scheme": "retail"
        }
        
        success, status, data = self.make_request('POST', 'customers', customer_data, 200)  # Try with 200
        if success and 'id' in data:
            customer_id = data.get('id')
            self.log_result("Create Customer", True, f"Name: {data.get('name')}")
            return customer_id
        else:
            self.log_result("Create Customer", False, f"Status: {status}, Data: {data}")
            return None

    def test_pos_sale(self, repack_id, customer_id):
        """Test POS sale creation"""
        print("\n🛒 Testing POS Sale...")
        
        if not repack_id or not self.branch_id:
            self.log_result("POS Sale Setup", False, "Missing repack_id or branch_id")
            return False
        
        sale_data = {
            "branch_id": self.branch_id,
            "customer_id": customer_id,
            "customer_name": "Test Customer",
            "items": [
                {
                    "product_id": repack_id,
                    "quantity": 2,
                    "price": 15
                }
            ],
            "discount": 0,
            "payment_method": "Cash",
            "payment_details": {"tendered": 30, "change": 0}
        }
        
        success, status, data = self.make_request('POST', 'sales', sale_data, 200)  # Try with 200
        if success and 'id' in data:
            sale_id = data.get('id')
            self.log_result("Create POS Sale", True, f"Sale ID: {sale_id}, Total: {data.get('total')}")
            return sale_id
        else:
            self.log_result("Create POS Sale", False, f"Status: {status}, Data: {data}")
            return None

    def test_sales_history(self):
        """Test sales history retrieval"""
        print("\n📋 Testing Sales History...")
        
        success, status, data = self.make_request('GET', 'sales')
        if success and 'sales' in data:
            self.log_result("Get Sales History", True, f"Found {len(data['sales'])} sales")
        else:
            self.log_result("Get Sales History", False, f"Status: {status}")

    def test_accounting(self):
        """Test accounting operations"""
        print("\n💰 Testing Accounting...")
        
        # Create expense
        expense_data = {
            "branch_id": self.branch_id,
            "category": "Office Supplies",
            "description": "Test expense",
            "amount": 50
        }
        
        success, status, data = self.make_request('POST', 'expenses', expense_data, 201)
        if success:
            self.log_result("Create Expense", True, f"Amount: {data.get('amount')}")
        else:
            self.log_result("Create Expense", False, f"Status: {status}")

    def test_dashboard(self):
        """Test dashboard stats"""
        print("\n📊 Testing Dashboard...")
        
        success, status, data = self.make_request('GET', 'dashboard/stats')
        if success and isinstance(data, dict):
            self.log_result("Get Dashboard Stats", True, f"Today's revenue: {data.get('today_revenue', 0)}")
        else:
            self.log_result("Get Dashboard Stats", False, f"Status: {status}")

    def test_settings(self):
        """Test settings/users"""
        print("\n⚙️ Testing Settings...")
        
        success, status, data = self.make_request('GET', 'users')
        if success and isinstance(data, list):
            self.log_result("Get Users", True, f"Found {len(data)} users")
        else:
            self.log_result("Get Users", False, f"Status: {status}")

    def run_all_tests(self):
        """Run all API tests"""
        print("🧪 Starting AgriPOS API Testing...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test authentication first
        if not self.test_login():
            print("❌ Authentication failed - stopping tests")
            return False
        
        # Test other features
        self.test_branches()
        parent_id, repack_id = self.test_products()
        self.test_inventory(parent_id, repack_id)
        customer_id = self.test_customers()
        sale_id = self.test_pos_sale(repack_id, customer_id)
        self.test_sales_history()
        self.test_accounting()
        self.test_dashboard()
        self.test_settings()
        
        # Print final results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failed in self.failed_tests:
                print(f"  - {failed['test']}: {failed['details']}")
        
        return success_rate >= 80  # 80% success rate threshold

if __name__ == "__main__":
    tester = AgriPOSAPITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)