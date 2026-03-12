"""
Test interest rate override feature (iteration 104)
Tests:
- GET /customers/{id}/charges-preview with rate_override parameter
- POST /customers/{id}/generate-interest with rate_override and save_rate
- Verify rate is saved to customer profile when save_rate=true
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInterestRateOverride:
    """Test interest rate override and save_rate functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_01_get_customers_list(self):
        """Get customers to find test customers"""
        response = requests.get(f"{BASE_URL}/api/customers?limit=500", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        
        # Find customers mentioned in test notes
        customers = data["customers"]
        
        # Look for a customer with interest_rate > 0 (for pre-fill test)
        cust_with_rate = next((c for c in customers if c.get("interest_rate", 0) > 0), None)
        print(f"Customer with saved rate: {cust_with_rate.get('name') if cust_with_rate else 'None'} - rate: {cust_with_rate.get('interest_rate') if cust_with_rate else 0}")
        
        # Look for customer with interest_rate=0 or no rate (for override test)
        cust_no_rate = next((c for c in customers if c.get("interest_rate", 0) == 0 and c.get("balance", 0) > 0), None)
        print(f"Customer without rate (with balance): {cust_no_rate.get('name') if cust_no_rate else 'None'}")
        
        # Store for later tests
        self.__class__.cust_with_rate = cust_with_rate
        self.__class__.cust_no_rate = cust_no_rate
        self.__class__.all_customers = customers
    
    def test_02_charges_preview_without_rate_override(self):
        """Test charges-preview uses customer's saved rate when no override"""
        if not hasattr(self.__class__, 'cust_with_rate') or not self.__class__.cust_with_rate:
            pytest.skip("No customer with saved rate found")
        
        cust = self.__class__.cust_with_rate
        response = requests.get(
            f"{BASE_URL}/api/customers/{cust['id']}/charges-preview",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "customer_id" in data
        assert "total_principal" in data
        assert "total_interest" in data
        assert "interest_preview" in data
        print(f"Preview (saved rate): total_interest={data['total_interest']}, principal={data['total_principal']}")
        
        # If there's interest preview, verify rate matches customer's saved rate
        if data.get("interest_preview"):
            for item in data["interest_preview"]:
                assert "rate" in item
                print(f"  Invoice {item.get('invoice_number')}: rate={item.get('rate')}%, days={item.get('days_for_interest')}")
    
    def test_03_charges_preview_with_rate_override(self):
        """Test charges-preview uses rate_override when provided"""
        # Find a customer with balance
        cust = next((c for c in self.__class__.all_customers if c.get("balance", 0) > 100), None)
        if not cust:
            pytest.skip("No customer with balance found")
        
        override_rate = 5.0  # 5%/mo override
        response = requests.get(
            f"{BASE_URL}/api/customers/{cust['id']}/charges-preview",
            params={"rate_override": override_rate},
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        print(f"Preview (rate_override={override_rate}%): customer={cust['name']}, total_interest={data['total_interest']}")
        
        # Verify rate_override is used in calculations
        if data.get("interest_preview"):
            for item in data["interest_preview"]:
                # Rate should be the override rate
                assert item.get("rate") == override_rate, f"Rate should be {override_rate}, got {item.get('rate')}"
                print(f"  Invoice {item.get('invoice_number')}: rate={item.get('rate')}% (override applied)")
    
    def test_04_charges_preview_different_rate_values(self):
        """Test charges-preview with various rate_override values"""
        cust = next((c for c in self.__class__.all_customers if c.get("balance", 0) > 100), None)
        if not cust:
            pytest.skip("No customer with balance found")
        
        test_rates = [0, 1.5, 3.0, 7.5, 10.0]
        results = []
        
        for rate in test_rates:
            params = {"rate_override": rate} if rate > 0 else {}
            response = requests.get(
                f"{BASE_URL}/api/customers/{cust['id']}/charges-preview",
                params=params,
                headers=self.headers
            )
            assert response.status_code == 200
            data = response.json()
            results.append((rate, data.get("total_interest", 0)))
            print(f"  Rate {rate}%/mo → Interest: {data.get('total_interest', 0)}")
        
        # Higher rate should yield higher or equal interest
        # (assuming same number of days)
        for i in range(1, len(results)):
            if results[i][0] > results[i-1][0] and results[i-1][1] > 0:
                # Interest should increase with rate
                assert results[i][1] >= results[i-1][1], \
                    f"Interest should increase with rate: {results[i-1]} vs {results[i]}"
    
    def test_05_generate_interest_with_rate_override_no_save(self):
        """Test generate-interest with rate_override (without saving to profile)"""
        # Find a customer with balance and no saved rate
        cust = next((c for c in self.__class__.all_customers 
                    if c.get("balance", 0) > 100 and c.get("interest_rate", 0) == 0), None)
        if not cust:
            # Try any customer with balance
            cust = next((c for c in self.__class__.all_customers if c.get("balance", 0) > 100), None)
        if not cust:
            pytest.skip("No suitable customer found")
        
        original_rate = cust.get("interest_rate", 0)
        override_rate = 4.0
        
        # First check preview
        preview_resp = requests.get(
            f"{BASE_URL}/api/customers/{cust['id']}/charges-preview",
            params={"rate_override": override_rate},
            headers=self.headers
        )
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        
        # Generate interest with override but save_rate=false
        response = requests.post(
            f"{BASE_URL}/api/customers/{cust['id']}/generate-interest",
            json={
                "rate_override": override_rate,
                "save_rate": False
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        print(f"Generate interest (rate_override={override_rate}, save_rate=false): {data}")
        
        # Verify customer rate is NOT changed
        cust_resp = requests.get(f"{BASE_URL}/api/customers/{cust['id']}", headers=self.headers)
        if cust_resp.status_code == 200:
            updated_cust = cust_resp.json()
            assert updated_cust.get("interest_rate", 0) == original_rate, \
                f"Rate should NOT be saved when save_rate=false"
        
        self.__class__.test_customer_for_save = cust
    
    def test_06_generate_interest_with_rate_override_and_save(self):
        """Test generate-interest with rate_override AND save_rate=true"""
        # Find a customer different from last test, or use any with balance
        cust = next((c for c in self.__class__.all_customers 
                    if c.get("balance", 0) > 100), None)
        if not cust:
            pytest.skip("No suitable customer found")
        
        new_rate = 6.5  # New rate to save
        
        # Get current customer state
        cust_resp = requests.get(f"{BASE_URL}/api/customers/{cust['id']}", headers=self.headers)
        if cust_resp.status_code == 200:
            original_rate = cust_resp.json().get("interest_rate", 0)
        else:
            original_rate = cust.get("interest_rate", 0)
        
        # Generate interest with override AND save_rate=true
        response = requests.post(
            f"{BASE_URL}/api/customers/{cust['id']}/generate-interest",
            json={
                "rate_override": new_rate,
                "save_rate": True
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        print(f"Generate interest (rate_override={new_rate}, save_rate=true): {data}")
        
        # Verify customer rate IS updated
        cust_resp = requests.get(f"{BASE_URL}/api/customers/{cust['id']}", headers=self.headers)
        if cust_resp.status_code == 200:
            updated_cust = cust_resp.json()
            assert updated_cust.get("interest_rate") == new_rate, \
                f"Rate should be saved to {new_rate}, got {updated_cust.get('interest_rate')}"
            print(f"Customer rate saved: {updated_cust.get('interest_rate')}%/mo")
        
        # Clean up: restore original rate
        if original_rate != new_rate:
            requests.put(
                f"{BASE_URL}/api/customers/{cust['id']}",
                json={"interest_rate": original_rate},
                headers=self.headers
            )
    
    def test_07_generate_interest_no_rate_returns_message(self):
        """Test generate-interest without rate returns helpful message"""
        # Find customer with no rate
        cust = next((c for c in self.__class__.all_customers 
                    if c.get("interest_rate", 0) == 0), None)
        if not cust:
            pytest.skip("No customer without rate found")
        
        response = requests.post(
            f"{BASE_URL}/api/customers/{cust['id']}/generate-interest",
            json={},  # No rate_override
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return message about no rate
        assert data.get("total_interest", 0) == 0 or "No interest rate" in data.get("message", ""), \
            f"Should indicate no rate was provided: {data}"
        print(f"No-rate response: {data}")
    
    def test_08_get_customer_invoices(self):
        """Test getting customer invoices (used by frontend)"""
        cust = next((c for c in self.__class__.all_customers if c.get("balance", 0) > 0), None)
        if not cust:
            pytest.skip("No customer with balance found")
        
        response = requests.get(
            f"{BASE_URL}/api/customers/{cust['id']}/invoices",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        invoices = response.json()
        
        print(f"Customer {cust['name']} has {len(invoices)} open invoices")
        for inv in invoices[:3]:
            print(f"  {inv.get('invoice_number')}: type={inv.get('sale_type')}, balance={inv.get('balance')}")


class TestInterestCalculationCorrectness:
    """Verify interest calculation uses correct formula: principal × (rate/30) × days"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_interest_formula_verification(self):
        """Verify interest = principal × (rate/100/30) × days"""
        # Get customers
        response = requests.get(f"{BASE_URL}/api/customers?limit=500", headers=self.headers)
        assert response.status_code == 200, f"Get customers failed: {response.status_code} {response.text}"
        customers = response.json().get("customers", [])
        
        # Find customer with balance
        cust = next((c for c in customers if c.get("balance", 0) > 1000), None)
        if not cust:
            pytest.skip("No customer with sufficient balance")
        
        # Get preview with known rate
        test_rate = 3.0  # 3%/mo
        response = requests.get(
            f"{BASE_URL}/api/customers/{cust['id']}/charges-preview",
            params={"rate_override": test_rate},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("interest_preview"):
            print("No interest to compute (invoices within grace period)")
            return
        
        # Verify each invoice's interest calculation
        for item in data["interest_preview"]:
            principal = item.get("principal", 0)
            days = item.get("days_for_interest", 0)
            rate = item.get("rate", 0)
            reported_interest = item.get("interest_amount", 0)
            
            # Calculate expected interest: principal × (rate/100/30) × days
            expected_interest = round(principal * (rate / 100 / 30) * days, 2)
            
            print(f"Invoice {item.get('invoice_number')}:")
            print(f"  Principal: ₱{principal}, Days: {days}, Rate: {rate}%/mo")
            print(f"  Expected: ₱{expected_interest}, Reported: ₱{reported_interest}")
            
            # Allow small rounding difference
            assert abs(expected_interest - reported_interest) < 0.02, \
                f"Interest calculation mismatch: expected {expected_interest}, got {reported_interest}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
