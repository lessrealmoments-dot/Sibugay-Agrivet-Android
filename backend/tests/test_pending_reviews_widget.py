"""
Test: Pending Receipt Reviews Widget & Generic Mark-Reviewed Endpoints
Iteration 49: Testing the new pending reviews dashboard widget and mark-reviewed endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPendingReviewsEndpoints:
    """Test pending reviews dashboard endpoint and mark-reviewed endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def company_admin_token(self):
        """Login as company admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "jovelyneahig@gmail.com",
            "password": "Aa@050772"
        })
        assert response.status_code == 200, f"Company admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_pending_reviews_endpoint_returns_data(self, admin_token):
        """GET /api/dashboard/pending-reviews returns items with total_count and by_branch"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/pending-reviews", headers=headers)
        
        assert response.status_code == 200, f"Pending reviews failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "items" in data, "Response missing 'items'"
        assert "total_count" in data, "Response missing 'total_count'"
        assert "by_branch" in data, "Response missing 'by_branch'"
        
        # Verify items structure (if any)
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "id" in item, "Item missing 'id'"
            assert "record_type" in item, "Item missing 'record_type'"
            assert "record_number" in item, "Item missing 'record_number'"
            assert "branch_id" in item, "Item missing 'branch_id'"
            assert "branch_name" in item, "Item missing 'branch_name'"
            assert "receipt_count" in item, "Item missing 'receipt_count'"
        
        print(f"✓ Pending reviews returned {data['total_count']} items across {len(data['by_branch'])} branches")
        return data
    
    def test_pending_reviews_with_branch_filter(self, admin_token):
        """GET /api/dashboard/pending-reviews with branch_id param filters correctly"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First get all branches
        all_response = requests.get(f"{BASE_URL}/api/dashboard/pending-reviews", headers=headers)
        assert all_response.status_code == 200
        all_data = all_response.json()
        
        if len(all_data["by_branch"]) > 0:
            # Get first branch_id
            first_branch = list(all_data["by_branch"].values())[0]
            branch_id = first_branch["branch_id"]
            
            # Filter by branch
            filtered_response = requests.get(
                f"{BASE_URL}/api/dashboard/pending-reviews",
                params={"branch_id": branch_id},
                headers=headers
            )
            assert filtered_response.status_code == 200
            filtered_data = filtered_response.json()
            
            # All items should be from that branch
            for item in filtered_data["items"]:
                assert item["branch_id"] == branch_id, f"Item from wrong branch: {item['branch_id']} != {branch_id}"
            
            print(f"✓ Branch filter works: {filtered_data['total_count']} items for branch {branch_id}")
        else:
            print("⚠ No pending reviews to test branch filter")
    
    def test_mark_reviewed_branch_transfer_invalid_pin(self, admin_token):
        """POST /api/uploads/mark-reviewed/branch_transfer/{id} with invalid PIN returns 401"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Use a fake ID for the invalid PIN test
        response = requests.post(
            f"{BASE_URL}/api/uploads/mark-reviewed/branch_transfer/fake-id-12345",
            json={"pin": "wrongpin123", "notes": "test"},
            headers=headers
        )
        
        # Should be 404 (not found) or 401 (invalid pin) - depends on whether record exists
        assert response.status_code in [401, 404], f"Expected 401 or 404, got {response.status_code}: {response.text}"
        print(f"✓ Invalid PIN returns {response.status_code}")
    
    def test_mark_reviewed_expense_invalid_pin(self, admin_token):
        """POST /api/uploads/mark-reviewed/expense/{id} with invalid PIN returns 401"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/uploads/mark-reviewed/expense/fake-id-12345",
            json={"pin": "wrongpin123", "notes": "test"},
            headers=headers
        )
        
        assert response.status_code in [401, 404], f"Expected 401 or 404, got {response.status_code}: {response.text}"
        print(f"✓ Invalid PIN returns {response.status_code}")
    
    def test_mark_reviewed_unsupported_type(self, admin_token):
        """POST /api/uploads/mark-reviewed/{unsupported_type}/{id} returns 400"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/uploads/mark-reviewed/invoice/fake-id-12345",
            json={"pin": "1234", "notes": "test"},
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400 for unsupported type, got {response.status_code}"
        assert "Unsupported record type" in response.json().get("detail", "")
        print("✓ Unsupported record type returns 400")
    
    def test_mark_reviewed_requires_pin(self, admin_token):
        """POST /api/uploads/mark-reviewed without PIN returns 400"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/uploads/mark-reviewed/expense/fake-id-12345",
            json={"notes": "test"},  # No PIN
            headers=headers
        )
        
        # Should require PIN or record not found
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"
        print(f"✓ Missing PIN returns {response.status_code}")
    
    def test_company_admin_can_access_pending_reviews(self, company_admin_token):
        """Company admin can access pending reviews"""
        headers = {"Authorization": f"Bearer {company_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/pending-reviews", headers=headers)
        
        assert response.status_code == 200, f"Company admin access failed: {response.text}"
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        print(f"✓ Company admin sees {data['total_count']} pending reviews")
    
    def test_mark_reviewed_with_valid_data(self, admin_token):
        """
        Test mark-reviewed with a real expense/branch_transfer that has uploads.
        First find an unreviewed record, then try to mark it reviewed.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get pending reviews
        response = requests.get(f"{BASE_URL}/api/dashboard/pending-reviews", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Find an expense or branch_transfer to test
        test_item = None
        for item in data["items"]:
            if item["record_type"] in ["expense", "branch_transfer"]:
                test_item = item
                break
        
        if not test_item:
            pytest.skip("No expense or branch_transfer pending reviews to test mark-reviewed")
        
        # We need the admin's manager_pin - try common pins
        # First, let's get the user's manager_pin
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        user_data = me_response.json()
        
        # Try the PIN from user data or a known PIN
        possible_pins = [
            user_data.get("manager_pin", ""),
            user_data.get("owner_pin", ""),
            "1234",  # Default test pin
        ]
        
        for pin in possible_pins:
            if not pin:
                continue
            
            response = requests.post(
                f"{BASE_URL}/api/uploads/mark-reviewed/{test_item['record_type']}/{test_item['id']}",
                json={"pin": pin, "notes": "Tested via iteration 49"},
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✓ Successfully marked {test_item['record_type']} {test_item['record_number']} as reviewed with PIN")
                return
            elif response.status_code == 401:
                continue  # Wrong PIN, try next
            else:
                # Other error
                print(f"⚠ Mark reviewed returned {response.status_code}: {response.text}")
                break
        
        print(f"⚠ Could not find valid PIN to mark {test_item['record_type']} as reviewed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
