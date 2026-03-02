"""
Test Audit Center API endpoints - Iteration 93
Tests for:
- Cash reconciliation formula (starting float, cash sales, partial cash, split cash, cash AR, fund transfers, cashier expenses)
- Unverified items section (expenses and POs without verification)
- Expense detail lists with receipt indicators
- AR payment details with invoice numbers
- Fund transfer details
- PO details in payables section
- Overall audit compute response structure
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "limittest@testmail.com"
TEST_PASSWORD = "TestAdmin123!"
TEST_BRANCH_ID = "c435277f-9fc7-4d83-83e7-38be5b4423ac"
PERIOD_FROM = "2026-02-01"
PERIOD_TO = "2026-02-28"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestAuditComputeEndpoint:
    """Tests for GET /api/audit/compute endpoint"""
    
    def test_audit_compute_returns_200(self, api_client):
        """Test that audit compute endpoint returns successfully"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO,
                "audit_type": "partial"
            }
        )
        assert response.status_code == 200, f"Audit compute failed: {response.text}"
        data = response.json()
        assert "cash" in data, "Cash section missing from response"
        assert "sales" in data, "Sales section missing from response"
        assert "ar" in data, "AR section missing from response"
        assert "payables" in data, "Payables section missing from response"
        assert "unverified" in data, "Unverified section missing from response"
        print(f"✓ Audit compute returned all required sections")


class TestCashReconciliationFormula:
    """Tests for cash reconciliation section with proper formula components"""
    
    def test_cash_section_has_formula_components(self, api_client):
        """Test that cash section includes all formula components"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO,
                "audit_type": "partial"
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        
        # Check required formula components
        required_fields = [
            "starting_float",
            "cash_sales",
            "total_partial_cash",
            "total_split_cash",
            "total_cash_ar",
            "net_fund_transfers",
            "total_cashier_expenses",
            "expected_cash"
        ]
        for field in required_fields:
            assert field in cash, f"Missing field: {field}"
            print(f"✓ Cash section has {field}: {cash[field]}")
        
        # Verify formula is correct
        assert "formula" in cash, "Formula string missing"
        print(f"✓ Formula: {cash['formula']}")
    
    def test_cash_section_has_ar_payments_detail(self, api_client):
        """Test that AR payments list is included with fund_source"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        
        ar_payments = cash.get("ar_payments", [])
        if ar_payments:
            for p in ar_payments[:3]:
                assert "invoice_number" in p, "AR payment missing invoice_number"
                assert "fund_source" in p, "AR payment missing fund_source"
                assert "amount_paid" in p, "AR payment missing amount_paid"
                print(f"✓ AR Payment: {p.get('invoice_number')} - {p.get('fund_source')} - {p.get('amount_paid')}")
        else:
            print("ℹ No AR payments in period")
        
        # Verify total_digital_ar is present (separated from cash AR)
        assert "total_digital_ar" in cash, "total_digital_ar field missing"
        print(f"✓ Digital AR total: {cash.get('total_digital_ar')}")
    
    def test_cash_section_has_fund_transfer_details(self, api_client):
        """Test fund transfer breakdown"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        
        # Check fund transfer components
        assert "capital_to_cashier" in cash, "capital_to_cashier missing"
        assert "safe_to_cashier" in cash, "safe_to_cashier missing"
        assert "cashier_to_safe" in cash, "cashier_to_safe missing"
        assert "fund_transfer_details" in cash, "fund_transfer_details list missing"
        
        print(f"✓ Capital to Cashier: {cash.get('capital_to_cashier')}")
        print(f"✓ Safe to Cashier: {cash.get('safe_to_cashier')}")
        print(f"✓ Cashier to Safe: {cash.get('cashier_to_safe')}")
        print(f"✓ Net Fund Transfers: {cash.get('net_fund_transfers')}")


class TestExpenseDetailsWithReceipts:
    """Tests for expense detail list with verification and receipt indicators"""
    
    def test_expenses_have_verification_status(self, api_client):
        """Test that expenses include verified status and receipt info"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        expenses = cash.get("expenses", [])
        
        if expenses:
            for exp in expenses[:5]:
                assert "id" in exp, "Expense missing id"
                assert "category" in exp, "Expense missing category"
                assert "fund_source" in exp, "Expense missing fund_source"
                assert "verified" in exp, "Expense missing verified status"
                assert "has_receipt" in exp, "Expense missing has_receipt indicator"
                print(f"✓ Expense: {exp.get('category')} - Fund: {exp.get('fund_source')} - Verified: {exp.get('verified')} - Receipt: {exp.get('has_receipt')}")
        else:
            print("ℹ No expenses in period")


