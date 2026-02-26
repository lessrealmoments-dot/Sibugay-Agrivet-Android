"""
Test public verify endpoint for transaction verification from phone.
Iteration 51 - Bug fixes for QR dialog close and TOTP unauthorized error.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPublicVerifyEndpoint:
    """Tests for POST /api/verify/public/{doc_type}/{doc_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.headers = {"Content-Type": "application/json"}
    
    def test_invalid_pin_returns_400_not_401(self):
        """
        Bug fix verification: Wrong PIN should return 400 'Invalid PIN' 
        not 401 Unauthorized (no auth header needed)
        """
        # First get a valid PO ID by logging in
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"},
            headers=self.headers
        )
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        
        # Get a purchase order ID
        po_resp = requests.get(
            f"{BASE_URL}/api/purchase-orders?limit=1",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert po_resp.status_code == 200
        pos = po_resp.json().get("purchase_orders", [])
        assert len(pos) > 0
        po_id = pos[0]["id"]
        
        # Now test PUBLIC endpoint with wrong PIN (no auth header)
        verify_resp = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/{po_id}",
            json={"pin": "wrong_pin_123"},
            headers=self.headers  # No Authorization header
        )
        
        # Should return 400, NOT 401
        assert verify_resp.status_code == 400, f"Expected 400, got {verify_resp.status_code}"
        assert "Invalid PIN" in verify_resp.json().get("detail", "")
    
    def test_public_verify_without_auth_header(self):
        """Public endpoint should work without Authorization header"""
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/nonexistent_id",
            json={"pin": "1234"},
            headers=self.headers  # No Authorization header
        )
        # Should get 404 (not found) not 401 (unauthorized)
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_invalid_document_type_returns_400(self):
        """Invalid document type should return 400 with descriptive error"""
        response = requests.post(
            f"{BASE_URL}/api/verify/public/invalid_type/some_id",
            json={"pin": "1234"},
            headers=self.headers
        )
        assert response.status_code == 400
        assert "Invalid document type" in response.json().get("detail", "")
    
    def test_valid_document_types_accepted(self):
        """All three valid document types should be accepted"""
        valid_types = ["purchase_order", "expense", "branch_transfer"]
        
        for doc_type in valid_types:
            response = requests.post(
                f"{BASE_URL}/api/verify/public/{doc_type}/nonexistent_id",
                json={"pin": "1234"},
                headers=self.headers
            )
            # Should get 404 (doc not found) not 400 (invalid type)
            assert response.status_code == 404, f"Type {doc_type}: Expected 404, got {response.status_code}"
    
    def test_nonexistent_document_returns_404(self):
        """Non-existent document ID should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/verify/public/purchase_order/nonexistent_id_12345",
            json={"pin": "1234"},
            headers=self.headers
        )
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()


class TestAuthenticatedVerifyEndpoint:
    """Tests for authenticated POST /api/verify/{doc_type}/{doc_id}"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "janmarkeahig@gmail.com", "password": "Aa@58798546521325"},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_authenticated_verify_requires_auth(self):
        """Authenticated endpoint should require Authorization header"""
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/some_id",
            json={"pin": "1234"},
            headers={"Content-Type": "application/json"}  # No auth header
        )
        # Should get 401 or 403 (requires auth)
        assert response.status_code in [401, 403]
    
    def test_authenticated_verify_with_auth_header(self, auth_token):
        """Authenticated endpoint should work with valid auth header"""
        response = requests.post(
            f"{BASE_URL}/api/verify/purchase_order/nonexistent_id",
            json={"pin": "wrong_pin"},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}"
            }
        )
        # Should get 404 (not found) since we have valid auth but doc doesn't exist
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
