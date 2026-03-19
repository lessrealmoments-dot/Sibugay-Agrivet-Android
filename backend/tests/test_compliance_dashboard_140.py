"""
AgriDocs Phase 3 - Compliance Dashboard Tests (Iteration 140)

Tests for:
- GET /api/documents/compliance/summary endpoint
- monthly_coverage tracking for SSS, PhilHealth, Pag-IBIG, BIR forms
- expired documents alerts (valid_until < today)
- expiring_soon alerts (valid_until within 60 days)
- sub_category_label returned in response
- branch_id filtering (excludes 'all')
- Search by document name and tags
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
TEST_EMAIL = "janmarkeahig@gmail.com"
TEST_PASSWORD = "Aa@58798546521325"

# Test document IDs to clean up
test_doc_ids = []


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for Super Admin."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated session."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


class TestComplianceSummaryEndpoint:
    """Test GET /api/documents/compliance/summary"""

    def test_compliance_summary_returns_structure(self, api_client):
        """Compliance summary returns year, monthly_coverage, expiring_soon, expired"""
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "year" in data, "Missing 'year' in response"
        assert "monthly_coverage" in data, "Missing 'monthly_coverage' in response"
        assert "expiring_soon" in data, "Missing 'expiring_soon' in response"
        assert "expired" in data, "Missing 'expired' in response"
        
        assert data["year"] == 2026, f"Expected year 2026, got {data['year']}"
        assert isinstance(data["monthly_coverage"], dict), "monthly_coverage should be dict"
        assert isinstance(data["expiring_soon"], list), "expiring_soon should be list"
        assert isinstance(data["expired"], list), "expired should be list"
        print(f"PASS: Compliance summary structure verified")

    def test_compliance_summary_branch_filter(self, api_client):
        """Branch filter works (excludes 'all')"""
        # With specific branch_id
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026&branch_id=test_branch")
        assert res.status_code == 200, f"Failed with branch filter: {res.text}"
        
        # Without branch_id (should work)
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200, f"Failed without branch filter: {res.text}"
        print(f"PASS: Branch filtering works")


class TestMonthlyCoverageTracking:
    """Test monthly document coverage in compliance summary"""

    def test_upload_sss_contribution_shows_in_coverage(self, api_client):
        """SSS contribution with coverage_months appears in monthly_coverage"""
        # Create SSS contribution document
        files = [('files', ('test_sss.pdf', b'Test SSS content', 'application/pdf'))]
        data = {
            'category': 'employer_compliance',
            'sub_category': 'sss_contributions',
            'name': 'TEST_SSS_Jan_Feb_140',
            'year': '2026',
            'coverage_months': '1,2',  # January, February
        }
        res = api_client.post(f"{BASE_URL}/api/documents", files=files, data=data, headers={'Authorization': api_client.headers['Authorization']})
        # Remove Content-Type for multipart
        del api_client.headers['Content-Type']
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        api_client.headers['Content-Type'] = 'application/json'
        
        assert res.status_code == 200, f"Failed to upload SSS doc: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created test SSS document: {doc['id']}")

        # Check compliance summary
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200
        data = res.json()
        
        coverage = data.get("monthly_coverage", {})
        sss_months = coverage.get("sss_contributions", [])
        assert 1 in sss_months or 2 in sss_months, f"SSS coverage should include months 1,2. Got: {sss_months}"
        print(f"PASS: SSS contribution coverage: {sss_months}")

    def test_upload_philhealth_contribution_shows_in_coverage(self, api_client):
        """PhilHealth contribution with coverage_months appears in monthly_coverage"""
        files = [('files', ('test_philhealth.pdf', b'Test PhilHealth content', 'application/pdf'))]
        data = {
            'category': 'employer_compliance',
            'sub_category': 'philhealth_contributions',
            'name': 'TEST_PhilHealth_Mar_140',
            'year': '2026',
            'coverage_months': '3',  # March
        }
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        
        assert res.status_code == 200, f"Failed to upload PhilHealth doc: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created test PhilHealth document: {doc['id']}")

        # Check compliance summary
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200
        data = res.json()
        
        coverage = data.get("monthly_coverage", {})
        philhealth_months = coverage.get("philhealth_contributions", [])
        assert 3 in philhealth_months, f"PhilHealth coverage should include month 3. Got: {philhealth_months}"
        print(f"PASS: PhilHealth contribution coverage: {philhealth_months}")


class TestExpiryAlerts:
    """Test expired and expiring_soon alerts"""

    def test_expired_document_shows_in_expired_list(self, api_client):
        """Document with valid_until in the past appears in expired array"""
        # Create expired permit
        yesterday = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        files = [('files', ('test_permit_expired.pdf', b'Test expired permit', 'application/pdf'))]
        data = {
            'category': 'lgu_permits',
            'sub_category': 'mayors_permit',
            'name': 'TEST_Expired_Permit_140',
            'year': '2026',
            'valid_until': yesterday,
        }
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        
        assert res.status_code == 200, f"Failed to upload expired permit: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created expired permit document: {doc['id']} with valid_until={yesterday}")

        # Check compliance summary
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200
        data = res.json()
        
        expired = data.get("expired", [])
        expired_subcats = [e.get("sub_category") for e in expired]
        assert "mayors_permit" in expired_subcats, f"Expired list should include mayors_permit. Got: {expired_subcats}"
        
        # Check sub_category_label is present
        for e in expired:
            if e.get("sub_category") == "mayors_permit":
                assert "sub_category_label" in e, "Missing sub_category_label in expired item"
                print(f"PASS: Expired mayors_permit found with label: {e.get('sub_category_label')}")
                break

    def test_expiring_soon_document_shows_in_expiring_list(self, api_client):
        """Document with valid_until within 60 days appears in expiring_soon"""
        # Create expiring soon permit (30 days from now)
        expiring_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        files = [('files', ('test_permit_expiring.pdf', b'Test expiring permit', 'application/pdf'))]
        data = {
            'category': 'lgu_permits',
            'sub_category': 'fsic',
            'name': 'TEST_Expiring_FSIC_140',
            'year': '2026',
            'valid_until': expiring_date,
        }
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        
        assert res.status_code == 200, f"Failed to upload expiring permit: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created expiring permit document: {doc['id']} with valid_until={expiring_date}")

        # Check compliance summary
        res = api_client.get(f"{BASE_URL}/api/documents/compliance/summary?year=2026")
        assert res.status_code == 200
        data = res.json()
        
        expiring = data.get("expiring_soon", [])
        expiring_subcats = [e.get("sub_category") for e in expiring]
        assert "fsic" in expiring_subcats, f"Expiring list should include fsic. Got: {expiring_subcats}"
        
        # Check sub_category_label and days_left present
        for e in expiring:
            if e.get("sub_category") == "fsic":
                assert "sub_category_label" in e, "Missing sub_category_label in expiring item"
                assert "days_left" in e, "Missing days_left in expiring item"
                assert e["days_left"] <= 60, f"days_left should be <=60, got {e['days_left']}"
                print(f"PASS: Expiring FSIC found with {e['days_left']} days left, label: {e.get('sub_category_label')}")
                break


class TestSearchFunctionality:
    """Test document search by name and tags"""

    def test_search_by_document_name(self, api_client):
        """Search returns documents matching name"""
        # Create a searchable document
        files = [('files', ('test_searchable.pdf', b'Test searchable doc', 'application/pdf'))]
        data = {
            'category': 'other',
            'sub_category': 'miscellaneous',
            'name': 'TEST_UNIQUE_SEARCHNAME_140',
            'year': '2026',
        }
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        
        assert res.status_code == 200, f"Failed to upload searchable doc: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created searchable document: {doc['id']}")

        # Search by name
        res = api_client.get(f"{BASE_URL}/api/documents?search=UNIQUE_SEARCHNAME_140")
        assert res.status_code == 200
        data = res.json()
        
        docs = data.get("documents", [])
        found = any("UNIQUE_SEARCHNAME_140" in d.get("name", "") for d in docs)
        assert found, f"Search by name should find document. Got {len(docs)} results"
        print(f"PASS: Search by name found {len(docs)} document(s)")

    def test_search_by_tags(self, api_client):
        """Search returns documents matching tags"""
        # Create a document with unique tag
        files = [('files', ('test_tagged.pdf', b'Test tagged doc', 'application/pdf'))]
        data = {
            'category': 'other',
            'sub_category': 'miscellaneous',
            'name': 'TEST_Tagged_Doc_140',
            'year': '2026',
            'tags': 'uniquetag140,testtag',
        }
        res = requests.post(
            f"{BASE_URL}/api/documents",
            files=files,
            data=data,
            headers={'Authorization': api_client.headers['Authorization']}
        )
        
        assert res.status_code == 200, f"Failed to upload tagged doc: {res.text}"
        doc = res.json()
        test_doc_ids.append(doc['id'])
        print(f"Created tagged document: {doc['id']}")

        # Search by tag
        res = api_client.get(f"{BASE_URL}/api/documents?search=uniquetag140")
        assert res.status_code == 200
        data = res.json()
        
        docs = data.get("documents", [])
        found = any("uniquetag140" in (d.get("tags", []) or []) for d in docs)
        assert found, f"Search by tag should find document. Got {len(docs)} results"
        print(f"PASS: Search by tag found {len(docs)} document(s)")


class TestCategoryFolderCounts:
    """Test category folder document counts"""

    def test_list_documents_returns_correct_count(self, api_client):
        """Document list returns total count"""
        res = api_client.get(f"{BASE_URL}/api/documents?year=2026&limit=10")
        assert res.status_code == 200
        data = res.json()
        
        assert "documents" in data, "Missing 'documents' in response"
        assert "total" in data, "Missing 'total' in response"
        assert isinstance(data["total"], int), "total should be integer"
        print(f"PASS: Document list returns total={data['total']}, docs in page={len(data['documents'])}")


class TestCleanup:
    """Clean up test documents"""

    def test_cleanup_test_documents(self, api_client):
        """Delete all test documents created during testing"""
        deleted = 0
        for doc_id in test_doc_ids:
            res = api_client.delete(f"{BASE_URL}/api/documents/{doc_id}")
            if res.status_code in [200, 204]:
                deleted += 1
            else:
                print(f"Warning: Could not delete doc {doc_id}: {res.status_code}")
        
        print(f"PASS: Cleaned up {deleted}/{len(test_doc_ids)} test documents")
        test_doc_ids.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
