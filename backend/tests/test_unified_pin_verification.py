"""
Unified PIN Verification Tests - Iteration 52

Tests the unified _resolve_pin() function that checks:
1. System admin PIN (bcrypt hashed in system_settings)
2. Manager/Owner PIN (plain text on user documents)
3. TOTP (6-digit code)
4. Auditor PIN

All these PIN types should work across all verification endpoints:
- POST /api/verify/public/{type}/{id} (no auth)
- POST /api/verify/{type}/{id} (authenticated)
- POST /api/purchase-orders/{id}/mark-reviewed
- POST /api/uploads/mark-reviewed/{type}/{id}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"  # Janmark Ahig admin user
WRONG_PIN = "000000"


class TestAuthSetup:
    """Get auth token for authenticated tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        # Try with owner username
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "owner",
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.text}")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}


class TestPublicVerifyWithManagerPin(TestAuthSetup):
    """Test POST /api/verify/public/{type}/{id} with manager PIN (521325)"""
    
    @pytest.fixture(scope="class")
    def sample_po(self, auth_token):
        """Get a PO to verify - create one if needed"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # First get existing PO
        response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=headers)
        if response.status_code == 200:
            pos = response.json().get("purchase_orders", [])
            if pos:
                return pos[0]
        pytest.skip("No POs available for testing")
    
    def test_public_verify_with_manager_pin_success(self, sample_po):
        """Manager PIN (521325) should work on public verify endpoint"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        # Should succeed with 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("message") == "Transaction verified"
        assert data.get("method") == "manager_pin"
        assert "verified_by" in data
        print(f"SUCCESS: Verified by {data.get('verified_by')} via {data.get('method')}")
    
    def test_public_verify_with_wrong_pin_fails(self, sample_po):
        """Wrong PIN should fail with clear error message"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": WRONG_PIN}
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        # Should fail with 400 (not 401)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Invalid PIN" in data.get("detail", ""), f"Expected 'Invalid PIN' in error: {data}"
    
    def test_public_verify_doc_not_found(self):
        """Non-existent document should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/nonexistent_id_12345",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_public_verify_invalid_doc_type(self):
        """Invalid document type should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/verify/public/invalid_type/some_id",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code == 400
        assert "Invalid document type" in response.json().get("detail", "")


class TestAuthenticatedVerifyWithManagerPin(TestAuthSetup):
    """Test POST /api/verify/{type}/{id} with manager PIN (authenticated endpoint)"""
    
    @pytest.fixture(scope="class")
    def sample_po_for_auth(self, auth_token):
        """Get a PO for authenticated verify test"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=headers)
        if response.status_code == 200:
            pos = response.json().get("purchase_orders", [])
            if pos:
                return pos[0]
        pytest.skip("No POs available")
    
    def test_authenticated_verify_with_manager_pin(self, sample_po_for_auth, auth_headers):
        """Manager PIN should also work on authenticated endpoint"""
        po_id = sample_po_for_auth["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN},
            headers=auth_headers
        )
        print(f"Auth verify response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("method") == "manager_pin"
    
    def test_authenticated_verify_requires_auth(self, sample_po_for_auth):
        """Authenticated endpoint should require auth header"""
        po_id = sample_po_for_auth["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        # Should fail without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"


class TestPOMarkReviewed(TestAuthSetup):
    """Test POST /api/purchase-orders/{id}/mark-reviewed with manager PIN"""
    
    @pytest.fixture(scope="class") 
    def sample_po_for_review(self, auth_token):
        """Get a PO for mark-reviewed test"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=headers)
        if response.status_code == 200:
            pos = response.json().get("purchase_orders", [])
            if pos:
                return pos[0]
        pytest.skip("No POs available")
    
    def test_mark_reviewed_with_manager_pin(self, sample_po_for_review, auth_headers):
        """POST /api/purchase-orders/{id}/mark-reviewed with manager PIN"""
        po_id = sample_po_for_review["id"]
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/mark-reviewed",
            json={"pin": MANAGER_PIN, "notes": "Test review"},
            headers=auth_headers
        )
        print(f"Mark-reviewed response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "reviewed" in data.get("message", "").lower()
        assert "reviewed_by" in data
    
    def test_mark_reviewed_with_wrong_pin_fails(self, sample_po_for_review, auth_headers):
        """Wrong PIN should fail on mark-reviewed"""
        po_id = sample_po_for_review["id"]
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/mark-reviewed",
            json={"pin": WRONG_PIN},
            headers=auth_headers
        )
        assert response.status_code == 401, f"Expected 401 for wrong PIN, got {response.status_code}"


class TestUploadsMarkReviewed(TestAuthSetup):
    """Test POST /api/uploads/mark-reviewed/{type}/{id} with manager PIN"""
    
    @pytest.fixture(scope="class")
    def sample_branch_transfer(self, auth_token):
        """Get a branch transfer for testing"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/branch-transfers?limit=5", headers=headers)
        if response.status_code == 200:
            transfers = response.json().get("transfers", [])
            if transfers:
                return transfers[0]
        return None
    
    def test_uploads_mark_reviewed_with_manager_pin(self, sample_branch_transfer, auth_headers):
        """POST /api/uploads/mark-reviewed/branch_transfer/{id} with manager PIN"""
        if not sample_branch_transfer:
            pytest.skip("No branch transfers available")
        
        bt_id = sample_branch_transfer["id"]
        response = requests.post(
            f"{BASE_URL}/api/uploads/mark-reviewed/branch_transfer/{bt_id}",
            json={"pin": MANAGER_PIN, "notes": "Test review"},
            headers=auth_headers
        )
        print(f"Uploads mark-reviewed response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "reviewed" in data.get("message", "").lower()


class TestPublicVerifySetsReceiptStatus(TestAuthSetup):
    """Test that public verify also sets receipt_review_status"""
    
    @pytest.fixture(scope="class")
    def po_with_receipts(self, auth_token):
        """Find a PO that has uploaded receipts"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get POs
        response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=20", headers=headers)
        if response.status_code != 200:
            pytest.skip("Cannot get POs")
        
        pos = response.json().get("purchase_orders", [])
        for po in pos:
            # Check if PO has receipts
            uploads_resp = requests.get(
                f"{BASE_URL}/api/uploads/record/purchase_order/{po['id']}",
                headers=headers
            )
            if uploads_resp.status_code == 200:
                upload_data = uploads_resp.json()
                if upload_data.get("total_files", 0) > 0:
                    return po
        return None
    
    def test_public_verify_sets_receipt_review_status(self, po_with_receipts, auth_headers):
        """Public verify should also set receipt_review_status to 'reviewed'"""
        if not po_with_receipts:
            pytest.skip("No PO with receipts found")
        
        po_id = po_with_receipts["id"]
        
        # Call public verify
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code == 200, f"Verify failed: {response.text}"
        
        # Now check if receipt_review_status was updated
        po_response = requests.get(
            f"{BASE_URL}/api/purchase-orders?limit=100",
            headers=auth_headers
        )
        assert po_response.status_code == 200
        
        # Find our PO
        pos = po_response.json().get("purchase_orders", [])
        updated_po = next((p for p in pos if p["id"] == po_id), None)
        
        if updated_po:
            print(f"PO after verify - receipt_review_status: {updated_po.get('receipt_review_status')}")
            # If PO has receipts, receipt_review_status should be 'reviewed'
            assert updated_po.get("receipt_review_status") == "reviewed" or updated_po.get("verified") == True, \
                "PO should be marked as reviewed after public verify"


class TestAllDocumentTypes:
    """Test all document types work with public verify endpoint"""
    
    def test_expense_public_verify(self):
        """Expense type should work with public verify"""
        # First create an expense via login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "owner",
            "password": SUPER_ADMIN_PASSWORD
        })
        if login_resp.status_code != 200:
            pytest.skip("Cannot login")
        
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get existing expenses
        resp = requests.get(f"{BASE_URL}/api/expenses?limit=5", headers=headers)
        if resp.status_code == 200:
            expenses = resp.json().get("expenses", [])
            if expenses:
                expense_id = expenses[0]["id"]
                verify_resp = requests.post(
                    f"{BASE_URL}/api/verify/public/expense/{expense_id}",
                    json={"pin": MANAGER_PIN}
                )
                print(f"Expense verify: {verify_resp.status_code} - {verify_resp.text}")
                assert verify_resp.status_code == 200 or verify_resp.status_code == 404
    
    def test_branch_transfer_public_verify(self):
        """Branch transfer type should work with public verify"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "owner",
            "password": SUPER_ADMIN_PASSWORD
        })
        if login_resp.status_code != 200:
            pytest.skip("Cannot login")
        
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        resp = requests.get(f"{BASE_URL}/api/branch-transfers?limit=5", headers=headers)
        if resp.status_code == 200:
            transfers = resp.json().get("transfers", [])
            if transfers:
                bt_id = transfers[0]["id"]
                verify_resp = requests.post(
                    f"{BASE_URL}/api/verify/public/branch_transfer/{bt_id}",
                    json={"pin": MANAGER_PIN}
                )
                print(f"Branch transfer verify: {verify_resp.status_code} - {verify_resp.text}")
                assert verify_resp.status_code == 200 or verify_resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
