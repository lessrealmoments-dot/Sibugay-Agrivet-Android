"""
Test QR Code Upload Feature for ReceiptUploadInline
Tests:
- POST /api/uploads/generate-pending-link (creates pending session with token)
- POST /api/uploads/generate-pending-link with existing session_id (adds token to existing session)
- GET /api/uploads/session-status/{session_id} (returns file_count and files list)
- GET /api/uploads/preview/{token} (returns record_summary for pending sessions)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestQRUploadFeature:
    """QR Code Upload Feature tests for pending sessions"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get authenticated headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # Test 1: Generate pending link creates new pending session with token
    def test_generate_pending_link_creates_new_session(self, auth_headers):
        """POST /api/uploads/generate-pending-link creates pending session with token"""
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link", 
            headers=auth_headers,
            json={
                "record_type": "purchase_order",
                "record_summary": {
                    "type_label": "Purchase Order",
                    "title": "PO-TEST-001",
                    "description": "Test Vendor · DR: 12345",
                    "amount": 15000
                }
            }
        )
        assert response.status_code == 200, f"Failed to generate pending link: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "token" in data, "Response missing 'token'"
        assert "session_id" in data, "Response missing 'session_id'"
        assert "record_id" in data, "Response missing 'record_id'"
        assert "expires_at" in data, "Response missing 'expires_at'"
        
        # Validate values
        assert len(data["token"]) > 20, "Token should be a secure random string"
        assert data["record_id"].startswith("pending_"), "Record ID should start with 'pending_'"
        
        print(f"✓ Created pending session: session_id={data['session_id']}, token={data['token'][:20]}...")
        return data
    
    # Test 2: Generate pending link with existing session_id adds token to existing session
    def test_generate_pending_link_with_existing_session(self, auth_headers):
        """POST /api/uploads/generate-pending-link with session_id adds token to existing session"""
        # First create a direct upload session (no token)
        import io
        files = {'files': ('test.jpg', io.BytesIO(b'test image content'), 'image/jpeg')}
        data = {'record_type': 'purchase_order'}
        direct_response = requests.post(f"{BASE_URL}/api/uploads/direct",
            headers={"Authorization": auth_headers["Authorization"]},
            files=files,
            data=data
        )
        assert direct_response.status_code == 200, f"Direct upload failed: {direct_response.text}"
        session_id = direct_response.json()["session_id"]
        print(f"  Created direct upload session: {session_id}")
        
        # Now generate a pending link for this existing session
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link",
            headers=auth_headers,
            json={
                "record_type": "purchase_order",
                "session_id": session_id,
                "record_summary": {
                    "type_label": "Purchase Order",
                    "title": "PO-EXISTING-001",
                    "description": "Existing session test"
                }
            }
        )
        assert response.status_code == 200, f"Failed to add token to existing session: {response.text}"
        data = response.json()
        
        # Session ID should remain the same
        assert data["session_id"] == session_id, "Session ID should not change"
        assert "token" in data, "Response should include new token"
        assert len(data["token"]) > 20, "Token should be valid"
        
        print(f"✓ Added token to existing session {session_id}, token={data['token'][:20]}...")
        return data
    
    # Test 3: Session status returns file_count and files list
    def test_session_status_returns_files(self, auth_headers):
        """GET /api/uploads/session-status/{session_id} returns file_count and files"""
        # Create a session with a file first
        import io
        files = {'files': ('status_test.jpg', io.BytesIO(b'test image content for status check'), 'image/jpeg')}
        data = {'record_type': 'purchase_order'}
        upload_response = requests.post(f"{BASE_URL}/api/uploads/direct",
            headers={"Authorization": auth_headers["Authorization"]},
            files=files,
            data=data
        )
        assert upload_response.status_code == 200
        session_id = upload_response.json()["session_id"]
        file_id = upload_response.json()["file_ids"][0]
        
        # Get session status
        response = requests.get(f"{BASE_URL}/api/uploads/session-status/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Session status failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert data["session_id"] == session_id, "Session ID should match"
        assert data["file_count"] == 1, "File count should be 1"
        assert "files" in data, "Response should include 'files' list"
        assert len(data["files"]) == 1, "Should have 1 file in list"
        
        # Validate file details
        file_info = data["files"][0]
        assert "id" in file_info, "File should have 'id'"
        assert "filename" in file_info, "File should have 'filename'"
        assert file_info["id"] == file_id, "File ID should match"
        
        print(f"✓ Session status returned: file_count={data['file_count']}, files={len(data['files'])}")
    
    # Test 4: Session status returns 404 for nonexistent session
    def test_session_status_nonexistent_session(self, auth_headers):
        """GET /api/uploads/session-status/{session_id} returns 404 for nonexistent"""
        response = requests.get(f"{BASE_URL}/api/uploads/session-status/nonexistent-session-123",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Session status returns 404 for nonexistent session")
    
    # Test 5: Preview endpoint returns record_summary for pending sessions
    def test_preview_returns_record_summary(self, auth_headers):
        """GET /api/uploads/preview/{token} returns record_summary with custom data"""
        # Create a pending session with custom summary
        custom_summary = {
            "type_label": "Purchase Order",
            "title": "PO-PREVIEW-TEST",
            "description": "Preview Test Vendor · DR: PREV123",
            "amount": 25000
        }
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link",
            headers=auth_headers,
            json={
                "record_type": "purchase_order",
                "record_summary": custom_summary
            }
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Get preview (public endpoint - no auth)
        preview_response = requests.get(f"{BASE_URL}/api/uploads/preview/{token}")
        assert preview_response.status_code == 200, f"Preview failed: {preview_response.text}"
        data = preview_response.json()
        
        # Validate response structure
        assert "record_summary" in data, "Response should have 'record_summary'"
        assert "file_count" in data, "Response should have 'file_count'"
        assert "max_files" in data, "Response should have 'max_files'"
        assert data["expired"] == False, "Link should not be expired"
        
        # Validate record_summary has custom data
        summary = data["record_summary"]
        assert summary.get("title") == "PO-PREVIEW-TEST", "Title should match custom summary"
        assert summary.get("description") == "Preview Test Vendor · DR: PREV123", "Description should match"
        assert summary.get("amount") == 25000, "Amount should match"
        
        print(f"✓ Preview returned record_summary: title={summary.get('title')}, amount={summary.get('amount')}")
    
    # Test 6: Preview returns 404 for invalid token
    def test_preview_invalid_token(self):
        """GET /api/uploads/preview/{token} returns 404 for invalid token"""
        response = requests.get(f"{BASE_URL}/api/uploads/preview/invalid-token-xyz123")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Preview returns 404 for invalid token")
    
    # Test 7: Generate pending link for different record types
    def test_generate_pending_link_for_expense(self, auth_headers):
        """POST /api/uploads/generate-pending-link works for expense record type"""
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link",
            headers=auth_headers,
            json={
                "record_type": "expense",
                "record_summary": {
                    "type_label": "Expense",
                    "title": "Office Supplies",
                    "description": "Operations · Cash",
                    "amount": 5000
                }
            }
        )
        assert response.status_code == 200, f"Failed for expense: {response.text}"
        data = response.json()
        assert "token" in data
        assert "session_id" in data
        print(f"✓ Generated pending link for expense: {data['token'][:20]}...")
    
    # Test 8: Generate pending link for branch_transfer
    def test_generate_pending_link_for_branch_transfer(self, auth_headers):
        """POST /api/uploads/generate-pending-link works for branch_transfer"""
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link",
            headers=auth_headers,
            json={
                "record_type": "branch_transfer",
                "record_summary": {
                    "type_label": "Branch Transfer",
                    "title": "BTO-001",
                    "description": "Main Branch → Sibugay Branch",
                    "amount": 10000
                }
            }
        )
        assert response.status_code == 200, f"Failed for branch_transfer: {response.text}"
        data = response.json()
        assert "token" in data
        assert "session_id" in data
        print(f"✓ Generated pending link for branch_transfer: {data['token'][:20]}...")


