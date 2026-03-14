"""
Test suite for 3-tier Document Viewer system (iteration 120)
- Tier 1: Open endpoint (GET /api/doc/view/{code}) - no auth required
- Tier 2: PIN-protected lookup (POST /api/doc/lookup) - requires PIN
- Tier 3: Terminal actions - tested via frontend (localStorage gating)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_DOC_CODE = "CT7SP66X"
VALID_PIN = "521325"
INVALID_PIN = "000000"
NONEXISTENT_CODE = "INVALID123"


class TestTier1OpenEndpoint:
    """Tier 1: GET /api/doc/view/{code} - Open endpoint, no auth required"""

    def test_view_existing_document_no_auth(self):
        """GET /api/doc/view/{code} returns basic info without any authentication"""
        response = requests.get(f"{BASE_URL}/api/doc/view/{TEST_DOC_CODE}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate basic document structure
        assert "doc_type" in data, "Response should include doc_type"
        assert "doc_id" in data, "Response should include doc_id"
        assert "number" in data, "Response should include document number"
        assert "date" in data, "Response should include date"
        assert "items" in data, "Response should include items"
        assert "status" in data, "Response should include status"
        
        # For branch_transfer type, verify branch info
        if data["doc_type"] == "branch_transfer":
            assert "from_branch" in data, "Branch transfer should include from_branch"
            assert "to_branch" in data, "Branch transfer should include to_branch"
            assert "total" in data, "Branch transfer should include total"

    def test_view_document_case_insensitive(self):
        """Document code lookup should be case-insensitive (lowercased converted to uppercase)"""
        response = requests.get(f"{BASE_URL}/api/doc/view/{TEST_DOC_CODE.lower()}")
        assert response.status_code == 200

    def test_view_nonexistent_document_returns_404(self):
        """GET /api/doc/view/{code} with nonexistent code returns 404"""
        response = requests.get(f"{BASE_URL}/api/doc/view/{NONEXISTENT_CODE}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "404 response should include detail message"
        assert "not found" in data["detail"].lower(), "Error message should indicate not found"

    def test_tier1_excludes_sensitive_data(self):
        """Tier 1 response should NOT include sensitive data like payment history or attached files"""
        response = requests.get(f"{BASE_URL}/api/doc/view/{TEST_DOC_CODE}")
        data = response.json()
        
        # These should NOT be in Tier 1 response
        assert "payments" not in data, "Tier 1 should NOT expose payment history"
        assert "attached_files" not in data, "Tier 1 should NOT expose attached files"
        assert "verifier" not in data, "Tier 1 should NOT expose verifier info"


class TestTier2PinProtectedLookup:
    """Tier 2: POST /api/doc/lookup - PIN-protected full document details"""

    def test_lookup_with_valid_pin_returns_full_details(self):
        """POST /api/doc/lookup with valid PIN returns full document details"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": TEST_DOC_CODE, "pin": VALID_PIN}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate full document structure
        assert "doc_type" in data, "Response should include doc_type"
        assert "document" in data, "Response should include full document object"
        assert "verifier" in data, "Response should include verifier info"
        
        # Verify document object has detailed info
        doc = data["document"]
        assert "id" in doc, "Document should have id"
        
        # For branch_transfer type, verify additional details
        if data["doc_type"] == "branch_transfer":
            assert "from_branch_name" in data, "Should include from_branch_name"
            assert "to_branch_name" in data, "Should include to_branch_name"
            assert "attached_files" in data, "Should include attached_files (even if empty)"

    def test_lookup_with_invalid_pin_returns_403(self):
        """POST /api/doc/lookup with invalid PIN returns 403 Forbidden"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": TEST_DOC_CODE, "pin": INVALID_PIN}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower(), "Error should indicate invalid PIN"

    def test_lookup_missing_code_returns_400(self):
        """POST /api/doc/lookup without code returns 400 Bad Request"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"pin": VALID_PIN}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_lookup_missing_pin_returns_400(self):
        """POST /api/doc/lookup without PIN returns 400 Bad Request"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": TEST_DOC_CODE}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_lookup_nonexistent_code_returns_404(self):
        """POST /api/doc/lookup with valid PIN but nonexistent code returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": NONEXISTENT_CODE, "pin": VALID_PIN}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_lookup_empty_code_returns_400(self):
        """POST /api/doc/lookup with empty code returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": "", "pin": VALID_PIN}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_lookup_empty_pin_returns_400(self):
        """POST /api/doc/lookup with empty PIN returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/doc/lookup",
            json={"code": TEST_DOC_CODE, "pin": ""}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"


class TestTier1ItemsStructure:
    """Verify Tier 1 items structure contains expected fields"""

    def test_items_have_required_fields(self):
        """Each item in Tier 1 response should have name, qty, price, total"""
        response = requests.get(f"{BASE_URL}/api/doc/view/{TEST_DOC_CODE}")
        data = response.json()
        
        assert "items" in data, "Response should include items"
        for item in data["items"]:
            assert "name" in item, "Item should have name"
            assert "qty" in item, "Item should have qty"
            assert "price" in item, "Item should have price"
            assert "total" in item, "Item should have total"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
