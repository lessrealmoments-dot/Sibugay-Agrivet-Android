"""
Tests for QuickBooks-style Receive Payments feature (new endpoints):
- GET /customers/{id}/invoices - sorted: penalty → interest → regular
- POST /customers/{id}/generate-interest - creates INT- invoice
- POST /customers/{id}/generate-penalty - creates PEN- invoice
- POST /customers/{id}/receive-payment (QB multi-invoice allocation)
- GET /customers/{id}/payment-history
- GET /customers/{id}/charges-preview
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known customer from agent context
SADRAK_CUSTOMER_ID = "a842f0fe-61fc-46bf-8c89-13d926825206"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token with owner credentials"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner",
        "password": "testpass123"
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
    """Create a fresh test customer for payment testing"""
    response = api_client.post(f"{BASE_URL}/api/customers", json={
        "name": "TEST_QBPaymentCustomer",
        "phone": "09-TEST-QB",
        "address": "Test QB Address",
        "price_scheme": "Retail",
        "credit_limit": 50000,
        "interest_rate": 3,  # 3% monthly so interest can be generated
        "grace_period": 7
    })
    assert response.status_code in [200, 201], f"Customer creation failed: {response.text}"
    customer = response.json()
    yield customer
    # Cleanup
    try:
        api_client.delete(f"{BASE_URL}/api/customers/{customer['id']}")
    except Exception:
        pass


@pytest.fixture(scope="module")
def test_product(api_client):
    """Create a test product"""
    response = api_client.post(f"{BASE_URL}/api/products", json={
        "name": "TEST_QBPaymentProduct",
        "sku": f"TEST-QB-{datetime.now().strftime('%H%M%S')}",
        "category": "Testing",
        "cost_price": 1000,
        "prices": {"Retail": 1500, "Wholesale": 1200}
    })
    assert response.status_code in [200, 201], f"Product creation failed: {response.text}"
    product = response.json()
    yield product
    try:
        api_client.delete(f"{BASE_URL}/api/products/{product['id']}")
    except Exception:
        pass


@pytest.fixture(scope="module")
def branch_id(api_client):
    """Get first available branch ID"""
    response = api_client.get(f"{BASE_URL}/api/branches")
    assert response.status_code == 200
    branches = response.json()
    assert len(branches) > 0, "No branches found"
    return branches[0]["id"]


# ==================== GET /customers/{id}/invoices ====================

class TestGetCustomerInvoices:
    """Test GET /customers/{id}/invoices"""

    def test_get_open_invoices_sadrak(self, api_client):
        """GET invoices for SADRAK customer — should return list"""
        res = api_client.get(f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/invoices")
        assert res.status_code == 200, f"Failed: {res.text}"
        invoices = res.json()
        assert isinstance(invoices, list), "Should return a list"
        print(f"SADRAK open invoices: {len(invoices)}")
        if invoices:
            for inv in invoices:
                assert "invoice_number" in inv, "invoice_number missing"
                assert "balance" in inv, "balance missing"
                assert "grand_total" in inv, "grand_total missing"
                assert "sale_type" in inv, "sale_type missing"
                assert "id" in inv, "id missing"
                assert inv["balance"] > 0, "Open invoice should have positive balance"

    def test_get_invoices_sorting_penalty_first(self, api_client, test_customer, test_product, branch_id):
        """Invoices sorted penalty → interest → regular"""
        customer_id = test_customer["id"]
        past_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

        # Create a regular invoice
        inv_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "order_date": past_date,
            "due_date": past_date,
            "interest_rate": 3,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 1500}]
        })
        assert inv_res.status_code in [200, 201], f"Invoice creation failed: {inv_res.text}"
        regular_inv = inv_res.json()
        print(f"Created regular invoice: {regular_inv['invoice_number']}, balance: {regular_inv['balance']}")

        # Generate penalty (old date → past grace period)
        pen_res = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-penalty",
            json={"penalty_rate": 5, "as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert pen_res.status_code == 200
        print(f"Penalty result: {pen_res.json()}")

        # Now get sorted invoices
        sorted_res = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices")
        assert sorted_res.status_code == 200
        inv_list = sorted_res.json()
        assert len(inv_list) >= 1

        # Check sort order: penalty first, then regular
        types = [i.get("sale_type") for i in inv_list]
        print(f"Invoice types in order: {types}")

        # If penalty was generated, it must come before regular
        if "penalty_charge" in types and any(t not in ("penalty_charge", "interest_charge") for t in types):
            penalty_idx = types.index("penalty_charge")
            regular_idx = next(i for i, t in enumerate(types) if t not in ("penalty_charge", "interest_charge"))
            assert penalty_idx < regular_idx, f"Penalty should come before regular invoices. Got order: {types}"
            print("VERIFIED: penalty_charge sorted before regular invoices")

    def test_get_invoices_nonexistent_customer(self, api_client):
        """GET invoices for nonexistent customer returns empty list"""
        res = api_client.get(f"{BASE_URL}/api/customers/nonexistent-id-xyz/invoices")
        # Should return empty list (no items match) or 404
        assert res.status_code in [200, 404]
        if res.status_code == 200:
            assert res.json() == [], "Should return empty list for nonexistent customer"


# ==================== POST /generate-interest ====================

class TestGenerateInterest:
    """Test POST /customers/{id}/generate-interest"""

    def test_generate_interest_sadrak_no_rate(self, api_client):
        """Generate interest for SADRAK — returns response (may have 0 rate)"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/generate-interest",
            json={"as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        result = res.json()
        assert "message" in result or "total_interest" in result
        print(f"SADRAK interest result: {result}")

    def test_generate_interest_with_rate_customer(self, api_client, test_customer, test_product, branch_id):
        """Generate interest for customer with interest_rate set"""
        customer_id = test_customer["id"]
        past_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")

        # Create invoice with past due date
        inv_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "order_date": past_date,
            "due_date": past_date,
            "interest_rate": 3,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 2000}]
        })
        assert inv_res.status_code in [200, 201]

        res = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-interest",
            json={"as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        result = res.json()
        print(f"Interest generation result: {result}")
        assert "total_interest" in result

        # If interest was generated, verify the invoice structure
        if result.get("total_interest", 0) > 0:
            assert "invoice_number" in result, "Should return invoice_number"
            assert result["invoice_number"].startswith("INT"), f"Interest invoice should start with INT, got: {result['invoice_number']}"
            print(f"Interest invoice created: {result['invoice_number']} for {result['total_interest']}")

    def test_generate_interest_nonexistent_customer(self, api_client):
        """Generate interest for nonexistent customer returns 404"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/nonexistent-xyz/generate-interest",
            json={"as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert res.status_code == 404


# ==================== POST /generate-penalty ====================

class TestGeneratePenalty:
    """Test POST /customers/{id}/generate-penalty"""

    def test_generate_penalty_sadrak(self, api_client):
        """Generate penalty for SADRAK"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/generate-penalty",
            json={"penalty_rate": 5, "as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        result = res.json()
        assert "message" in result or "total_penalty" in result
        print(f"SADRAK penalty result: {result}")

    def test_generate_penalty_within_grace(self, api_client, test_customer, test_product, branch_id):
        """Generate penalty within grace period returns no-penalty message"""
        customer_id = test_customer["id"]
        today = datetime.now().strftime("%Y-%m-%d")

        # Create invoice with today's date (within grace period)
        inv_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "order_date": today,
            "due_date": today,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 500}]
        })
        assert inv_res.status_code in [200, 201]

        # Try to generate penalty — should return no penalty (within grace)
        res = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/generate-penalty",
            json={"penalty_rate": 5, "as_of_date": today}
        )
        assert res.status_code == 200
        result = res.json()
        print(f"Within grace penalty result: {result}")
        assert result.get("total_penalty", 0) == 0 or "grace" in result.get("message", "").lower() or "within" in result.get("message", "").lower()

    def test_generate_penalty_nonexistent_customer(self, api_client):
        """Generate penalty for nonexistent customer returns 404"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/nonexistent-xyz/generate-penalty",
            json={"penalty_rate": 5}
        )
        assert res.status_code == 404


# ==================== POST /receive-payment ====================

class TestReceivePayment:
    """Test POST /customers/{id}/receive-payment (QB multi-invoice format)"""

    def test_receive_payment_sadrak_full_amount(self, api_client):
        """Receive payment for SADRAK — must use allocations format"""
        # First get SADRAK's open invoices
        inv_res = api_client.get(f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/invoices")
        assert inv_res.status_code == 200
        open_invoices = inv_res.json()

        if not open_invoices:
            pytest.skip("SADRAK has no open invoices to test")

        invoice = open_invoices[0]
        pay_amount = min(invoice["balance"], 100)  # Pay partial to not wipe out test data

        res = api_client.post(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/receive-payment",
            json={
                "allocations": [{"invoice_id": invoice["id"], "amount": pay_amount}],
                "method": "Cash",
                "reference": "TEST-QB-001",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "memo": "Test payment"
            }
        )
        assert res.status_code == 200, f"Payment failed: {res.text}"
        result = res.json()
        print(f"Payment result: {result}")

        # Verify response structure
        assert "total_applied" in result, "Response must have total_applied"
        assert "applied_invoices" in result, "Response must have applied_invoices"
        assert "deposited_to" in result, "Response must have deposited_to"
        assert result["total_applied"] == pay_amount
        assert len(result["applied_invoices"]) >= 1

        # Verify allocation details
        alloc = result["applied_invoices"][0]
        assert "invoice_id" in alloc
        assert "invoice_number" in alloc
        assert "applied" in alloc
        assert "new_balance" in alloc

        print(f"Applied {pay_amount} to {alloc['invoice_number']}, new balance: {alloc['new_balance']}")

    def test_receive_payment_zero_amount_returns_400(self, api_client):
        """Payment with zero allocations returns 400"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/receive-payment",
            json={"allocations": [], "method": "Cash"}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"

    def test_receive_payment_invalid_invoice_id(self, api_client):
        """Payment with invalid invoice_id is ignored gracefully"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/receive-payment",
            json={
                "allocations": [{"invoice_id": "nonexistent-inv-id", "amount": 100}],
                "method": "Cash"
            }
        )
        # Should return 400 (no payment applied) since invoice not found
        assert res.status_code in [400, 200]
        print(f"Invalid invoice_id result: {res.status_code} - {res.json()}")

    def test_receive_payment_nonexistent_customer(self, api_client):
        """Payment for nonexistent customer returns 404"""
        res = api_client.post(
            f"{BASE_URL}/api/customers/nonexistent-xyz/receive-payment",
            json={"allocations": [{"invoice_id": "x", "amount": 100}], "method": "Cash"}
        )
        assert res.status_code == 404

    def test_receive_payment_multi_invoice(self, api_client, test_customer, test_product, branch_id):
        """Test multi-invoice payment allocation"""
        customer_id = test_customer["id"]
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        # Create 2 invoices
        inv1_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "order_date": past_date,
            "due_date": past_date,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 500}]
        })
        assert inv1_res.status_code in [200, 201]
        inv1 = inv1_res.json()

        inv2_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "order_date": past_date,
            "due_date": past_date,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 300}]
        })
        assert inv2_res.status_code in [200, 201]
        inv2 = inv2_res.json()

        # Pay both invoices
        res = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
            json={
                "allocations": [
                    {"invoice_id": inv1["id"], "amount": inv1["balance"]},
                    {"invoice_id": inv2["id"], "amount": inv2["balance"]},
                ],
                "method": "Bank Transfer",
                "reference": "TEST-MULTI-001",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        )
        assert res.status_code == 200, f"Multi-invoice payment failed: {res.text}"
        result = res.json()
        print(f"Multi-invoice payment: total_applied={result['total_applied']}, invoices={len(result['applied_invoices'])}")

        assert result["total_applied"] == round(inv1["balance"] + inv2["balance"], 2)
        assert len(result["applied_invoices"]) == 2

        # Verify invoices are now paid
        inv_after = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/invoices").json()
        inv1_after = next((i for i in inv_after if i["id"] == inv1["id"]), None)
        inv2_after = next((i for i in inv_after if i["id"] == inv2["id"]), None)
        # Both should be fully paid (not in open list) or have 0 balance
        assert inv1_after is None or inv1_after["balance"] == 0, "Invoice 1 should be fully paid"
        assert inv2_after is None or inv2_after["balance"] == 0, "Invoice 2 should be fully paid"
        print("Multi-invoice payment VERIFIED: both invoices paid")


# ==================== GET /payment-history ====================

class TestPaymentHistory:
    """Test GET /customers/{id}/payment-history"""

    def test_get_payment_history_sadrak(self, api_client):
        """Get payment history for SADRAK"""
        res = api_client.get(f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/payment-history")
        assert res.status_code == 200, f"Failed: {res.text}"
        history = res.json()
        assert isinstance(history, list), "Should return a list"
        print(f"SADRAK payment history: {len(history)} records")
        if history:
            record = history[0]
            assert "date" in record
            assert "invoice_number" in record
            assert "method" in record
            assert "amount" in record
            assert "recorded_by" in record

    def test_get_payment_history_after_payment(self, api_client, test_customer, test_product, branch_id):
        """Payment history grows after making a payment"""
        customer_id = test_customer["id"]

        # Get history before
        before_res = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/payment-history")
        history_before = before_res.json() if before_res.status_code == 200 else []
        count_before = len(history_before)

        # Create invoice and pay it
        inv_res = api_client.post(f"{BASE_URL}/api/invoices", json={
            "customer_id": customer_id,
            "customer_name": test_customer["name"],
            "branch_id": branch_id,
            "items": [{"product_id": test_product["id"], "product_name": test_product["name"],
                       "quantity": 1, "rate": 750}]
        })
        assert inv_res.status_code in [200, 201]
        inv = inv_res.json()

        pay_res = api_client.post(
            f"{BASE_URL}/api/customers/{customer_id}/receive-payment",
            json={
                "allocations": [{"invoice_id": inv["id"], "amount": 200}],
                "method": "GCash",
                "reference": "HIST-TEST-001"
            }
        )
        assert pay_res.status_code == 200

        # Get history after
        after_res = api_client.get(f"{BASE_URL}/api/customers/{customer_id}/payment-history")
        assert after_res.status_code == 200
        history_after = after_res.json()
        count_after = len(history_after)

        assert count_after > count_before, f"Payment history should grow: {count_before} -> {count_after}"
        print(f"Payment history grew: {count_before} → {count_after}")

        # Check the latest payment is at top
        latest = history_after[0]
        assert latest["method"] == "GCash"
        assert latest["amount"] == 200
        assert latest["reference"] == "HIST-TEST-001"

    def test_get_payment_history_nonexistent_customer(self, api_client):
        """Payment history for nonexistent customer returns empty list"""
        res = api_client.get(f"{BASE_URL}/api/customers/nonexistent-xyz/payment-history")
        assert res.status_code == 200
        assert res.json() == []


# ==================== GET /charges-preview ====================

class TestChargesPreview:
    """Test GET /customers/{id}/charges-preview"""

    def test_charges_preview_sadrak(self, api_client):
        """Preview charges for SADRAK"""
        res = api_client.get(
            f"{BASE_URL}/api/customers/{SADRAK_CUSTOMER_ID}/charges-preview",
            params={"as_of_date": datetime.now().strftime("%Y-%m-%d")}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        preview = res.json()
        assert "customer_id" in preview
        assert "total_principal" in preview
        assert "total_interest" in preview
        assert "interest_preview" in preview
        assert isinstance(preview["interest_preview"], list)
        print(f"SADRAK charges preview: principal={preview['total_principal']}, interest={preview['total_interest']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
