#!/usr/bin/env python3
import requests
import sys
import json
from datetime import datetime

class AgriPOSBackendTester:
    def __init__(self, base_url="https://multibranch-pos-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.current_branch = None
        self.test_product_id = None
        self.test_customer_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, params=data)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login", "POST", "auth/login", 200,
            data={"username": "admin", "password": "admin123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   Token received for user: {response.get('user', {}).get('full_name', 'admin')}")
            return True
        return False

    def test_branches(self):
        """Test branches endpoint"""
        success, response = self.run_test(
            "List Branches", "GET", "branches", 200
        )
        if success and response:
            self.current_branch = response[0] if response else None
            print(f"   Found {len(response)} branches")
            if self.current_branch:
                print(f"   Using branch: {self.current_branch['name']} (ID: {self.current_branch['id']})")
            return True
        return False

    def test_inventory_endpoint(self):
        """Test simplified inventory endpoint"""
        success, response = self.run_test(
            "Inventory List (Simplified View)", "GET", "inventory", 200,
            data={"limit": 10}
        )
        if success:
            items = response.get('items', [])
            print(f"   Found {len(items)} inventory items")
            print(f"   Total count: {response.get('total', 0)}")
            if items:
                item = items[0]
                print(f"   Sample item: {item.get('name')} - SKU: {item.get('sku')}")
                print(f"   Stock: {item.get('total_stock', 0)} {item.get('unit', '')}")
                print(f"   Category: {item.get('category')}, Type: {item.get('product_type')}")
                self.test_product_id = item.get('id')
            return True
        return False

    def test_product_detail_endpoint(self):
        """Test comprehensive product detail endpoint"""
        if not self.test_product_id:
            print("⚠️  No test product available, creating one...")
            # Create a test product first
            success, response = self.run_test(
                "Create Test Product", "POST", "products", 201,
                data={
                    "sku": f"TEST-{datetime.now().strftime('%H%M%S')}",
                    "name": "Test Product for Detail",
                    "category": "Test Category",
                    "unit": "Piece",
                    "cost_price": 50.0,
                    "prices": {"retail": 75.0, "wholesale": 65.0}
                }
            )
            if success:
                self.test_product_id = response.get('id')
            else:
                return False

        success, response = self.run_test(
            "Product Detail", "GET", f"products/{self.test_product_id}/detail", 200
        )
        if success:
            product = response.get('product', {})
            inventory = response.get('inventory', {})
            cost = response.get('cost', {})
            repacks = response.get('repacks', [])
            vendors = response.get('vendors', [])
            
            print(f"   Product: {product.get('name')} - SKU: {product.get('sku')}")
            print(f"   Currency in prices: {product.get('prices', {})}")
            print(f"   Inventory - Total: {inventory.get('total', 0)}, Coming: {inventory.get('coming', 0)}, Reserved: {inventory.get('reserved', 0)}")
            print(f"   Cost - Moving Avg: {cost.get('moving_average', 0)}, Method: {cost.get('method', 'manual')}")
            print(f"   Repacks: {len(repacks)}, Vendors: {len(vendors)}")
            return True
        return False

    def test_product_movements(self):
        """Test product movement history"""
        if not self.test_product_id:
            return False
            
        success, response = self.run_test(
            "Product Movements", "GET", f"products/{self.test_product_id}/movements", 200,
            data={"limit": 10}
        )
        if success:
            movements = response.get('movements', [])
            print(f"   Found {len(movements)} movement records")
            print(f"   Total movements: {response.get('total', 0)}")
            return True
        return False

    def test_product_orders(self):
        """Test product order history"""
        if not self.test_product_id:
            return False
            
        success, response = self.run_test(
            "Product Order History", "GET", f"products/{self.test_product_id}/orders", 200,
            data={"limit": 10}
        )
        if success:
            orders = response.get('orders', [])
            print(f"   Found {len(orders)} order records")
            return True
        return False

    def test_product_vendors_crud(self):
        """Test product vendors CRUD operations"""
        if not self.test_product_id:
            return False

        # Add vendor
        vendor_data = {
            "vendor_name": "Test Vendor Co.",
            "vendor_contact": "09123456789",
            "last_price": 45.50,
            "is_preferred": True
        }
        success, response = self.run_test(
            "Add Product Vendor", "POST", f"products/{self.test_product_id}/vendors", 200,
            data=vendor_data
        )
        if not success:
            return False
        
        vendor_id = response.get('id')
        print(f"   Created vendor: {response.get('vendor_name')} with ID: {vendor_id}")

        # List vendors
        success, vendors = self.run_test(
            "List Product Vendors", "GET", f"products/{self.test_product_id}/vendors", 200
        )
        if success:
            print(f"   Found {len(vendors)} vendors")

        # Remove vendor
        if vendor_id:
            success, _ = self.run_test(
                "Remove Product Vendor", "DELETE", f"products/{self.test_product_id}/vendors/{vendor_id}", 200
            )
            if success:
                print(f"   Removed vendor {vendor_id}")

        return success

    def test_purchase_orders_crud(self):
        """Test Purchase Orders CRUD operations"""
        if not self.test_product_id or not self.current_branch:
            return False

        # Create PO
        po_data = {
            "vendor": "Test Supplier Ltd.",
            "branch_id": self.current_branch['id'],
            "items": [{
                "product_id": self.test_product_id,
                "product_name": "Test Product",
                "quantity": 10,
                "unit_price": 45.0
            }],
            "notes": "Test purchase order"
        }
        success, po_response = self.run_test(
            "Create Purchase Order", "POST", "purchase-orders", 200,
            data=po_data
        )
        if not success:
            return False
        
        po_id = po_response.get('id')
        print(f"   Created PO: {po_response.get('po_number')} with ID: {po_id}")
        print(f"   Subtotal: ₱{po_response.get('subtotal', 0)}")

        # List POs
        success, po_list = self.run_test(
            "List Purchase Orders", "GET", "purchase-orders", 200,
            data={"limit": 5}
        )
        if success:
            print(f"   Found {po_list.get('total', 0)} purchase orders")

        # Receive PO (updates inventory)
        if po_id:
            success, _ = self.run_test(
                "Receive Purchase Order", "POST", f"purchase-orders/{po_id}/receive", 200
            )
            if success:
                print(f"   Received PO {po_id}, inventory updated")

        return success

    def test_pos_sale_with_php_currency(self):
        """Test POS sale with PHP currency formatting"""
        if not self.test_product_id or not self.current_branch:
            return False

        # Create a customer first
        customer_data = {
            "name": "Test Customer",
            "phone": "09123456789",
            "price_scheme": "retail"
        }
        success, customer_response = self.run_test(
            "Create Test Customer", "POST", "customers", 200,
            data=customer_data
        )
        if success:
            self.test_customer_id = customer_response.get('id')
            print(f"   Created customer: {customer_response.get('name')}")

        # Create a sale
        sale_data = {
            "branch_id": self.current_branch['id'],
            "customer_id": self.test_customer_id,
            "customer_name": "Test Customer",
            "items": [{
                "product_id": self.test_product_id,
                "quantity": 2,
                "price": 75.0  # Retail price in PHP
            }],
            "payment_method": "Cash",
            "discount": 0
        }
        success, sale_response = self.run_test(
            "Create POS Sale", "POST", "sales", 200,
            data=sale_data
        )
        if success:
            print(f"   Sale Number: {sale_response.get('sale_number')}")
            print(f"   Total: ₱{sale_response.get('total', 0)} (PHP Currency)")
            print(f"   Status: {sale_response.get('status')}")
            return True
        return False

    def test_dashboard_with_php_currency(self):
        """Test dashboard stats showing PHP currency"""
        success, response = self.run_test(
            "Dashboard Stats (PHP Currency)", "GET", "dashboard/stats", 200,
            data={"branch_id": self.current_branch['id'] if self.current_branch else None}
        )
        if success:
            print(f"   Today's Revenue: ₱{response.get('today_revenue', 0)}")
            print(f"   Today's Sales Count: {response.get('today_sales_count', 0)}")
            print(f"   Today's Expenses: ₱{response.get('today_expenses', 0)}")
            print(f"   Total Products: {response.get('total_products', 0)}")
            print(f"   Low Stock Count: {response.get('low_stock_count', 0)}")
            print(f"   Total Receivables: ₱{response.get('total_receivables', 0)}")
            return True
        return False

    def test_price_schemes(self):
        """Test price schemes (for PHP pricing tiers)"""
        success, response = self.run_test(
            "List Price Schemes", "GET", "price-schemes", 200
        )
        if success:
            schemes = response
            print(f"   Found {len(schemes)} price schemes")
            for scheme in schemes:
                print(f"   - {scheme.get('name')} ({scheme.get('key')}): {scheme.get('description')}")
            return True
        return False

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting AgriPOS Backend Testing for Redesigned Product & Inventory Pages")
        print("=" * 80)

        if not self.test_login():
            print("❌ Login failed, stopping tests")
            return False

        # Core data setup
        self.test_branches()
        self.test_price_schemes()

        # Test redesigned inventory and product detail features
        print(f"\n📦 Testing Redesigned Inventory & Product Features")
        print("-" * 50)
        self.test_inventory_endpoint()
        self.test_product_detail_endpoint()
        self.test_product_movements()
        self.test_product_orders()
        self.test_product_vendors_crud()

        # Test new purchase orders functionality  
        print(f"\n🛒 Testing Purchase Orders & Receive Flow")
        print("-" * 50)
        self.test_purchase_orders_crud()

        # Test POS with PHP currency
        print(f"\n💰 Testing POS & Dashboard with PHP Currency (₱)")
        print("-" * 50)
        self.test_pos_sale_with_php_currency()
        self.test_dashboard_with_php_currency()

        # Print final results
        print(f"\n" + "=" * 80)
        print(f"📊 FINAL RESULTS:")
        print(f"   Tests Passed: {self.tests_passed}/{self.tests_run}")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("✅ Backend testing PASSED - AgriPOS APIs working correctly")
            return True
        else:
            print("❌ Backend testing FAILED - Multiple API issues found")
            return False

def main():
    tester = AgriPOSBackendTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())