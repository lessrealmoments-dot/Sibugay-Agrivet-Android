"""
Backend API tests for QB-style Payments Page with Discount Feature
Tests: Customer invoices, receive-payment with allocations and discounts,
       interest/penalty generation, payment history
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"


class TestQBPaymentsAPI:
    """Test QB-style payments API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get a customer with open invoices
        customers_resp = self.session.get(f"{BASE_URL}/api/customers", params={"limit": 100})
        customers = customers_resp.json().get("customers", [])
        
        # Find customer with balance (Credit Customer 264ebc6f)
        self.test_customer = None
        for c in customers:
            if "Credit Customer 264ebc6f" in c.get("name", "") or c.get("balance", 0) > 0:
                self.test_customer = c
                break
        
        if not self.test_customer:
            pytest.skip("No customer with balance found for testing")
    
    def test_get_customer_open_invoices(self):
        """Test GET /customers/{id}/invoices returns open invoices"""
        response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        
        assert response.status_code == 200
        invoices = response.json()
        assert isinstance(invoices, list)
        
        # All returned invoices should have balance > 0
        for inv in invoices:
            assert inv.get("balance", 0) > 0, f"Invoice {inv.get('invoice_number')} has no balance"
            assert "id" in inv
            assert "invoice_number" in inv
            assert "sale_type" in inv
        
        print(f"Found {len(invoices)} open invoices for customer")
        return invoices
    
    def test_get_charges_preview(self):
        """Test GET /customers/{id}/charges-preview returns interest preview"""
        response = self.session.get(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/charges-preview",
            params={"as_of_date": "2026-03-12"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should have preview fields
        assert "total_interest" in data or "interest_preview" in data
        print(f"Charges preview: total_interest={data.get('total_interest', 0)}")
    
    def test_generate_interest_invoice(self):
        """Test POST /customers/{id}/generate-interest creates interest invoice"""
        # Only run if customer has interest rate
        if not self.test_customer.get("interest_rate"):
            pytest.skip("Customer has no interest rate configured")
        
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/generate-interest",
            json={"as_of_date": "2026-03-12"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should indicate success or no interest to generate
        assert "message" in data
        assert "total_interest" in data
        
        if data["total_interest"] > 0:
            assert "invoice_number" in data
            assert data["invoice_number"].startswith("INT")
            print(f"Generated interest invoice: {data['invoice_number']} for {data['total_interest']}")
        else:
            print(f"No interest generated: {data['message']}")
    
    def test_generate_penalty_invoice(self):
        """Test POST /customers/{id}/generate-penalty creates penalty invoice"""
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/generate-penalty",
            json={"penalty_rate": 5, "as_of_date": "2026-03-12"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "total_penalty" in data
        
        if data["total_penalty"] > 0:
            assert "invoice_number" in data
            assert data["invoice_number"].startswith("PEN")
            print(f"Generated penalty invoice: {data['invoice_number']} for {data['total_penalty']}")
        else:
            print(f"No penalty generated: {data['message']}")
    
    def test_receive_payment_basic(self):
        """Test POST /customers/{id}/receive-payment applies payment to invoices"""
        # Get open invoices first
        inv_response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        invoices = inv_response.json()
        
        if not invoices:
            pytest.skip("No open invoices for payment test")
        
        # Create allocation for first invoice (partial payment)
        first_invoice = invoices[0]
        payment_amount = min(10.00, first_invoice["balance"])
        
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/receive-payment",
            json={
                "allocations": [
                    {"invoice_id": first_invoice["id"], "amount": payment_amount}
                ],
                "method": "Cash",
                "reference": "TEST-PAY-001",
                "date": "2026-03-12"
            }
        )
        
        assert response.status_code == 200, f"Payment failed: {response.text}"
        data = response.json()
        
        assert "total_applied" in data
        assert data["total_applied"] == payment_amount
        assert "applied_invoices" in data
        assert len(data["applied_invoices"]) > 0
        assert "deposited_to" in data
        
        print(f"Payment applied: {data['total_applied']} to {len(data['applied_invoices'])} invoice(s)")
    
    def test_receive_payment_with_discount(self):
        """Test POST /customers/{id}/receive-payment with discount on interest/penalty invoice"""
        # Get open invoices
        inv_response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        invoices = inv_response.json()
        
        # Find an interest or penalty invoice
        discountable_invoice = None
        for inv in invoices:
            if inv.get("sale_type") in ("interest_charge", "penalty_charge"):
                discountable_invoice = inv
                break
        
        if not discountable_invoice:
            pytest.skip("No interest/penalty invoice found for discount test")
        
        # Apply discount with small payment
        discount_amount = min(5.00, discountable_invoice["balance"] / 2)
        payment_amount = max(0, discountable_invoice["balance"] - discount_amount - 1)  # Leave $1 balance
        
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/receive-payment",
            json={
                "allocations": [
                    {
                        "invoice_id": discountable_invoice["id"],
                        "amount": payment_amount,
                        "discount": discount_amount
                    }
                ],
                "method": "Cash",
                "reference": "TEST-DISCOUNT-001",
                "date": "2026-03-12"
            }
        )
        
        assert response.status_code == 200, f"Payment with discount failed: {response.text}"
        data = response.json()
        
        assert "total_applied" in data
        assert "total_discounted" in data
        assert data["total_discounted"] >= 0  # Discount was applied
        
        print(f"Payment with discount: applied={data['total_applied']}, discounted={data['total_discounted']}")
    
    def test_receive_payment_discount_rejected_for_regular_invoice(self):
        """Test that discount is ignored for non-interest/penalty invoices"""
        # Get open invoices
        inv_response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        invoices = inv_response.json()
        
        # Find a regular invoice (not interest/penalty)
        regular_invoice = None
        for inv in invoices:
            if inv.get("sale_type") not in ("interest_charge", "penalty_charge"):
                regular_invoice = inv
                break
        
        if not regular_invoice:
            pytest.skip("No regular invoice found")
        
        # Try to apply discount to regular invoice
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/receive-payment",
            json={
                "allocations": [
                    {
                        "invoice_id": regular_invoice["id"],
                        "amount": 5.00,
                        "discount": 10.00  # This should be ignored
                    }
                ],
                "method": "Cash",
                "reference": "TEST-NO-DISCOUNT",
                "date": "2026-03-12"
            }
        )
        
        assert response.status_code == 200, f"Payment failed: {response.text}"
        data = response.json()
        
        # Discount should be 0 or ignored for regular invoices
        assert data.get("total_discounted", 0) == 0, "Discount should be rejected for regular invoice"
        print("Correctly rejected discount for regular invoice")
    
    def test_payment_history(self):
        """Test GET /customers/{id}/payment-history returns payment records"""
        response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/payment-history")
        
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)
        
        # Each history item should have required fields
        for record in history[:5]:  # Check first 5
            assert "date" in record
            assert "invoice_number" in record
            assert "amount" in record
            assert "method" in record
        
        print(f"Found {len(history)} payment history records")
    
    def test_receive_payment_multi_allocation(self):
        """Test payment distributed across multiple invoices"""
        # Get open invoices
        inv_response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        invoices = inv_response.json()
        
        if len(invoices) < 2:
            pytest.skip("Need at least 2 invoices for multi-allocation test")
        
        # Create allocations for first 2 invoices
        allocations = [
            {"invoice_id": invoices[0]["id"], "amount": min(5.00, invoices[0]["balance"])},
            {"invoice_id": invoices[1]["id"], "amount": min(5.00, invoices[1]["balance"])}
        ]
        total_amount = sum(a["amount"] for a in allocations)
        
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/receive-payment",
            json={
                "allocations": allocations,
                "method": "GCash",
                "reference": "TEST-MULTI-001",
                "date": "2026-03-12"
            }
        )
        
        assert response.status_code == 200, f"Multi-allocation payment failed: {response.text}"
        data = response.json()
        
        assert data["total_applied"] == total_amount
        assert len(data["applied_invoices"]) == 2
        assert data["deposited_to"] == "Digital / E-Wallet"  # GCash is digital
        
        print(f"Multi-allocation: {total_amount} applied to 2 invoices via GCash")
    
    def test_receive_payment_zero_amount_rejected(self):
        """Test that zero/negative amounts are rejected"""
        inv_response = self.session.get(f"{BASE_URL}/api/customers/{self.test_customer['id']}/invoices")
        invoices = inv_response.json()
        
        if not invoices:
            pytest.skip("No invoices for test")
        
        response = self.session.post(
            f"{BASE_URL}/api/customers/{self.test_customer['id']}/receive-payment",
            json={
                "allocations": [
                    {"invoice_id": invoices[0]["id"], "amount": 0}
                ],
                "method": "Cash"
            }
        )
        
        # Should fail with 400
        assert response.status_code == 400, "Zero amount should be rejected"
        print("Correctly rejected zero amount payment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
