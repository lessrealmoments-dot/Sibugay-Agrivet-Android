"""
Test suite for AgriDocs Business Document Cloud API (Phase 1)
Tests document CRUD, categories, QR upload tokens, and compliance summary endpoints.
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASS = "Aa@58798546521325"


@pytest.fixture(scope="module")
def auth_headers():
    """Authenticate and return authorization headers."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASS
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    token = data.get("access_token") or data.get("token")
    assert token, "No token in login response"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_document_id(auth_headers):
    """Create a test document for CRUD operations and return its ID."""
    # Create a simple test file
    test_content = b"TEST PDF CONTENT"
    files = [('files', ('test_document.pdf', io.BytesIO(test_content), 'application/pdf'))]
    
    data = {
        'category': 'bir',
        'sub_category': 'sss_contributions',  # This doesn't exist in BIR, let's use valid one
        'year': '2025',
        'coverage_months': '1,2,3',
        'name': 'TEST_Document_For_Testing',
        'description': 'Test document created for API testing',
        'tags': 'test,automated,cleanup'
    }
    
    # Actually BIR has monthly types like sss_contributions, but that's in employer_compliance
    # Let's use the correct category/subcategory
    data['category'] = 'employer_compliance'
    data['sub_category'] = 'sss_contributions'
    
    response = requests.post(
        f"{BASE_URL}/api/documents",
        headers=auth_headers,
        files=files,
        data=data
    )
    
    # If upload fails, try a simpler category
    if response.status_code != 200:
        data['category'] = 'bir'
        data['sub_category'] = '1601c'  # Monthly withholding tax
        files = [('files', ('test_document.pdf', io.BytesIO(test_content), 'application/pdf'))]
        response = requests.post(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            files=files,
            data=data
        )
    
    assert response.status_code == 200, f"Failed to create test document: {response.text}"
    doc = response.json()
    doc_id = doc.get("id")
    assert doc_id, "No document ID returned"
    
    yield doc_id
    
    # Cleanup: Delete the test document after tests
    requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=auth_headers)


class TestDocumentCategories:
    """Test GET /api/documents/categories endpoint."""
    
    def test_get_categories_returns_6_categories(self, auth_headers):
        """Verify categories endpoint returns all 6 Philippine compliance categories."""
        response = requests.get(f"{BASE_URL}/api/documents/categories", headers=auth_headers)
        assert response.status_code == 200, f"Categories request failed: {response.text}"
        
        categories = response.json()
        assert isinstance(categories, dict), "Categories should be a dictionary"
        
        # Verify 6 categories exist
        expected_categories = [
            'business_registration',
            'lgu_permits', 
            'bir',
            'employer_compliance',
            'agrivet',
            'other'
        ]
        
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
        
        assert len(categories) == 6, f"Expected 6 categories, got {len(categories)}"
        print(f"✓ All 6 categories present: {list(categories.keys())}")
    
    def test_categories_have_correct_structure(self, auth_headers):
        """Verify each category has label, icon, and sub_categories."""
        response = requests.get(f"{BASE_URL}/api/documents/categories", headers=auth_headers)
        assert response.status_code == 200
        
        categories = response.json()
        
        for cat_key, cat_data in categories.items():
            assert "label" in cat_data, f"Category {cat_key} missing label"
            assert "icon" in cat_data, f"Category {cat_key} missing icon"
            assert "sub_categories" in cat_data, f"Category {cat_key} missing sub_categories"
            assert isinstance(cat_data["sub_categories"], dict), f"sub_categories should be dict"
            
        print("✓ All categories have correct structure (label, icon, sub_categories)")
    
    def test_bir_category_has_monthly_subcategories(self, auth_headers):
        """Verify BIR category has monthly period types like 1601C, 0619E, 2550M."""
        response = requests.get(f"{BASE_URL}/api/documents/categories", headers=auth_headers)
        assert response.status_code == 200
        
        categories = response.json()
        bir = categories.get("bir", {})
        subs = bir.get("sub_categories", {})
        
        # Check monthly types
        monthly_types = ['1601c', '0619e', '2550m']
        for sub_key in monthly_types:
            assert sub_key in subs, f"Missing BIR sub-category: {sub_key}"
            assert subs[sub_key].get("period_type") == "monthly", f"{sub_key} should be monthly"
        
        print(f"✓ BIR has monthly sub-categories: {monthly_types}")
    
    def test_employer_compliance_has_contribution_types(self, auth_headers):
        """Verify employer compliance has SSS, PhilHealth, Pag-IBIG contribution types."""
        response = requests.get(f"{BASE_URL}/api/documents/categories", headers=auth_headers)
        assert response.status_code == 200
        
        categories = response.json()
        emp = categories.get("employer_compliance", {})
        subs = emp.get("sub_categories", {})
        
        contrib_types = ['sss_contributions', 'philhealth_contributions', 'pagibig_contributions']
        for sub_key in contrib_types:
            assert sub_key in subs, f"Missing contribution type: {sub_key}"
            assert subs[sub_key].get("period_type") == "monthly", f"{sub_key} should be monthly"
        
        print(f"✓ Employer compliance has contribution types: {contrib_types}")
    
    def test_agrivet_category_is_audit_sensitive(self, auth_headers):
        """Verify agrivet category is marked as audit-sensitive."""
        response = requests.get(f"{BASE_URL}/api/documents/categories", headers=auth_headers)
        assert response.status_code == 200
        
        categories = response.json()
        agrivet = categories.get("agrivet", {})
        
        assert agrivet.get("audit_sensitive") == True, "Agrivet should be audit_sensitive"
        
        # Check BAI license is also audit sensitive
        subs = agrivet.get("sub_categories", {})
        bai = subs.get("bai_license", {})
        assert bai.get("audit_sensitive") == True, "BAI license should be audit_sensitive"
        
        print("✓ Agrivet category and BAI license are audit-sensitive")


