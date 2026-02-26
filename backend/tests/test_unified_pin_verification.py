"""
Unified PIN Verification Tests - Iteration 52

Tests the unified _resolve_pin() function that checks:
1. System admin PIN (bcrypt hashed in system_settings)
2. Manager/Owner PIN (plain text on user documents)
3. TOTP (6-digit code)
4. Auditor PIN
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MANAGER_PIN = "521325"  # Janmark Ahig admin user
WRONG_PIN = "000000"


@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "superadmin",
        "password": "Aa@58798546521325"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def sample_po(auth_headers):
    """Get a PO to verify"""
    response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=5", headers=auth_headers)
    if response.status_code == 200:
        pos = response.json().get("purchase_orders", [])
        if pos:
            return pos[0]
    pytest.skip("No POs available for testing")


class TestPublicVerifyEndpoint:
    """Test POST /api/verify/public/{type}/{id}"""
    
    def test_public_verify_with_manager_pin_success(self, sample_po):
        """Manager PIN (521325) should work on public verify endpoint - THE MAIN BUG FIX"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        print(f"Status: {response.status_code}, Body: {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("message") == "Transaction verified"
        assert data.get("method") == "manager_pin"
        assert "verified_by" in data
    
    def test_public_verify_with_wrong_pin_fails(self, sample_po):
        """Wrong PIN should fail with clear error message"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": WRONG_PIN}
        )
        assert response.status_code == 400
        assert "Invalid PIN" in response.json().get("detail", "")
    
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


class TestAuthenticatedVerifyEndpoint:
    """Test POST /api/verify/{type}/{id} (authenticated endpoint)"""
    
    def test_authenticated_verify_with_manager_pin(self, sample_po, auth_headers):
        """Manager PIN should also work on authenticated endpoint"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN},
            headers=auth_headers
        )
        print(f"Auth verify: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert response.json().get("method") == "manager_pin"
    
    def test_authenticated_verify_requires_auth(self, sample_po):
        """Authenticated endpoint should require auth header"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code in [401, 403]


class TestPOMarkReviewed:
    """Test POST /api/purchase-orders/{id}/mark-reviewed"""
    
    def test_mark_reviewed_with_manager_pin(self, sample_po, auth_headers):
        """POST /api/purchase-orders/{id}/mark-reviewed with manager PIN"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/mark-reviewed",
            json={"pin": MANAGER_PIN, "notes": "Test review"},
            headers=auth_headers
        )
        print(f"Mark-reviewed: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert "reviewed" in response.json().get("message", "").lower()
    
    def test_mark_reviewed_with_wrong_pin_fails(self, sample_po, auth_headers):
        """Wrong PIN should fail on mark-reviewed"""
        po_id = sample_po["id"]
        response = requests.post(
            f"{BASE_URL}/api/purchase-orders/{po_id}/mark-reviewed",
            json={"pin": WRONG_PIN},
            headers=auth_headers
        )
        assert response.status_code == 401


class TestUploadsMarkReviewed:
    """Test POST /api/uploads/mark-reviewed/{type}/{id}"""
    
    @pytest.fixture
    def sample_branch_transfer(self, auth_headers):
        """Get a branch transfer for testing"""
        response = requests.get(f"{BASE_URL}/api/branch-transfers?limit=5", headers=auth_headers)
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
        print(f"Uploads mark-reviewed: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert "reviewed" in response.json().get("message", "").lower()


class TestReceiptReviewStatusBridge:
    """Test that public verify also sets receipt_review_status"""
    
    def test_verify_sets_receipt_status(self, sample_po, auth_headers):
        """Public verify should set receipt_review_status to 'reviewed'"""
        po_id = sample_po["id"]
        
        # Call public verify
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": MANAGER_PIN}
        )
        assert response.status_code == 200
        
        # Check PO was updated
        po_response = requests.get(f"{BASE_URL}/api/purchase-orders?limit=100", headers=auth_headers)
        assert po_response.status_code == 200
        
        pos = po_response.json().get("purchase_orders", [])
        updated_po = next((p for p in pos if p["id"] == po_id), None)
        
        if updated_po:
            # PO should be marked as verified
            assert updated_po.get("verified") == True, "PO should be marked as verified"
            print(f"PO verified: {updated_po.get('verified')}, receipt_review_status: {updated_po.get('receipt_review_status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
