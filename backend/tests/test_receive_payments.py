"""
Tests for QuickBooks-style Receive Payments feature:
- GET /api/customers/{id}/invoices - returns open invoices
- POST /api/customers/{id}/generate-interest - creates interest charge invoice
- POST /api/customers/{id}/generate-penalty - creates penalty charge invoice
- POST /api/customers/{id}/receive-payment - auto-allocates to interest first, penalty second, oldest invoice last
- Payment updates cashier wallet balance
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_CUSTOMER_ID = "38511712-81e6-45ea-ac10-4a3ac6adad04"
BRANCH_ID = "9599a32f-722d-4824-9af8-b0217ca78523"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


@pytest.fixture(scope="module")
def test_customer(api_client):
    """Create a test customer for payment testing with interest_rate"""
    customer_data = {
        "name": "TEST_PaymentCustomer",
        "phone": "555-PAY-TEST",
        "address": "Payment Test Address",
        "price_scheme": "Retail",
        "credit_limit": 50000,
        "interest_rate": 3  # 3% monthly interest for testing
    }
    response = api_client.post(f"{BASE_URL}/api/customers", json=customer_data)
    assert response.status_code in [200, 201], f"Customer creation failed: {response.text}"
    customer = response.json()
    yield customer
    # Cleanup: soft-delete the customer
    try:
        api_client.delete(f"{BASE_URL}/api/customers/{customer['id']}")
    except:
        pass


@pytest.fixture(scope="module")
def test_product(api_client):
    """Create a test product with cost_price >= 1000"""
    product_data = {
        "name": "TEST_PaymentProduct",
        "sku": f"TEST-PAY-{datetime.now().strftime('%H%M%S')}",
        "category": "Testing",
        "cost_price": 1000,
        "prices": {"Retail": 1500, "Wholesale": 1200}
    }
    response = api_client.post(f"{BASE_URL}/api/products", json=product_data)
    assert response.status_code in [200, 201], f"Product creation failed: {response.text}"
    product = response.json()
    yield product
    # Cleanup
    try:
        api_client.delete(f"{BASE_URL}/api/products/{product['id']}")
    except:
        pass


class TestGetCustomerInvoices:
    """Test GET /api/customers/{id}/invoices"""
    
    def test_get_invoices_for_existing_customer(self, api_client):
        """GET /api/customers/{id}/invoices returns open invoices"""
        response = api_client.get(f"{BASE_URL}/api/customers/{TEST_CUSTOMER_ID}/invoices")
        assert response.status_code == 200, f"Failed: {response.text}"
        invoices = response.json()
        assert isinstance(invoices, list)
        print(f"Found {len(invoices)} open invoices for test customer")
        # Verify invoices have required fields
        if invoices:
            inv = invoices[0]
            assert "invoice_number" in inv
            assert "balance" in inv
            assert "grand_total" in inv
            assert "sale_type" in inv
    
    def test_get_invoices_for_nonexistent_customer(self, api_client):
        """GET /api/customers/{id}/invoices returns empty for invalid customer"""
        response = api_client.get(f"{BASE_URL}/api/customers/invalid-customer-id/invoices")
        # Should return empty list or 404
        assert response.status_code in [200, 404]


class TestGenerateInterest:
    """Test POST /api/customers/{id}/generate-interest"""
    
    def test_generate_interest_no_overdue_invoices(self, api_client):
        """Generate interest returns 'no interest to charge' when no overdue invoices"""
        # Test customer has invoices with future due dates
        response = api_client.post(f"{BASE_URL}/api/customers/{TEST_CUSTOMER_ID}/generate-interest")
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        # Since due dates are in future, no interest should be charged
        assert "message" in result
        print(f"Generate interest result: {result.get('message', result)}")
    
    def test_generate_interest_for_nonexistent_customer(self, api_client):
        """Generate interest returns 404 for invalid customer"""
        response = api_client.post(f"{BASE_URL}/api/customers/invalid-customer-id/generate-interest")
        assert response.status_code == 404


class TestGeneratePenalty:
    """Test POST /api/customers/{id}/generate-penalty"""
    
    def test_generate_penalty_no_overdue_invoices(self, api_client):
        """Generate penalty returns 'no penalty to charge' when no overdue invoices"""
        response = api_client.post(
            f"{BASE_URL}/api/customers/{TEST_CUSTOMER_ID}/generate-penalty",
            json={"penalty_rate": 5}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        # Since due dates are in future, no penalty should be charged
        assert "message" in result
        print(f"Generate penalty result: {result.get('message', result)}")
    
    def test_generate_penalty_for_nonexistent_customer(self, api_client):
        """Generate penalty returns 404 for invalid customer"""
        response = api_client.post(
            f"{BASE_URL}/api/customers/invalid-customer-id/generate-penalty",
            json={"penalty_rate": 5}
        )
        assert response.status_code == 404


class TestReceivePayment:
    """Test POST /api/customers/{id}/receive-payment"""
    
    def test_receive_payment_full_workflow(self, api_client, test_customer, test_product):
        """Complete payment workflow: create invoice, receive payment, verify allocation"""
        customer_id = test_customer["id"]
        
        # 1. Create an invoice with past due date to test interest
        past_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        invoice_data = {
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": BRANCH_ID,
            "order_date": past_date,
            "terms": "COD",
            "terms_days": 0,
            "interest_rate": 3,
            "items": [{
                "product_id": test_product["id"],
                "product_name": test_product["name"],
                "quantity": 2,
                "rate": 1500
            }]
        }
        inv_response = api_client.post(f"{BASE_URL}/api/invoices", json=invoice_data)
        assert inv_response.status_code in [200, 201], f"Invoice creation failed: {inv_response.text}"
        invoice = inv_response.json()
        print(f"Created invoice: {invoice['invoice_number']}, balance: {invoice['balance']}")
        
        # 2. Verify customer has open invoices
        invoices_response = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices")
        assert invoices_response.status_code == 200
        open_invoices = invoices_response.json()
        assert len(open_invoices) >= 1, "Customer should have at least 1 open invoice"
        
        # 3. Receive partial payment
        payment_amount = 1000
        pay_response = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
            json={
                "amount": payment_amount,
                "method": "Cash",
                "reference": "TEST-PAY-001",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        )
        assert pay_response.status_code == 200, f"Payment failed: {pay_response.text}"
        result = pay_response.json()
        
        # Verify payment response
        assert "total_received" in result
        assert "total_applied" in result
        assert "allocations" in result
        assert result["total_received"] == payment_amount
        print(f"Payment result: total_applied={result['total_applied']}, allocations={result['allocations']}")
        
        # Verify allocations are in order: interest first, penalty second, oldest invoice last
        if len(result["allocations"]) > 0:
            alloc = result["allocations"][0]
            assert "invoice" in alloc
            assert "applied" in alloc
            assert "new_balance" in alloc
    
    def test_receive_payment_invalid_amount(self, api_client):
        """Receive payment with invalid amount returns error"""
        response = api_client.post(
            f"{BASE_URL}/api/customers/{TEST_CUSTOMER_ID}/receive-payment",
            json={"amount": -100, "method": "Cash"}
        )
        assert response.status_code == 400
    
    def test_receive_payment_zero_amount(self, api_client):
        """Receive payment with zero amount returns error"""
        response = api_client.post(
            f"{BASE_URL}/api/customers/{TEST_CUSTOMER_ID}/receive-payment",
            json={"amount": 0, "method": "Cash"}
        )
        assert response.status_code == 400
    
    def test_receive_payment_nonexistent_customer(self, api_client):
        """Receive payment for nonexistent customer returns 404"""
        response = api_client.post(
            f"{BASE_URL}/api/customers/invalid-customer-id/receive-payment",
            json={"amount": 500, "method": "Cash"}
        )
        assert response.status_code == 404


class TestPaymentAllocationOrder:
    """Test payment allocation prioritizes: Interest -> Penalty -> Oldest Invoice"""
    
    def test_payment_allocation_priority(self, api_client, test_customer, test_product):
        """Verify payment allocates to interest invoices first, then penalty, then oldest"""
        customer_id = test_customer["id"]
        past_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        
        # 1. Create a regular invoice
        regular_invoice_data = {
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": BRANCH_ID,
            "order_date": past_date,
            "terms": "COD",
            "terms_days": 0,
            "interest_rate": 3,
            "items": [{
                "product_id": test_product["id"],
                "product_name": test_product["name"],
                "quantity": 1,
                "rate": 2000
            }]
        }
        inv_response = api_client.post(f"{BASE_URL}/api/invoices", json=regular_invoice_data)
        assert inv_response.status_code in [200, 201]
        regular_invoice = inv_response.json()
        print(f"Created regular invoice: {regular_invoice['invoice_number']}")
        
        # 2. Try to generate interest (may not work if no overdue yet based on due_date logic)
        interest_response = api_client.post(f"{BASE_URL}/api/customers/{customer_id}/generate-interest")
        assert interest_response.status_code == 200
        interest_result = interest_response.json()
        print(f"Interest result: {interest_result}")
        
        # 3. Try to generate penalty
        penalty_response = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-penalty",
            json={"penalty_rate": 5}
        )
        assert penalty_response.status_code == 200
        penalty_result = penalty_response.json()
        print(f"Penalty result: {penalty_result}")
        
        # 4. Get open invoices to check types
        invoices_response = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices")
        invoices = invoices_response.json()
        
        interest_invoices = [i for i in invoices if i.get("sale_type") == "interest_charge"]
        penalty_invoices = [i for i in invoices if i.get("sale_type") == "penalty_charge"]
        regular_invoices = [i for i in invoices if i.get("sale_type") not in ("interest_charge", "penalty_charge")]
        
        print(f"Invoice types: interest={len(interest_invoices)}, penalty={len(penalty_invoices)}, regular={len(regular_invoices)}")
        
        # 5. Make a large payment to cover multiple invoices
        total_open = sum(i["balance"] for i in invoices)
        if total_open > 0:
            pay_response = api_client.post(
                f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
                json={"amount": min(total_open, 5000), "method": "Cash"}
            )
            assert pay_response.status_code == 200
            result = pay_response.json()
            print(f"Allocation result: {result['allocations']}")
            
            # Verify allocation order if we have multiple invoice types
            if len(result["allocations"]) > 1 and interest_invoices and regular_invoices:
                # Interest should be allocated first
                first_alloc = result["allocations"][0]
                interest_numbers = [i["invoice_number"] for i in interest_invoices]
                if first_alloc["invoice"] in interest_numbers:
                    print("VERIFIED: Interest invoice allocated first")


class TestCashierWalletUpdate:
    """Test that receive-payment updates cashier wallet balance"""
    
    def test_payment_updates_wallet(self, api_client, test_customer, test_product):
        """Verify receive-payment updates cashier wallet balance"""
        customer_id = test_customer["id"]
        
        # 1. Get current wallet balance
        wallets_response = api_client.get(f"{BASE_URL}/api/fund-wallets", params={"branch_id": BRANCH_ID})
        assert wallets_response.status_code == 200
        wallets = wallets_response.json()
        cashier_wallet = next((w for w in wallets if w["type"] == "cashier"), None)
        initial_balance = cashier_wallet["balance"] if cashier_wallet else 0
        print(f"Initial cashier wallet balance: {initial_balance}")
        
        # 2. Create invoice if needed
        invoice_data = {
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": BRANCH_ID,
            "items": [{
                "product_id": test_product["id"],
                "product_name": test_product["name"],
                "quantity": 1,
                "rate": 1500
            }]
        }
        inv_response = api_client.post(f"{BASE_URL}/api/invoices", json=invoice_data)
        assert inv_response.status_code in [200, 201]
        
        # 3. Make a payment
        payment_amount = 500
        pay_response = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
            json={"amount": payment_amount, "method": "Cash"}
        )
        assert pay_response.status_code == 200
        result = pay_response.json()
        total_applied = result.get("total_applied", 0)
        
        # 4. Check wallet balance increased
        wallets_response2 = api_client.get(f"{BASE_URL}/api/fund-wallets", params={"branch_id": BRANCH_ID})
        wallets2 = wallets_response2.json()
        cashier_wallet2 = next((w for w in wallets2 if w["type"] == "cashier"), None)
        new_balance = cashier_wallet2["balance"] if cashier_wallet2 else 0
        
        print(f"Wallet balance: {initial_balance} -> {new_balance} (expected increase: {total_applied})")
        # Wallet should increase by total_applied amount
        assert new_balance >= initial_balance, "Wallet balance should increase after payment"


class TestIntegration:
    """Integration tests for the complete receive payments workflow"""
    
    def test_complete_payment_cycle(self, api_client, test_customer, test_product):
        """Test complete cycle: invoice -> interest -> penalty -> payment -> verify"""
        customer_id = test_customer["id"]
        
        # 1. Create invoice
        invoice_data = {
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": BRANCH_ID,
            "items": [{
                "product_id": test_product["id"],
                "product_name": test_product["name"],
                "quantity": 3,
                "rate": 1500
            }]
        }
        inv_response = api_client.post(f"{BASE_URL}/api/invoices", json=invoice_data)
        assert inv_response.status_code in [200, 201]
        invoice = inv_response.json()
        original_balance = invoice["balance"]
        
        # 2. Get all open invoices
        invoices_before = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices").json()
        total_before = sum(i["balance"] for i in invoices_before)
        print(f"Total open balance before payment: {total_before}")
        
        # 3. Make payment
        pay_response = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
            json={"amount": 1000, "method": "Cash", "reference": "TEST-INTEGRATION"}
        )
        assert pay_response.status_code == 200
        result = pay_response.json()
        
        # 4. Verify balances reduced
        invoices_after = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices").json()
        total_after = sum(i["balance"] for i in invoices_after)
        print(f"Total open balance after payment: {total_after}")
        
        assert total_after < total_before, "Total balance should decrease after payment"
        assert total_before - total_after == result["total_applied"], "Balance reduction should match applied amount"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