class TestPhoneUploadPage:
    """Tests for phone upload page public endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def pending_token(self, auth_token):
        """Create a pending session token for testing"""
        response = requests.post(f"{BASE_URL}/api/uploads/generate-pending-link",
            headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            json={
                "record_type": "purchase_order",
                "record_summary": {
                    "type_label": "Purchase Order",
                    "title": "PO-PHONE-TEST",
                    "description": "Phone Upload Test Vendor",
                    "amount": 12345.67
                }
            }
        )
        assert response.status_code == 200
        return response.json()["token"]
    
    # Test 9: Phone upload via token (public endpoint)
    def test_phone_upload_via_token(self, pending_token):
        """POST /api/uploads/upload/{token} works without auth"""
        import io
        files = {'files': ('phone_photo.jpg', io.BytesIO(b'simulated phone photo content'), 'image/jpeg')}
        response = requests.post(f"{BASE_URL}/api/uploads/upload/{pending_token}",
            files=files
        )
        assert response.status_code == 200, f"Phone upload failed: {response.text}"
        data = response.json()
        
        assert data["uploaded"] == 1, "Should upload 1 file"
        assert data["total_files"] >= 1, "Total files should be at least 1"
        
        print(f"✓ Phone upload successful: uploaded={data['uploaded']}, total={data['total_files']}")
    
    # Test 10: Phone upload with invalid token
    def test_phone_upload_invalid_token(self):
        """POST /api/uploads/upload/{token} returns 404 for invalid token"""
        import io
        files = {'files': ('test.jpg', io.BytesIO(b'test'), 'image/jpeg')}
        response = requests.post(f"{BASE_URL}/api/uploads/upload/invalid-token-abc",
            files=files
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Phone upload returns 404 for invalid token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
