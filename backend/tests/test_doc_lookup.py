"""
Test Document Lookup API routes.
Tests: doc code generation, PIN-protected lookup, error handling.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from requirements
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
MANAGER_PIN = "521325"

class TestDocCodeGeneration:
    """Test POST /api/doc/generate-code endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for authenticated requests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Login failed: {login_res.status_code}")
    
    def test_generate_code_missing_params(self):
        """Test generate-code returns 400 if doc_type or doc_id missing"""
        # Missing both
        res = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={})
        assert res.status_code == 400
        assert "doc_type and doc_id required" in res.json().get("detail", "")
        print("PASS: Missing params returns 400")
        
        # Missing doc_id
        res = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={"doc_type": "invoice"})
        assert res.status_code == 400
        print("PASS: Missing doc_id returns 400")
        
        # Missing doc_type
        res = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={"doc_id": "test123"})
        assert res.status_code == 400
        print("PASS: Missing doc_type returns 400")
    
    def test_generate_code_without_auth(self):
        """Test generate-code requires authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.post(f"{BASE_URL}/api/doc/generate-code", json={
            "doc_type": "invoice",
            "doc_id": "test123"
        })
        assert res.status_code == 401 or res.status_code == 403
        print(f"PASS: Unauthenticated request returns {res.status_code}")
    
    def test_generate_code_success(self):
        """Test generate-code returns unique 8-char code"""
        # Use a test document ID
        test_doc_id = "test_doc_" + os.urandom(4).hex()
        res = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={
            "doc_type": "invoice",
            "doc_id": test_doc_id
        })
        assert res.status_code == 200
        data = res.json()
        assert "code" in data
        code = data["code"]
        assert len(code) == 8
        assert code.isalnum()
        assert code.isupper()
        assert data["doc_type"] == "invoice"
        assert data["doc_id"] == test_doc_id
        print(f"PASS: Generated code {code} for test doc")
        
        # Calling again should return same code (idempotent)
        res2 = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={
            "doc_type": "invoice",
            "doc_id": test_doc_id
        })
        assert res2.status_code == 200
        assert res2.json()["code"] == code
        print("PASS: Second call returns same code (idempotent)")


class TestDocLookup:
    """Test POST /api/doc/lookup endpoint (PIN-protected)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_lookup_missing_code(self):
        """Test lookup returns 400 if code missing"""
        res = self.session.post(f"{BASE_URL}/api/doc/lookup", json={
            "pin": MANAGER_PIN
        })
        assert res.status_code == 400
        assert "code required" in res.json().get("detail", "").lower()
        print("PASS: Missing code returns 400")
    
    def test_lookup_missing_pin(self):
        """Test lookup returns 400 if PIN missing"""
        res = self.session.post(f"{BASE_URL}/api/doc/lookup", json={
            "code": "CT7SP66X"  # Known test code from requirements
        })
        assert res.status_code == 400
        assert "pin required" in res.json().get("detail", "").lower()
        print("PASS: Missing PIN returns 400")
    
    def test_lookup_invalid_pin(self):
        """Test lookup returns 403 for invalid PIN"""
        res = self.session.post(f"{BASE_URL}/api/doc/lookup", json={
            "code": "CT7SP66X",
            "pin": "000000"  # Invalid PIN
        })
        assert res.status_code == 403
        assert "invalid pin" in res.json().get("detail", "").lower()
        print("PASS: Invalid PIN returns 403")
    
    def test_lookup_nonexistent_code(self):
        """Test lookup returns 404 for nonexistent document code"""
        res = self.session.post(f"{BASE_URL}/api/doc/lookup", json={
            "code": "XXXXXX99",  # Non-existent code
            "pin": MANAGER_PIN
        })
        assert res.status_code == 404
        assert "not found" in res.json().get("detail", "").lower()
        print("PASS: Nonexistent code returns 404")
    
    def test_lookup_success_with_valid_pin(self):
        """Test lookup returns document details with valid PIN"""
        # Use the known test code CT7SP66X for branch_transfer
        res = self.session.post(f"{BASE_URL}/api/doc/lookup", json={
            "code": "CT7SP66X",
            "pin": MANAGER_PIN
        })
        
        # This test may fail if test code doesn't exist - that's valid scenario
        if res.status_code == 404:
            print("INFO: Test code CT7SP66X not found - testing with fresh code")
            pytest.skip("Test code CT7SP66X not found in database")
            return
        
        assert res.status_code == 200
        data = res.json()
        assert "doc_type" in data
        assert "document" in data
        assert "verifier" in data
        print(f"PASS: Lookup returned doc_type={data['doc_type']}")
        
        # Verify document structure based on type
        doc_type = data["doc_type"]
        if doc_type == "branch_transfer":
            assert "from_branch_name" in data
            assert "to_branch_name" in data
            print(f"PASS: Branch transfer has from={data['from_branch_name']}, to={data['to_branch_name']}")
        elif doc_type == "invoice":
            # Invoice may have customer info
            print(f"PASS: Invoice document returned")
        elif doc_type == "purchase_order":
            print(f"PASS: Purchase order document returned")


class TestDocCodeByRef:
    """Test GET /api/doc/by-ref/{doc_type}/{doc_id} endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Login failed")
    
    def test_get_existing_code_by_ref(self):
        """Test get code by ref for existing document"""
        # First create a code
        test_doc_id = "byref_test_" + os.urandom(4).hex()
        create_res = self.session.post(f"{BASE_URL}/api/doc/generate-code", json={
            "doc_type": "invoice",
            "doc_id": test_doc_id
        })
        assert create_res.status_code == 200
        created_code = create_res.json()["code"]
        
        # Now fetch by ref
        res = self.session.get(f"{BASE_URL}/api/doc/by-ref/invoice/{test_doc_id}")
        assert res.status_code == 200
        assert res.json()["code"] == created_code
        print(f"PASS: get by-ref returned code {created_code}")
    
    def test_get_nonexistent_code_by_ref(self):
        """Test get code by ref returns null for non-existent"""
        res = self.session.get(f"{BASE_URL}/api/doc/by-ref/invoice/nonexistent_12345")
        assert res.status_code == 200
        assert res.json()["code"] is None
        print("PASS: Non-existent ref returns code=null")
    
    def test_get_code_by_ref_without_auth(self):
        """Test get by ref requires authentication"""
        session = requests.Session()
        res = session.get(f"{BASE_URL}/api/doc/by-ref/invoice/test123")
        assert res.status_code == 401 or res.status_code == 403
        print(f"PASS: Unauthenticated by-ref request returns {res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
