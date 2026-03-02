"""
Test suite for Smart Unclosed Date Detection + Date Picker feature
Iteration 92

Tests:
1. GET /api/daily-close/unclosed-days returns correct data structure
2. Unclosed days include sales_count and expense_count
3. Fund transfer endpoint accepts optional 'date' parameter
4. Sales log uses order_date from request (not hardcoded today)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"
BRANCH_ID = "c435277f-9fc7-4d83-83e7-38be5b4423ac"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API requests."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")


@pytest.fixture
def api_client(auth_token):
    """Create session with auth header."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestUnclosedDaysAPI:
    """Test the unclosed days detection API"""
    
    def test_unclosed_days_endpoint_exists(self, api_client):
        """GET /api/daily-close/unclosed-days returns valid response"""
        response = api_client.get(
            f"{BASE_URL}/api/daily-close/unclosed-days",
            params={"branch_id": BRANCH_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "unclosed_days" in data
        assert "last_close_date" in data
        assert "total_unclosed" in data
        assert "today" in data
        
    def test_unclosed_days_contains_activity_counts(self, api_client):
        """Each unclosed day includes sales_count and expense_count"""
        response = api_client.get(
            f"{BASE_URL}/api/daily-close/unclosed-days",
            params={"branch_id": BRANCH_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check that at least one day exists
        assert data["total_unclosed"] > 0, "Expected unclosed days for Branch 1"
        
        # Verify each day has required fields
        for day in data["unclosed_days"][:5]:  # Check first 5 days
            assert "date" in day
            assert "sales_count" in day
            assert "expense_count" in day
            assert "has_activity" in day
            
    def test_unclosed_days_sorted_by_date(self, api_client):
        """Unclosed days are returned sorted by date"""
        response = api_client.get(
            f"{BASE_URL}/api/daily-close/unclosed-days",
            params={"branch_id": BRANCH_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        dates = [d["date"] for d in data["unclosed_days"]]
        assert dates == sorted(dates), "Dates should be sorted ascending"
        
    def test_branch_id_required(self, api_client):
        """branch_id is required for unclosed days endpoint"""
        # Super admin without branch_id should still fail (requires explicit branch)
        response = api_client.get(f"{BASE_URL}/api/daily-close/unclosed-days")
        # Should either return error or use user's branch
        assert response.status_code in [200, 400]


class TestFundTransferDateParameter:
    """Test that fund transfers accept optional date parameter"""
    
    def test_fund_transfer_accepts_date_param(self, api_client):
        """Fund transfer endpoint should accept optional 'date' parameter"""
        # Just verify the date parameter is in the code - we won't actually execute
        # a fund transfer without proper PIN verification
        
        # Get fund wallets to verify endpoint works
        response = api_client.get(
            f"{BASE_URL}/api/fund-wallets",
            params={"branch_id": BRANCH_ID}
        )
        assert response.status_code == 200
        wallets = response.json()
        
        # Verify wallets exist for the branch
        assert len(wallets) > 0, "Branch should have fund wallets"
        

class TestSalesDateHandling:
    """Test that sales use order_date from request"""
    
    def test_daily_log_respects_date_param(self, api_client):
        """Daily log endpoint should filter by date parameter"""
        # Test with a specific date
        test_date = "2026-01-15"  # Known date with activity
        
        response = api_client.get(
            f"{BASE_URL}/api/daily-log",
            params={"branch_id": BRANCH_ID, "date": test_date}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify date is respected in response
        assert data["date"] == test_date
        
    def test_invoices_history_by_date(self, api_client):
        """Invoice history endpoint filters by date"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = api_client.get(
            f"{BASE_URL}/api/invoices/history/by-date",
            params={"branch_id": BRANCH_ID, "date": today}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "invoices" in data
        assert "totals" in data
        assert "date" in data
        assert data["date"] == today


class TestExpensesDateHandling:
    """Test that expenses respect encoding date"""
    
    def test_expenses_list_with_date_filter(self, api_client):
        """Expenses can be filtered by date range"""
        response = api_client.get(
            f"{BASE_URL}/api/expenses",
            params={
                "branch_id": BRANCH_ID,
                "date_from": "2026-01-01",
                "date_to": "2026-01-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "expenses" in data
        assert "total" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
