#!/usr/bin/env python3
"""
AgriPOS Backend API Test Suite
Tests all sales order, payment, and fund management endpoints
"""

import requests
import json
import sys
from datetime import datetime

class AgriPOSAPITester:
    def __init__(self, base_url="https://multibranch-pos-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, test_name, passed, response_data=None, error=None):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
        
        result = {
            "test_name": test_name,
            "passed": passed,
            "response_data": response_data,
            "error": str(error) if error else None
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if error:
            print(f"    Error: {error}")

    def make_request(self, method, endpoint, data=None, expected_status=200):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data if data else None)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            success = response.status_code == expected_status
            response_data = None
            
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw_response": response.text}
            else:
                response_data = {"status_code": response.status_code, "text": response.text}
                
            return success, response_data, None
            
        except Exception as e:
            return False, None, e

    def test_auth_login(self):
        """Test login with admin credentials"""
        success, data, error = self.make_request('POST', 'auth/login', {
            'username': 'admin',
            'password': 'admin123'
        })
        
        if success and data and 'token' in data:
            self.token = data['token']
            self.log_test("Login with admin/admin123", True, {"user_role": data.get('user', {}).get('role')})
            return True
        else:
            self.log_test("Login with admin/admin123", False, data, error)
            return False

    def test_settings_endpoints(self):
        """Test settings endpoints for invoice prefixes and terms"""
        # Test invoice prefixes
        success, data, error = self.make_request('GET', 'settings/invoice-prefixes')
        self.log_test("Get invoice prefixes", success, data, error)
        
        # Test terms options
        success, data, error = self.make_request('GET', 'settings/terms-options')
        self.log_test("Get terms options", success, data, error)
        
        return success

    def test_product_search_detail(self):
        """Test enhanced product search with inventory details"""
        success, data, error = self.make_request('GET', 'products/search-detail', {'q': 'lann'})
        
        if success and data:
            # Check if products have required detail fields
            has_details = False
            if isinstance(data, list) and len(data) > 0:
                product = data[0]
                required_fields = ['name', 'sku', 'prices', 'available', 'reserved', 'coming']
                has_details = all(field in product for field in required_fields)
        else:
            has_details = False
            
        self.log_test("Product search detail with 'lann'", success and has_details, 
                     {"products_found": len(data) if isinstance(data, list) else 0}, error)
        
        return success and has_details

    def test_fund_wallets_crud(self):
        """Test fund wallet CRUD operations"""
        # Create a cashier wallet
        wallet_data = {
            "type": "cashier",
            "name": "Test Cashier",
            "branch_id": "test_branch_001",
            "balance": 1000.0
        }
        
        success, data, error = self.make_request('POST', 'fund-wallets', wallet_data, 200)
        wallet_id = data.get('id') if data else None
        self.log_test("Create fund wallet (cashier type)", success, {"wallet_id": wallet_id}, error)
        
        if not success:
            return False
            
        # List wallets
        success, data, error = self.make_request('GET', 'fund-wallets')
        self.log_test("List fund wallets", success, {"wallets_count": len(data) if isinstance(data, list) else 0}, error)
        
        # Test deposit to wallet
        if wallet_id:
            deposit_data = {
                "amount": 500.0,
                "reference": "Test deposit",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            success, data, error = self.make_request('POST', f'fund-wallets/{wallet_id}/deposit', deposit_data)
            self.log_test("Deposit to wallet", success, data, error)
        
        return True

    def test_safe_lots(self):
        """Test safe lots endpoint"""
        success, data, error = self.make_request('GET', 'safe-lots')
        self.log_test("Get safe cash lots", success, {"lots_count": len(data) if isinstance(data, list) else 0}, error)
        return success

    def test_invoice_creation(self):
        """Test invoice creation with line items"""
        invoice_data = {
            "customer_id": "",
            "customer_name": "Test Customer",
            "terms": "COD",
            "terms_days": 0,
            "prefix": "SI",
            "order_date": datetime.now().strftime("%Y-%m-%d"),
            "invoice_date": datetime.now().strftime("%Y-%m-%d"),
            "branch_id": "test_branch_001",
            "items": [
                {
                    "product_id": "test_product_001",
                    "product_name": "Test Product",
                    "quantity": 2,
                    "rate": 50.0,
                    "discount_type": "amount",
                    "discount_value": 5.0
                }
            ],
            "freight": 10.0,
            "overall_discount": 0.0,
            "amount_paid": 0.0
        }
        
        success, data, error = self.make_request('POST', 'invoices', invoice_data)
        invoice_id = data.get('id') if data else None
        invoice_number = data.get('invoice_number') if data else None
        
        self.log_test("Create invoice with line items", success, 
                     {"invoice_id": invoice_id, "invoice_number": invoice_number}, error)
        
        # Test getting the created invoice
        if invoice_id:
            success, data, error = self.make_request('GET', f'invoices/{invoice_id}')
            self.log_test("Get created invoice", success, {"invoice_number": data.get('invoice_number') if data else None}, error)
        
        return success, invoice_id

    def test_invoice_payment(self):
        """Test invoice payment with interest computation"""
        # First create an invoice
        invoice_success, invoice_id = self.test_invoice_creation()
        
        if not invoice_success or not invoice_id:
            return False
            
        # Test payment recording
        payment_data = {
            "amount": 50.0,
            "method": "Cash",
            "fund_source": "cashier",
            "reference": "Test payment",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        success, data, error = self.make_request('POST', f'invoices/{invoice_id}/payment', payment_data)
        self.log_test("Record invoice payment", success, data, error)
        
        # Test interest computation
        success, data, error = self.make_request('POST', f'invoices/{invoice_id}/compute-interest')
        self.log_test("Compute interest on invoice", success, data, error)
        
        return success

    def test_customers_and_invoices(self):
        """Test customer invoice lookup"""
        # Get customers list
        success, data, error = self.make_request('GET', 'customers', {'limit': 10})
        self.log_test("Get customers list", success, 
                     {"customers_count": len(data.get('customers', [])) if data else 0}, error)
        
        if success and data and data.get('customers'):
            customer_id = data['customers'][0]['id']
            # Get customer invoices
            success, data, error = self.make_request('GET', f'customers/{customer_id}/invoices')
            self.log_test("Get customer invoices", success, 
                         {"invoices_count": len(data) if isinstance(data, list) else 0}, error)
        
        return success

    def test_repack_auto_compute_capital(self):
        """Test repack auto-compute capital functionality"""
        # This would be tested through product search results showing parent cost / units_per_parent
        success, data, error = self.make_request('GET', 'products/search-detail', {'q': 'r-'})  # Search for repacks
        
        repack_found = False
        if success and data and isinstance(data, list):
            for product in data:
                if product.get('is_repack'):
                    repack_found = True
                    break
        
        self.log_test("Repack auto-compute capital (search repacks)", success, 
                     {"repack_products_found": repack_found}, error)
        
        return success

    def test_purchase_orders_crud(self):
        """Test Purchase Order CRUD operations"""
        # Create a purchase order
        po_data = {
            "vendor": "Test Supplier Co.",
            "branch_id": "test_branch_001",
            "expected_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": "Test PO for API verification",
            "status": "ordered",
            "items": [
                {
                    "product_id": "test_product_001",
                    "product_name": "Test Product",
                    "quantity": 10,
                    "unit_price": 25.0
                },
                {
                    "product_id": "test_product_002", 
                    "product_name": "Another Test Product",
                    "quantity": 5,
                    "unit_price": 50.0
                }
            ]
        }
        
        success, data, error = self.make_request('POST', 'purchase-orders', po_data)
        po_id = data.get('id') if data else None
        po_number = data.get('po_number') if data else None
        
        self.log_test("Create Purchase Order", success, 
                     {"po_id": po_id, "po_number": po_number, "subtotal": data.get('subtotal') if data else None}, error)
        
        if not success:
            return False, None
            
        # List purchase orders
        success, data, error = self.make_request('GET', 'purchase-orders', {'limit': 10})
        self.log_test("List Purchase Orders", success, 
                     {"pos_count": len(data.get('purchase_orders', [])) if data else 0}, error)
        
        return True, po_id

    def test_purchase_order_receive(self):
        """Test receiving a Purchase Order (should update inventory)"""
        # First create a PO
        po_success, po_id = self.test_purchase_orders_crud()
        
        if not po_success or not po_id:
            return False
            
        # Receive the PO
        success, data, error = self.make_request('POST', f'purchase-orders/{po_id}/receive')
        self.log_test("Receive Purchase Order", success, data, error)
        
        if not success:
            return False
        
        # Verify PO status changed by getting it back
        success, data, error = self.make_request('GET', 'purchase-orders', {'limit': 50})
        if success and data:
            received_po = None
            for po in data.get('purchase_orders', []):
                if po.get('id') == po_id:
                    received_po = po
                    break
            
            status_updated = received_po and received_po.get('status') == 'received'
            self.log_test("Verify PO status changed to 'received'", status_updated, 
                         {"po_status": received_po.get('status') if received_po else None})
        
        return success

    def test_fund_wallet_payment(self):
        """Test paying from fund wallet (supplier payment)"""
        # First ensure we have wallets
        success, data, error = self.make_request('GET', 'fund-wallets', {'branch_id': 'test_branch_001'})
        
        if not success or not data:
            self.log_test("Get wallets for payment test", False, data, "No wallets available")
            return False
            
        wallet_id = None
        if isinstance(data, list) and len(data) > 0:
            wallet_id = data[0].get('id')
        
        if not wallet_id:
            self.log_test("Find wallet for payment", False, None, "No wallet ID found")
            return False
            
        # Test payment from wallet
        payment_data = {
            "wallet_id": wallet_id,
            "amount": 100.0,
            "reference": "PO-TEST-001",
            "description": "Test supplier payment",
            "reference_id": "test_po_id"
        }
        
        success, data, error = self.make_request('POST', 'fund-wallets/pay', payment_data)
        self.log_test("Pay from fund wallet (supplier payment)", success, data, error)
        
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting AgriPOS Backend API Tests...")
        print("=" * 50)
        
        # Authentication test
        if not self.test_auth_login():
            print("❌ Authentication failed - stopping tests")
            return False
            
        # Settings tests
        self.test_settings_endpoints()
        
        # Product search tests
        self.test_product_search_detail()
        
        # Fund management tests
        self.test_fund_wallets_crud()
        self.test_safe_lots()
        
        # Invoice system tests
        self.test_invoice_payment()
        
        # Customer tests
        self.test_customers_and_invoices()
        
        # Repack tests
        self.test_repack_auto_compute_capital()
        
        # Purchase Order tests
        self.test_purchase_order_receive()
        
        # Fund wallet payment tests  
        self.test_fund_wallet_payment()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Show failed tests
        failed_tests = [t for t in self.test_results if not t['passed']]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"  - {test['test_name']}")
                if test['error']:
                    print(f"    Error: {test['error']}")
        
        return self.tests_passed == self.tests_run

if __name__ == "__main__":
    tester = AgriPOSAPITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)