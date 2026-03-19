"""
Test suite for AgriDocs Phase 2 — QR Phone Upload Page
Tests the public /doc-upload/:token flow (no auth required):
- POST /api/documents/qr-upload-token — generate token (requires auth)
- GET /api/documents/qr-upload/{token} — public preview
- POST /api/documents/qr-upload/{token} — public file upload
- Token expiry and single-use behavior
"""
import pytest
import requests
import os
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"


class TestQRPhoneUploadPhase2:
    """Test QR-based phone upload functionality for AgriDocs Phase 2"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for generating QR upload tokens"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Auth failed: {response.text}"
        return response.json().get("token")
    
    # ─────────────────────────────────────────────────────────────────────────
    # POST /api/documents/qr-upload-token — Generate QR token (auth required)
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_generate_qr_token_success(self, auth_token):
        """Test generating a QR upload token with full context"""
        response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "employer_compliance",
                "sub_category": "sss_contributions",
                "branch_id": "",
                "year": 2026,
                "coverage_months": [1, 2, 3]
            }
        )
        assert response.status_code == 200, f"Token generation failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing 'token'"
        assert "expires_at" in data, "Response missing 'expires_at'"
        assert data.get("category_label") == "Employer & Employee Compliance"
        assert data.get("sub_category_label") == "SSS Contributions"
        
        # Store for next tests
        self.__class__.test_token = data["token"]
        print(f"Generated QR token: {data['token'][:20]}...")
    
    def test_generate_qr_token_requires_auth(self):
        """Test that generating token without auth fails"""
        response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            json={
                "category": "employer_compliance",
                "sub_category": "sss_contributions"
            }
        )
        assert response.status_code in [401, 403], "Should require authentication"
    
    # ─────────────────────────────────────────────────────────────────────────
    # GET /api/documents/qr-upload/{token} — Public preview (no auth)
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_qr_upload_preview_success(self, auth_token):
        """Test getting upload context from valid token (no auth required)"""
        # First generate a fresh token
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "employer_compliance",
                "sub_category": "philhealth_contributions",
                "branch_id": "",
                "year": 2026,
                "coverage_months": [4, 5, 6]
            }
        )
        token = gen_response.json()["token"]
        
        # Access preview WITHOUT auth
        response = requests.get(f"{BASE_URL}/api/documents/qr-upload/{token}")
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        assert data["category_label"] == "Employer & Employee Compliance"
        assert data["sub_category_label"] == "PhilHealth RF-1 / Remittance"
        assert data["year"] == 2026
        assert data["coverage_months"] == [4, 5, 6]
        assert data.get("expired") == False
        print(f"Preview shows: {data['category_label']} / {data['sub_category_label']}")
    
    def test_qr_upload_preview_invalid_token(self):
        """Test accessing preview with invalid token returns 404"""
        response = requests.get(f"{BASE_URL}/api/documents/qr-upload/invalid-token-12345")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    # ─────────────────────────────────────────────────────────────────────────
    # POST /api/documents/qr-upload/{token} — Public file upload (no auth)
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_qr_upload_file_success(self, auth_token):
        """Test uploading a file via QR token (no auth required)"""
        # Generate a fresh token
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "employer_compliance",
                "sub_category": "sss_contributions",
                "branch_id": "",
                "year": 2026,
                "coverage_months": [1, 2, 3]
            }
        )
        token = gen_response.json()["token"]
        
        # Create a test file (PNG image)
        test_file_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Minimal PNG-like header
        files = {
            'files': ('test_sss_contribution.png', io.BytesIO(test_file_content), 'image/png')
        }
        
        # Upload WITHOUT auth
        response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/{token}",
            files=files
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        
        data = response.json()
        assert data.get("uploaded") == 1
        assert "document_id" in data
        assert "document_name" in data
        # Document name should be auto-generated: "SSS Contributions 2026 (January, February, March)"
        assert "SSS Contributions" in data["document_name"]
        assert "2026" in data["document_name"]
        assert "January" in data["document_name"] or "Jan" in data["document_name"]
        
        # Store document_id for cleanup/verification
        self.__class__.uploaded_doc_id = data["document_id"]
        print(f"Uploaded document: {data['document_name']} (ID: {data['document_id']})")
    
    def test_qr_upload_file_invalid_token(self):
        """Test uploading file with invalid token returns 404"""
        test_file_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        files = {'files': ('test.png', io.BytesIO(test_file_content), 'image/png')}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/invalid-token-xyz",
            files=files
        )
        assert response.status_code == 404
    
    # ─────────────────────────────────────────────────────────────────────────
    # Token single-use behavior — token expires after first upload
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_token_single_use_expired_after_upload(self, auth_token):
        """Test that token becomes expired after first upload (single-use)"""
        # Generate a fresh token
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "bir",
                "sub_category": "1601c",
                "year": 2026,
                "coverage_months": [7]
            }
        )
        token = gen_response.json()["token"]
        
        # First upload should succeed
        test_file = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        files = {'files': ('withholding_tax.png', io.BytesIO(test_file), 'image/png')}
        
        first_upload = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/{token}",
            files=files
        )
        assert first_upload.status_code == 200, "First upload should succeed"
        
        # Second attempt — GET preview should return 410 (expired)
        preview_after = requests.get(f"{BASE_URL}/api/documents/qr-upload/{token}")
        assert preview_after.status_code == 410, f"Token should be expired (410), got {preview_after.status_code}"
        
        # Second upload should also fail
        files2 = {'files': ('second_try.png', io.BytesIO(test_file), 'image/png')}
        second_upload = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/{token}",
            files=files2
        )
        assert second_upload.status_code == 410, "Second upload should fail (expired token)"
        print("Token correctly became single-use (expired after first upload)")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Verify uploaded document has correct metadata and tags
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_uploaded_doc_has_qr_upload_tag(self, auth_token):
        """Test that documents uploaded via QR have 'qr-upload' tag"""
        # Generate and upload
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "employer_compliance",
                "sub_category": "pagibig_contributions",
                "year": 2026,
                "coverage_months": [8, 9]
            }
        )
        token = gen_response.json()["token"]
        
        test_file = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        files = {'files': ('pagibig.png', io.BytesIO(test_file), 'image/png')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/{token}",
            files=files
        )
        doc_id = upload_response.json()["document_id"]
        
        # Fetch the document (with auth) and verify tags
        doc_response = requests.get(
            f"{BASE_URL}/api/documents/{doc_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert doc_response.status_code == 200
        
        doc = doc_response.json()
        assert "qr-upload" in doc.get("tags", []), "Document should have 'qr-upload' tag"
        assert doc["description"] == "Uploaded via phone (QR)"
        assert "r2_key" in doc["files"][0], "File should have R2 key"
        print(f"Document tags: {doc['tags']}, r2_key present: {'r2_key' in doc['files'][0]}")
        
        # Store for cleanup
        self.__class__.doc_to_cleanup = doc_id
    
    # ─────────────────────────────────────────────────────────────────────────
    # Test document auto-naming
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_document_auto_naming_monthly(self, auth_token):
        """Test document auto-naming for monthly documents"""
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "category": "employer_compliance",
                "sub_category": "sss_contributions",
                "year": 2026,
                "coverage_months": [10, 11, 12]  # Oct, Nov, Dec
            }
        )
        token = gen_response.json()["token"]
        
        test_file = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        files = {'files': ('sss_q4.png', io.BytesIO(test_file), 'image/png')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload/{token}",
            files=files
        )
        
        doc_name = upload_response.json()["document_name"]
        # Expected: "SSS Contributions 2026 (October, November, December)"
        assert "SSS Contributions" in doc_name
        assert "2026" in doc_name
        # At least one month name should be present
        assert any(m in doc_name for m in ["October", "November", "December"]), f"Month not in name: {doc_name}"
        print(f"Auto-generated name: {doc_name}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup — delete test documents
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_cleanup_test_documents(self, auth_token):
        """Cleanup: Delete test documents created during testing"""
        # List recent documents and delete those with 'qr-upload' tag that we created
        response = requests.get(
            f"{BASE_URL}/api/documents?search=qr-upload&limit=20",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if response.status_code == 200:
            docs = response.json().get("documents", [])
            deleted_count = 0
            for doc in docs:
                # Delete only our test documents (uploaded via QR)
                if "qr-upload" in doc.get("tags", []):
                    del_response = requests.delete(
                        f"{BASE_URL}/api/documents/{doc['id']}",
                        headers={"Authorization": f"Bearer {auth_token}"}
                    )
                    if del_response.status_code in [200, 204]:
                        deleted_count += 1
            print(f"Cleanup: Deleted {deleted_count} test documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
