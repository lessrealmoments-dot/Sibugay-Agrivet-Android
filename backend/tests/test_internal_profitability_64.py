"""
Iteration 64: Internal Profitability Dashboard Widget - Backend Tests
Tests the GET /internal-invoices/profitability endpoint with period filter and per-branch aggregation.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInternalProfitability:
    """Tests for internal profitability endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as admin and get token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # === Period Filter Tests ===
    
    def test_profitability_this_month(self, headers):
        """Test profitability endpoint with this_month period"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "this_month"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "period" in data
        assert data["period"] == "this_month"
        assert "branches" in data
        assert "totals" in data
        
        # Check totals structure
        totals = data["totals"]
        assert "revenue" in totals
        assert "cost" in totals
        assert "net" in totals
        assert "invoice_count" in totals
        print(f"PASS: this_month - Revenue: {totals['revenue']}, Cost: {totals['cost']}, Net: {totals['net']}")
    
    def test_profitability_last_month(self, headers):
        """Test profitability endpoint with last_month period"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "last_month"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period"] == "last_month"
        assert "branches" in data
        assert "totals" in data
        print(f"PASS: last_month - {len(data['branches'])} branches, {data['totals']['invoice_count']} invoices")
    
    def test_profitability_quarter(self, headers):
        """Test profitability endpoint with quarter period"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "quarter"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period"] == "quarter"
        assert "branches" in data
        assert "totals" in data
        print(f"PASS: quarter - {len(data['branches'])} branches, {data['totals']['invoice_count']} invoices")
    
    def test_profitability_year(self, headers):
        """Test profitability endpoint with year period"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "year"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period"] == "year"
        assert "branches" in data
        assert "totals" in data
        print(f"PASS: year - {len(data['branches'])} branches, {data['totals']['invoice_count']} invoices")
    
    # === Branch Data Validation ===
    
    def test_branch_data_structure(self, headers):
        """Test that branch data has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "this_month"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # If there are branches with data, validate structure
        if data["branches"]:
            branch = data["branches"][0]
            required_fields = ["branch_id", "branch_name", "revenue", "cost", "profit"]
            for field in required_fields:
                assert field in branch, f"Missing field: {field}"
            
            # Validate profit calculation
            expected_profit = round(branch["revenue"] - branch["cost"], 2)
            assert branch["profit"] == expected_profit, f"Profit mismatch: {branch['profit']} != {expected_profit}"
            print(f"PASS: Branch '{branch['branch_name']}' - Revenue: {branch['revenue']}, Cost: {branch['cost']}, Profit: {branch['profit']}")
    
    def test_profit_centers_vs_cost_centers(self, headers):
        """Test that branches are correctly categorized as profit/cost centers"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "this_month"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        profit_centers = [b for b in data["branches"] if b["profit"] > 0]
        cost_centers = [b for b in data["branches"] if b["profit"] < 0]
        
        for b in profit_centers:
            print(f"  Profit center: {b['branch_name']} = +{b['profit']}")
        for b in cost_centers:
            print(f"  Cost center: {b['branch_name']} = {b['profit']}")
        
        # Net at company level should be close to zero (internal transfers)
        totals = data["totals"]
        assert totals["net"] == 0.0 or abs(totals["net"]) < 0.01, f"Net should be ~0 for internal transfers: {totals['net']}"
        print(f"PASS: Net at company level = {totals['net']} (expected ~0)")
    
    def test_branches_sorted_by_profit(self, headers):
        """Test that branches are sorted by profit descending"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            params={"period": "this_month"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        branches = data["branches"]
        if len(branches) > 1:
            for i in range(len(branches) - 1):
                assert branches[i]["profit"] >= branches[i + 1]["profit"], \
                    f"Branches not sorted by profit: {branches[i]['profit']} < {branches[i + 1]['profit']}"
            print(f"PASS: {len(branches)} branches sorted by profit descending")
    
    # === Edge Cases ===
    
    def test_default_period(self, headers):
        """Test profitability endpoint without period param (defaults to this_month)"""
        response = requests.get(
            f"{BASE_URL}/api/internal-invoices/profitability",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "this_month"
        print("PASS: Default period is this_month")
    
    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected"""
        response = requests.get(f"{BASE_URL}/api/internal-invoices/profitability")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Unauthenticated request rejected")
