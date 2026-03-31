"""
Test Customer Receivables Summary API - Iteration 149
Tests the new GET /api/customers/receivables-summary endpoint for the Payments page left sidebar
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestCustomerReceivablesSummary:
    """Tests for GET /api/customers/receivables-summary endpoint"""
    
    def test_receivables_summary_endpoint_exists(self, api_client):
        """Test that the receivables-summary endpoint exists and returns 200"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Receivables summary endpoint exists and returns 200")
    
    def test_receivables_summary_returns_list(self, api_client):
        """Test that endpoint returns a list of customers"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Endpoint returns list with {len(data)} customers")
    
    def test_receivables_summary_customer_fields(self, api_client):
        """Test that each customer has required fields: id, name, balance, overdue_balance, invoice_count"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            customer = data[0]
            required_fields = ['id', 'name', 'balance', 'overdue_balance', 'invoice_count']
            for field in required_fields:
                assert field in customer, f"Missing required field: {field}"
            
            # Validate field types
            assert isinstance(customer['id'], str), "id should be string"
            assert isinstance(customer['name'], str), "name should be string"
            assert isinstance(customer['balance'], (int, float)), "balance should be numeric"
            assert isinstance(customer['overdue_balance'], (int, float)), "overdue_balance should be numeric"
            assert isinstance(customer['invoice_count'], int), "invoice_count should be integer"
            
            print(f"✓ Customer fields validated: {list(customer.keys())}")
        else:
            print("⚠ No customers with balance found - skipping field validation")
    
    def test_receivables_summary_default_excludes_zero_balance(self, api_client):
        """Test that by default (include_zero=false), only customers with balance > 0 are returned"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        data = response.json()
        
        # All returned customers should have balance > 0
        for customer in data:
            assert customer['balance'] > 0, f"Customer {customer['name']} has balance {customer['balance']} but should be > 0"
        
        print(f"✓ Default query returns only customers with balance > 0 ({len(data)} customers)")
    
    def test_receivables_summary_include_zero_true(self, api_client):
        """Test that include_zero=true returns all customers including zero-balance ones"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary", params={"include_zero": "true"})
        assert response.status_code == 200
        data_with_zero = response.json()
        
        # Get count without zero balance
        response_default = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        data_default = response_default.json()
        
        # With include_zero=true should return >= customers than default
        assert len(data_with_zero) >= len(data_default), \
            f"include_zero=true should return >= customers. Got {len(data_with_zero)} vs {len(data_default)}"
        
        print(f"✓ include_zero=true returns {len(data_with_zero)} customers (vs {len(data_default)} with balance)")
    
    def test_receivables_summary_with_branch_filter(self, api_client):
        """Test that branch_id filter works"""
        # First get all customers to find a branch_id
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary", params={"include_zero": "true"})
        assert response.status_code == 200
        
        # Try with a branch filter - should not error
        response_branch = api_client.get(f"{BASE_URL}/api/customers/receivables-summary", params={"branch_id": "test_branch"})
        # Should return 200 even if no customers match
        assert response_branch.status_code == 200
        print(f"✓ Branch filter parameter accepted")
    
    def test_receivables_summary_has_balance_data(self, api_client):
        """Test that results contain balance data (frontend handles sorting)"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 1:
            balances = [c['balance'] for c in data]
            # Verify all balances are positive (since default excludes zero)
            assert all(b > 0 for b in balances), "All balances should be > 0"
            print(f"✓ Results contain {len(data)} customers with balances: {balances[:5]}...")
        else:
            print("⚠ Not enough customers to verify balance data")
    
    def test_receivables_summary_overdue_calculation(self, api_client):
        """Test that overdue_balance is calculated correctly (should be <= balance)"""
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        data = response.json()
        
        for customer in data:
            assert customer['overdue_balance'] <= customer['balance'], \
                f"Customer {customer['name']}: overdue_balance ({customer['overdue_balance']}) > balance ({customer['balance']})"
        
        print(f"✓ Overdue balance validation passed for all {len(data)} customers")


class TestCustomerReceivablesSummaryIntegration:
    """Integration tests with customer invoices"""
    
    def test_customer_invoices_endpoint_works(self, api_client):
        """Test that customer invoices endpoint works for customers from receivables summary"""
        # Get a customer with balance
        response = api_client.get(f"{BASE_URL}/api/customers/receivables-summary")
        assert response.status_code == 200
        customers = response.json()
        
        if len(customers) > 0:
            customer_id = customers[0]['id']
            inv_response = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices")
            assert inv_response.status_code == 200, f"Failed to get invoices: {inv_response.text}"
            invoices = inv_response.json()
            assert isinstance(invoices, list), "Invoices should be a list"
            print(f"✓ Customer {customers[0]['name']} has {len(invoices)} invoices")
        else:
            print("⚠ No customers with balance to test invoices endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