class TestUnverifiedItemsSection:
    """Tests for the new Unverified Items section"""
    
    def test_unverified_section_structure(self, api_client):
        """Test unverified section returns proper structure"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        unverified = response.json().get("unverified", {})
        
        # Check required fields
        required_fields = [
            "expenses",
            "expenses_count",
            "expenses_no_receipt",
            "total_unverified_expense_amount",
            "purchase_orders",
            "po_count",
            "po_no_receipt",
            "total_items",
            "severity"
        ]
        for field in required_fields:
            assert field in unverified, f"Unverified section missing field: {field}"
        
        print(f"✓ Unverified expenses: {unverified.get('expenses_count')}")
        print(f"✓ Unverified expenses without receipt: {unverified.get('expenses_no_receipt')}")
        print(f"✓ Unverified POs: {unverified.get('po_count')}")
        print(f"✓ Severity: {unverified.get('severity')}")
    
    def test_unverified_expenses_have_receipt_indicator(self, api_client):
        """Test unverified expenses include has_receipt flag"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        unverified = response.json().get("unverified", {})
        expenses = unverified.get("expenses", [])
        
        if expenses:
            for exp in expenses[:3]:
                assert "id" in exp, "Unverified expense missing id"
                assert "has_receipt" in exp, "Unverified expense missing has_receipt"
                assert "category" in exp, "Unverified expense missing category"
                assert "amount" in exp, "Unverified expense missing amount"
                print(f"✓ Unverified Expense: {exp.get('category')} - {exp.get('amount')} - Receipt: {exp.get('has_receipt')}")
        else:
            print("ℹ No unverified expenses found")
    
    def test_unverified_pos_have_receipt_indicator(self, api_client):
        """Test unverified POs include has_receipt flag"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        unverified = response.json().get("unverified", {})
        pos = unverified.get("purchase_orders", [])
        
        if pos:
            for po in pos[:3]:
                assert "id" in po, "Unverified PO missing id"
                assert "has_receipt" in po, "Unverified PO missing has_receipt"
                assert "po_number" in po, "Unverified PO missing po_number"
                print(f"✓ Unverified PO: {po.get('po_number')} - {po.get('vendor')} - Receipt: {po.get('has_receipt')}")
        else:
            print("ℹ No unverified POs found")


class TestPayablesSection:
    """Tests for payables section with PO details"""
    
    def test_payables_has_po_details(self, api_client):
        """Test that payables section includes PO detail list"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        payables = response.json().get("payables", {})
        
        assert "po_details" in payables, "po_details list missing from payables"
        assert "total_outstanding_ap" in payables, "total_outstanding_ap missing"
        assert "unpaid_po_count" in payables, "unpaid_po_count missing"
        
        po_details = payables.get("po_details", [])
        if po_details:
            for po in po_details[:3]:
                assert "po_number" in po, "PO missing po_number"
                assert "vendor" in po, "PO missing vendor"
                print(f"✓ PO: {po.get('po_number')} - {po.get('vendor')}")
        else:
            print("ℹ No PO details in period")


class TestPartialAndSplitInvoices:
    """Tests for partial and split invoice detail lists"""
    
    def test_partial_invoices_detail(self, api_client):
        """Test partial invoices list includes invoice numbers"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        
        assert "partial_invoices" in cash, "partial_invoices list missing"
        partial = cash.get("partial_invoices", [])
        if partial:
            for inv in partial[:3]:
                assert "invoice_number" in inv, "Partial invoice missing invoice_number"
                assert "amount_paid" in inv, "Partial invoice missing amount_paid"
                print(f"✓ Partial Invoice: {inv.get('invoice_number')} - Paid: {inv.get('amount_paid')}")
        else:
            print("ℹ No partial invoices in period")
    
    def test_split_invoices_detail(self, api_client):
        """Test split invoices list includes cash and digital amounts"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        cash = response.json().get("cash", {})
        
        assert "split_invoices" in cash, "split_invoices list missing"
        split = cash.get("split_invoices", [])
        if split:
            for inv in split[:3]:
                assert "invoice_number" in inv, "Split invoice missing invoice_number"
                assert "cash_amount" in inv, "Split invoice missing cash_amount"
                assert "digital_amount" in inv, "Split invoice missing digital_amount"
                print(f"✓ Split Invoice: {inv.get('invoice_number')} - Cash: {inv.get('cash_amount')} - Digital: {inv.get('digital_amount')}")
        else:
            print("ℹ No split invoices in period")


class TestOverallAuditScore:
    """Tests for overall audit score calculation"""
    
    def test_audit_includes_all_severity_sections(self, api_client):
        """Test that all sections have severity ratings"""
        response = api_client.get(
            f"{BASE_URL}/api/audit/compute",
            params={
                "branch_id": TEST_BRANCH_ID,
                "period_from": PERIOD_FROM,
                "period_to": PERIOD_TO
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        sections_with_severity = ["cash", "sales", "ar", "payables", "unverified"]
        for section in sections_with_severity:
            if section in data and data[section]:
                assert "severity" in data[section], f"Section {section} missing severity"
                print(f"✓ {section} severity: {data[section].get('severity')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