class TestDocumentUpload:
    """Test POST /api/documents upload endpoint."""
    
    def test_upload_document_with_file(self, auth_headers):
        """Upload a document with file attachment."""
        test_content = b"SAMPLE TEST CONTENT FOR UPLOAD TEST"
        files = [('files', ('sample.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        data = {
            'category': 'other',
            'sub_category': 'miscellaneous',
            'year': '2025',
            'name': 'TEST_Upload_Test_Document',
            'description': 'Testing upload functionality'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        doc = response.json()
        
        # Verify document structure
        assert "id" in doc, "Document should have ID"
        assert doc.get("category") == "other"
        assert doc.get("sub_category") == "miscellaneous"
        assert doc.get("file_count") == 1, "Should have 1 file"
        assert len(doc.get("files", [])) == 1
        
        # Verify file metadata
        file_meta = doc["files"][0]
        assert "r2_key" in file_meta, "File should have R2 key"
        assert file_meta.get("filename") == "sample.pdf"
        
        print(f"✓ Document uploaded successfully: {doc['id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc['id']}", headers=auth_headers)
    
    def test_upload_with_coverage_months(self, auth_headers):
        """Upload monthly document with coverage months."""
        test_content = b"SSS CONTRIBUTION RECEIPT"
        files = [('files', ('sss_jan_feb.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        data = {
            'category': 'employer_compliance',
            'sub_category': 'sss_contributions',
            'year': '2025',
            'coverage_months': '1,2,3',  # Jan, Feb, Mar
            'name': 'TEST_SSS_Q1_2025',
            'tags': 'test,sss,q1'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        doc = response.json()
        
        # Verify coverage months
        assert doc.get("coverage_months") == [1, 2, 3], "Coverage months should be [1, 2, 3]"
        assert doc.get("period_type") == "monthly"
        assert "test" in doc.get("tags", [])
        
        print(f"✓ Document with coverage months uploaded: {doc['coverage_months']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc['id']}", headers=auth_headers)
    
    def test_upload_invalid_category_fails(self, auth_headers):
        """Upload with invalid category should fail."""
        test_content = b"INVALID CATEGORY TEST"
        files = [('files', ('test.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        data = {
            'category': 'invalid_category',
            'sub_category': 'invalid_sub',
            'year': '2025'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 400, "Should fail with invalid category"
        assert "invalid" in response.text.lower()
        print("✓ Invalid category correctly rejected")


class TestDocumentList:
    """Test GET /api/documents list endpoint."""
    
    def test_list_documents(self, auth_headers, test_document_id):
        """List all documents."""
        response = requests.get(f"{BASE_URL}/api/documents", headers=auth_headers)
        assert response.status_code == 200, f"List failed: {response.text}"
        
        data = response.json()
        assert "documents" in data, "Response should have documents array"
        assert "total" in data, "Response should have total count"
        assert isinstance(data["documents"], list)
        
        print(f"✓ Listed {data['total']} documents")
    
    def test_filter_by_category(self, auth_headers, test_document_id):
        """Filter documents by category."""
        # Get our test document's category
        doc_response = requests.get(f"{BASE_URL}/api/documents/{test_document_id}", headers=auth_headers)
        doc = doc_response.json()
        category = doc.get("category", "bir")
        
        response = requests.get(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            params={"category": category}
        )
        assert response.status_code == 200
        
        data = response.json()
        # All returned docs should have the filtered category
        for d in data["documents"]:
            assert d.get("category") == category, f"Document {d['id']} has wrong category"
        
        print(f"✓ Category filter works: {len(data['documents'])} docs in {category}")
    
    def test_filter_by_year(self, auth_headers):
        """Filter documents by year."""
        response = requests.get(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            params={"year": 2025}
        )
        assert response.status_code == 200
        
        data = response.json()
        for d in data["documents"]:
            assert d.get("year") == 2025, f"Document {d['id']} has wrong year"
        
        print(f"✓ Year filter works: {len(data['documents'])} docs in 2025")
    
    def test_search_documents(self, auth_headers, test_document_id):
        """Search documents by name/tags."""
        response = requests.get(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            params={"search": "TEST_"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should find our test document
        assert data["total"] > 0, "Should find documents matching TEST_"
        
        print(f"✓ Search works: found {data['total']} documents matching 'TEST_'")


class TestDocumentCRUD:
    """Test single document GET, PUT, DELETE operations."""
    
    def test_get_single_document(self, auth_headers, test_document_id):
        """Get single document with pre-signed URLs."""
        response = requests.get(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get failed: {response.text}"
        
        doc = response.json()
        assert doc.get("id") == test_document_id
        assert "files" in doc
        
        # Verify files have pre-signed URLs
        if doc["files"]:
            for f in doc["files"]:
                assert "url" in f, "File should have pre-signed URL"
                assert f["url"].startswith("http"), "URL should be valid"
        
        print(f"✓ Got document {test_document_id} with {len(doc.get('files', []))} files")
    
    def test_get_nonexistent_document(self, auth_headers):
        """Get non-existent document returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/documents/nonexistent_id_12345",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Non-existent document returns 404")
    
    def test_update_document_metadata(self, auth_headers, test_document_id):
        """Update document metadata."""
        update_data = {
            "name": "TEST_Updated_Document_Name",
            "description": "Updated description for testing",
            "tags": ["updated", "test"],
            "coverage_months": [4, 5, 6],
            "valid_until": "2025-12-31"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify update by fetching
        get_response = requests.get(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers
        )
        doc = get_response.json()
        
        assert doc.get("name") == "TEST_Updated_Document_Name"
        assert doc.get("description") == "Updated description for testing"
        assert doc.get("valid_until") == "2025-12-31"
        
        print(f"✓ Document metadata updated successfully")
    
    def test_delete_document_requires_manager_role(self, auth_headers, test_document_id):
        """Delete requires admin/manager role (super admin should work)."""
        # Create a temporary document to delete
        test_content = b"TEMP DOC FOR DELETE TEST"
        files = [('files', ('temp.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        create_response = requests.post(
            f"{BASE_URL}/api/documents",
            headers=auth_headers,
            files=files,
            data={'category': 'other', 'sub_category': 'miscellaneous', 'year': '2025'}
        )
        assert create_response.status_code == 200
        temp_doc_id = create_response.json()["id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/documents/{temp_doc_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Delete failed: {response.text}"
        
        # Verify deleted
        get_response = requests.get(
            f"{BASE_URL}/api/documents/{temp_doc_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404, "Deleted document should return 404"
        
        print("✓ Document deleted successfully")


class TestComplianceSummary:
    """Test GET /api/documents/compliance/summary endpoint."""
    
    def test_compliance_summary_structure(self, auth_headers):
        """Get compliance summary with correct structure."""
        response = requests.get(
            f"{BASE_URL}/api/documents/compliance/summary",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Summary failed: {response.text}"
        
        summary = response.json()
        
        # Verify structure
        assert "year" in summary, "Should have year"
        assert "monthly_coverage" in summary, "Should have monthly_coverage"
        assert "expiring_soon" in summary, "Should have expiring_soon"
        assert "expired" in summary, "Should have expired"
        
        assert isinstance(summary["monthly_coverage"], dict)
        assert isinstance(summary["expiring_soon"], list)
        assert isinstance(summary["expired"], list)
        
        print(f"✓ Compliance summary for year {summary['year']}")
        print(f"  - Monthly coverage: {len(summary['monthly_coverage'])} sub-categories tracked")
        print(f"  - Expiring soon: {len(summary['expiring_soon'])} permits")
        print(f"  - Expired: {len(summary['expired'])} permits")
    
    def test_compliance_summary_with_year_filter(self, auth_headers):
        """Get compliance summary for specific year."""
        response = requests.get(
            f"{BASE_URL}/api/documents/compliance/summary",
            headers=auth_headers,
            params={"year": 2024}
        )
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["year"] == 2024
        
        print(f"✓ Compliance summary for 2024 retrieved")


class TestQRUploadToken:
    """Test QR upload token generation and usage."""
    
    def test_generate_qr_upload_token(self, auth_headers):
        """Generate QR upload token."""
        token_data = {
            "category": "bir",
            "sub_category": "1601c",
            "year": 2025,
            "coverage_months": [1, 2]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers=auth_headers,
            json=token_data
        )
        assert response.status_code == 200, f"Token generation failed: {response.text}"
        
        data = response.json()
        
        # Verify token structure
        assert "token" in data, "Should have token"
        assert "expires_at" in data, "Should have expires_at"
        assert "category_label" in data
        assert "sub_category_label" in data
        
        # Token should be 32 chars (24 bytes base64)
        assert len(data["token"]) > 20, "Token should be at least 20 chars"
        
        print(f"✓ QR upload token generated: {data['token'][:10]}...")
        print(f"  - Category: {data['category_label']}")
        print(f"  - Sub-category: {data['sub_category_label']}")
        print(f"  - Expires: {data['expires_at']}")
        
        return data["token"]
    
    def test_qr_upload_preview_public(self, auth_headers):
        """Preview QR upload context (public endpoint)."""
        # First generate a token
        token_data = {
            "category": "employer_compliance",
            "sub_category": "sss_contributions",
            "year": 2025,
            "coverage_months": [3, 4, 5]
        }
        
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/qr-upload-token",
            headers=auth_headers,
            json=token_data
        )
        assert gen_response.status_code == 200
        token = gen_response.json()["token"]
        
        # Now preview without auth (public endpoint)
        preview_response = requests.get(f"{BASE_URL}/api/documents/qr-upload/{token}")
        assert preview_response.status_code == 200, f"Preview failed: {preview_response.text}"
        
        preview = preview_response.json()
        
        # Verify preview data
        assert preview.get("category_label") == "Employer & Employee Compliance"
        assert preview.get("sub_category_label") == "SSS Contributions"
        assert preview.get("year") == 2025
        assert preview.get("coverage_months") == [3, 4, 5]
        assert preview.get("expired") == False
        
        print(f"✓ QR upload preview (public): {preview['category_label']} / {preview['sub_category_label']}")
    
    def test_qr_upload_invalid_token(self):
        """Invalid QR token returns 404."""
        response = requests.get(f"{BASE_URL}/api/documents/qr-upload/invalid_token_xyz")
        assert response.status_code == 404
        print("✓ Invalid QR token returns 404")


class TestFileOperations:
    """Test file management within documents."""
    
    def test_add_files_to_document(self, auth_headers, test_document_id):
        """Add additional files to existing document."""
        test_content = b"ADDITIONAL FILE CONTENT"
        files = [('files', ('additional.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        response = requests.post(
            f"{BASE_URL}/api/documents/{test_document_id}/files",
            headers=auth_headers,
            files=files
        )
        assert response.status_code == 200, f"Add files failed: {response.text}"
        
        result = response.json()
        assert result.get("uploaded") == 1
        
        # Verify file was added
        get_response = requests.get(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers
        )
        doc = get_response.json()
        
        # Find the new file
        new_file = next((f for f in doc["files"] if f["filename"] == "additional.pdf"), None)
        assert new_file is not None, "Additional file should exist"
        
        print(f"✓ Added file to document. Total files: {doc['file_count']}")
        
        # Return file ID for removal test
        return new_file["id"]
    
    def test_remove_file_from_document(self, auth_headers, test_document_id):
        """Remove a file from document."""
        # First add a file to remove
        test_content = b"FILE TO REMOVE"
        files = [('files', ('to_remove.pdf', io.BytesIO(test_content), 'application/pdf'))]
        
        add_response = requests.post(
            f"{BASE_URL}/api/documents/{test_document_id}/files",
            headers=auth_headers,
            files=files
        )
        assert add_response.status_code == 200
        
        # Get the file ID
        get_response = requests.get(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers
        )
        doc = get_response.json()
        file_to_remove = next((f for f in doc["files"] if f["filename"] == "to_remove.pdf"), None)
        assert file_to_remove is not None
        
        file_id = file_to_remove["id"]
        initial_count = doc["file_count"]
        
        # Remove the file
        remove_response = requests.delete(
            f"{BASE_URL}/api/documents/{test_document_id}/files/{file_id}",
            headers=auth_headers
        )
        assert remove_response.status_code == 200, f"Remove file failed: {remove_response.text}"
        
        # Verify file count decreased
        get_response = requests.get(
            f"{BASE_URL}/api/documents/{test_document_id}",
            headers=auth_headers
        )
        doc = get_response.json()
        assert doc["file_count"] == initial_count - 1, "File count should decrease"
        
        print(f"✓ Removed file from document. Remaining files: {doc['file_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
