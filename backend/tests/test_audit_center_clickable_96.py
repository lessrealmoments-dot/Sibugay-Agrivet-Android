"""
Test Audit Center Clickable References and Formula Fix (Iteration 96)

Tests:
1. Audit compute API returns correct formula including fund_transfers
2. Expense endpoint returns expense data for InvoiceDetailModal
3. Invoice by-number endpoint handles both invoices and POs
4. Unverified items include reference_number for expenses
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Login with super admin credentials"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


class TestAuditCenterFormula:
    """Verify the Audit Center formula includes fund_transfers"""
    
    def test_audit_compute_returns_correct_formula(self, auth_token):
        """The formula field should include 'Net Fund Transfers'"""
        response = requests.get(
            f"{BASE_URL}/api/audit/compute",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "audit_type": "partial",
                "period_from": "2024-01-01",
                "period_to": "2026-12-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check formula field
        assert "cash" in data
        formula = data["cash"].get("formula", "")
        assert "Net Fund Transfers" in formula, f"Formula missing fund transfers: {formula}"
        print(f"✅ Formula: {formula}")
    
    def test_audit_compute_includes_fund_transfer_fields(self, auth_token):
        """Verify net_fund_transfers and related fields are in response"""
        response = requests.get(
            f"{BASE_URL}/api/audit/compute",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "audit_type": "partial",
                "period_from": "2024-01-01",
                "period_to": "2026-12-31"
            }
        )
        assert response.status_code == 200
        cash = response.json()["cash"]
        
        # These fields should exist for fund transfer tracking
        assert "net_fund_transfers" in cash
        assert "capital_to_cashier" in cash
        assert "safe_to_cashier" in cash
        assert "cashier_to_safe" in cash
        assert "fund_transfer_details" in cash
        print("✅ All fund transfer fields present in audit response")


class TestInvoiceDetailModalEndpoints:
    """Verify endpoints used by InvoiceDetailModal for clickable references"""
    
    def test_invoice_by_number_returns_invoice(self, auth_token):
        """Test that /invoices/by-number returns invoice with _collection marker"""
        # First get an invoice number
        response = requests.get(
            f"{BASE_URL}/api/invoices",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"limit": 1}
        )
        if response.status_code == 200:
            invoices = response.json().get("invoices", [])
            if invoices:
                inv_number = invoices[0].get("invoice_number") or invoices[0].get("sale_number")
                
                # Now fetch by number
                resp = requests.get(
                    f"{BASE_URL}/api/invoices/by-number/{inv_number}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data.get("_collection") == "invoices"
                print(f"✅ Invoice {inv_number} returned with _collection='invoices'")
    
    def test_po_by_number_returns_po_collection(self, auth_token):
        """Test that /invoices/by-number with PO number returns _collection='purchase_orders'"""
        # First get a PO number
        response = requests.get(
            f"{BASE_URL}/api/purchase-orders",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"limit": 1}
        )
        if response.status_code == 200:
            pos = response.json().get("purchase_orders", [])
            if pos:
                po_number = pos[0].get("po_number")
                
                # Fetch by number - should return PO
                resp = requests.get(
                    f"{BASE_URL}/api/invoices/by-number/{po_number}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data.get("_collection") == "purchase_orders"
                print(f"✅ PO {po_number} returned with _collection='purchase_orders'")
    
    def test_expense_by_id_returns_expense(self, auth_token):
        """Test that /expenses/{id} returns expense data"""
        # First get an expense ID
        response = requests.get(
            f"{BASE_URL}/api/expenses",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"limit": 1}
        )
        if response.status_code == 200:
            expenses = response.json().get("expenses", [])
            if expenses:
                exp_id = expenses[0].get("id")
                
                # Fetch by ID
                resp = requests.get(
                    f"{BASE_URL}/api/expenses/{exp_id}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data.get("id") == exp_id
                assert "category" in data
                print(f"✅ Expense {exp_id} returned with category: {data.get('category')}")


class TestUnverifiedItemsReferenceNumber:
    """Verify unverified items include reference_number"""
    
    def test_unverified_expenses_have_reference_number_field(self, auth_token):
        """Check that unverified expenses include reference_number"""
        response = requests.get(
            f"{BASE_URL}/api/audit/compute",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "audit_type": "partial",
                "period_from": "2024-01-01",
                "period_to": "2026-12-31"
            }
        )
        assert response.status_code == 200
        unverified = response.json().get("unverified", {})
        expenses = unverified.get("expenses", [])
        
        # If there are unverified expenses, check they have reference_number
        for exp in expenses:
            assert "reference_number" in exp, f"Expense missing reference_number: {exp}"
        
        if expenses:
            print(f"✅ {len(expenses)} unverified expenses all have reference_number field")
        else:
            print("⚠️ No unverified expenses found to test (normal if data is clean)")
    
    def test_cash_expenses_have_reference_number_field(self, auth_token):
        """Check that cash expense details include reference_number"""
        response = requests.get(
            f"{BASE_URL}/api/audit/compute",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "audit_type": "partial",
                "period_from": "2024-01-01",
                "period_to": "2026-12-31"
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        expenses = cash.get("expenses", [])
        
        # If there are cash expenses, check they have reference_number
        for exp in expenses:
            assert "reference_number" in exp, f"Cash expense missing reference_number: {exp}"
        
        if expenses:
            print(f"✅ {len(expenses)} cash expenses all have reference_number field")
        else:
            print("⚠️ No cash expenses found to test (normal if no expenses in period)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
