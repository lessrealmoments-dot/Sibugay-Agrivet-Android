import requests
import sys
import json
from datetime import datetime

class AgriPOSAPITester:
    def __init__(self, base_url="https://multibranch-pos-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.branch_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

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
                response = requests.get(url, headers=req_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    resp_data = response.json() if response.content else {}
                    self.results.append({"test": name, "status": "PASSED", "response": resp_data})
                    return success, resp_data
                except:
                    self.results.append({"test": name, "status": "PASSED", "response": {}})
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json() if response.content else {"error": response.text}
                except:
                    error_data = {"error": response.text}
                print(f"   Response: {error_data}")
                self.results.append({"test": name, "status": "FAILED", "error": error_data})
                return False, error_data

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.results.append({"test": name, "status": "ERROR", "error": str(e)})
            return False, {"error": str(e)}

    def test_login(self):
        """Test admin login and store token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": "admin", "password": "admin123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            print(f"   Logged in as: {response['user'].get('full_name', 'admin')}")
            return True
        return False

    def test_get_branches(self):
        """Get branches and store one for testing"""
        success, response = self.run_test(
            "Get Branches",
            "GET", 
            "branches",
            200
        )
        if success and response:
            self.branch_id = response[0]['id']
            print(f"   Using branch: {response[0]['name']}")
            return True
        return False

    def test_sync_pos_data(self):
        """Test the new /api/sync/pos-data endpoint"""
        success, response = self.run_test(
            "Sync POS Data Endpoint",
            "GET",
            "sync/pos-data", 
            200
        )
        if success:
            # Verify response structure
            required_keys = ['products', 'customers', 'price_schemes', 'branches', 'timestamp']
            missing = [key for key in required_keys if key not in response]
            if missing:
                print(f"   ⚠️  Missing keys in response: {missing}")
                return False
            
            print(f"   Products: {len(response['products'])}")
            print(f"   Customers: {len(response['customers'])}")
            print(f"   Price schemes: {len(response['price_schemes'])}")
            print(f"   Branches: {len(response['branches'])}")
            print(f"   Timestamp: {response['timestamp']}")
            return True
        return False

    def test_sync_offline_sales(self):
        """Test the new /api/sales/sync endpoint with sample offline sales"""
        # Create sample offline sales data
        sample_sales = [
            {
                "id": f"offline-{datetime.now().strftime('%Y%m%d%H%M%S')}-001",
                "sale_number": f"SL-{datetime.now().strftime('%Y%m%d')}-OFFLINE1",
                "branch_id": self.branch_id,
                "customer_id": None,
                "customer_name": "Walk-in",
                "items": [
                    {
                        "product_id": "sample-product-id",
                        "product_name": "Test Offline Product",
                        "sku": "TEST-001",
                        "quantity": 2,
                        "price": 15.0,
                        "total": 30.0,
                        "is_repack": False
                    }
                ],
                "subtotal": 30.0,
                "discount": 0.0,
                "total": 30.0,
                "payment_method": "Cash",
                "payment_details": {"tendered": 30.0, "change": 0.0},
                "cashier_id": self.user_id,
                "cashier_name": "Admin",
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }
        ]

        success, response = self.run_test(
            "Sync Offline Sales",
            "POST",
            "sales/sync",
            200,
            data={"sales": sample_sales}
        )
        
        if success:
            # Verify response structure
            if 'results' not in response or 'synced' not in response:
                print("   ⚠️  Invalid sync response structure")
                return False
            
            print(f"   Results: {len(response['results'])}")
            print(f"   Synced: {response['synced']}")
            print(f"   Total: {response.get('total', 0)}")
            
            # Check individual results
            for result in response['results']:
                print(f"   Sale {result['id']}: {result['status']}")
            
            return True
        return False

    def test_duplicate_sale_detection(self):
        """Test duplicate detection by sending same sale twice"""
        # Use same sale ID as previous test to check duplicate detection
        duplicate_sale = {
            "id": f"offline-{datetime.now().strftime('%Y%m%d%H%M%S')}-DUPLICATE",
            "sale_number": f"SL-{datetime.now().strftime('%Y%m%d')}-DUP",
            "branch_id": self.branch_id,
            "customer_name": "Walk-in",
            "items": [{"product_id": "test", "quantity": 1, "price": 10, "total": 10}],
            "subtotal": 10.0, "total": 10.0,
            "payment_method": "Cash", "cashier_id": self.user_id,
            "status": "completed", "created_at": datetime.now().isoformat()
        }

        # Send first time
        success1, _ = self.run_test(
            "Sync Sale (First Time)",
            "POST", "sales/sync", 200,
            data={"sales": [duplicate_sale]}
        )

        # Send second time (should detect duplicate)
        success2, response = self.run_test(
            "Sync Sale (Duplicate Check)",
            "POST", "sales/sync", 200,
            data={"sales": [duplicate_sale]}
        )

        if success1 and success2:
            # Check if duplicate was detected
            if response['results'] and response['results'][0]['status'] == 'duplicate':
                print("   ✅ Duplicate detection working correctly")
                return True
            else:
                print(f"   ⚠️  Expected duplicate, got: {response['results'][0]['status']}")
        
        return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("=" * 60)
        print("🧪 AgriPOS Backend API Tests - PWA + Offline Features")
        print("=" * 60)
        
        # Login first
        if not self.test_login():
            print("❌ Login failed - cannot continue with other tests")
            return False
        
        # Get branches
        if not self.test_get_branches():
            print("❌ Could not get branches - using None")
        
        # Test new sync endpoints
        self.test_sync_pos_data()
        self.test_sync_offline_sales() 
        self.test_duplicate_sale_detection()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        print("=" * 60)
        
        # Print detailed results
        for result in self.results:
            status_emoji = "✅" if result["status"] == "PASSED" else "❌"
            print(f"{status_emoji} {result['test']}: {result['status']}")
            if result["status"] != "PASSED":
                print(f"   Error: {result.get('error', 'Unknown error')}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = AgriPOSAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())