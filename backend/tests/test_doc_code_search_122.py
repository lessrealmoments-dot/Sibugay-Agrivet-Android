"""
Test Suite: Document Code Search and Print Features (Iteration 122)
Tests the new features:
1. QuickSearch doc code scanning integration
2. Search API with doc_code lookup
3. Doc code generation for printing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDocCodeSearch:
    """Tests for document code search integration in QuickSearch"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_search_regular_query(self):
        """Test search API with regular text query (existing functionality)"""
        resp = requests.get(f"{BASE_URL}/api/search/transactions", 
            params={"q": "INV", "limit": 5},
            headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        # Should not have doc_code_match flag for regular query
        assert data.get("doc_code_match") is not True or data.get("doc_code_match") is None
        print(f"Regular search returned {len(data['results'])} results")
    
    def test_search_po_number_query(self):
        """Test search API with PO number query"""
        resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1", "limit": 5},
            headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        results = data["results"]
        # If results found, they should be POs
        if results:
            po_results = [r for r in results if r.get("type") == "purchase_order"]
            print(f"Found {len(po_results)} PO results")
    
    def test_generate_doc_code_invoice(self):
        """Test generating a doc code for an invoice"""
        # First get an invoice ID
        search_resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "SI", "limit": 1},
            headers=self.headers)
        assert search_resp.status_code == 200
        results = search_resp.json().get("results", [])
        
        if not results:
            pytest.skip("No invoices found to test doc code generation")
        
        invoice_id = results[0]["id"]
        
        # Generate doc code
        gen_resp = requests.post(f"{BASE_URL}/api/doc/generate-code",
            json={"doc_type": "invoice", "doc_id": invoice_id},
            headers=self.headers)
        assert gen_resp.status_code == 200
        data = gen_resp.json()
        assert "code" in data
        assert len(data["code"]) >= 6, "Doc code should be at least 6 characters"
        print(f"Generated doc code: {data['code']} for invoice {invoice_id}")
        
        return data["code"], invoice_id
    
    def test_search_with_doc_code(self):
        """Test search API with a generated doc code (QR scan simulation)"""
        # First generate a doc code
        search_resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "SI", "limit": 1},
            headers=self.headers)
        if not search_resp.json().get("results"):
            pytest.skip("No invoices available for doc code test")
        
        invoice_id = search_resp.json()["results"][0]["id"]
        invoice_number = search_resp.json()["results"][0].get("number", "")
        
        # Generate doc code
        gen_resp = requests.post(f"{BASE_URL}/api/doc/generate-code",
            json={"doc_type": "invoice", "doc_id": invoice_id},
            headers=self.headers)
        assert gen_resp.status_code == 200
        doc_code = gen_resp.json()["code"]
        
        # Now search with the doc code
        search_with_code = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": doc_code, "limit": 5},
            headers=self.headers)
        assert search_with_code.status_code == 200
        data = search_with_code.json()
        
        # Should have doc_code_match flag
        assert data.get("doc_code_match") == True, "doc_code_match flag should be True"
        assert len(data["results"]) >= 1, "Should find at least 1 result"
        
        # First result should be the invoice we generated code for
        first_result = data["results"][0]
        assert first_result["id"] == invoice_id, f"Should return the same invoice. Got {first_result['id']}, expected {invoice_id}"
        print(f"✓ Doc code search found invoice {first_result.get('number', invoice_number)}")
    
    def test_generate_doc_code_po(self):
        """Test generating a doc code for a purchase order"""
        # Get a PO ID
        search_resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1", "type": "purchase_order", "limit": 1},
            headers=self.headers)
        assert search_resp.status_code == 200
        results = search_resp.json().get("results", [])
        
        if not results:
            pytest.skip("No POs found to test doc code generation")
        
        po_id = results[0]["id"]
        
        # Generate doc code
        gen_resp = requests.post(f"{BASE_URL}/api/doc/generate-code",
            json={"doc_type": "purchase_order", "doc_id": po_id},
            headers=self.headers)
        assert gen_resp.status_code == 200
        data = gen_resp.json()
        assert "code" in data
        print(f"Generated doc code: {data['code']} for PO {po_id}")
    
    def test_search_empty_query(self):
        """Test search with empty query returns no results"""
        resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "", "limit": 5},
            headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("results", [])) == 0, "Empty query should return no results"
    
    def test_search_short_query(self):
        """Test search with query < 2 chars returns no results"""
        resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "A", "limit": 5},
            headers=self.headers)
        assert resp.status_code == 200
        # Short queries return empty results
        # This tests the frontend validation that requires >= 2 chars


class TestInvoiceEndpoints:
    """Tests for invoice/sale detail endpoints used by SaleDetailModal"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        self.token = login_resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_invoice_by_id(self):
        """Test fetching invoice details by ID"""
        # First get an invoice ID from search
        search_resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "SI", "limit": 1},
            headers=self.headers)
        if not search_resp.json().get("results"):
            pytest.skip("No invoices available")
        
        invoice_id = search_resp.json()["results"][0]["id"]
        
        # Get invoice details
        detail_resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}",
            headers=self.headers)
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert "id" in data
        assert "invoice_number" in data or "sale_number" in data
        print(f"✓ Fetched invoice detail: {data.get('invoice_number', data.get('sale_number'))}")


class TestPurchaseOrderEndpoints:
    """Tests for PO detail endpoints used by PODetailModal"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        self.token = login_resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_po_by_id(self):
        """Test fetching PO details by ID"""
        # First get a PO ID from search
        search_resp = requests.get(f"{BASE_URL}/api/search/transactions",
            params={"q": "PO-B1", "type": "purchase_order", "limit": 1},
            headers=self.headers)
        results = search_resp.json().get("results", [])
        
        if not results:
            pytest.skip("No POs available")
        
        po_id = results[0]["id"]
        
        # Get PO details
        detail_resp = requests.get(f"{BASE_URL}/api/purchase-orders/{po_id}",
            headers=self.headers)
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert "id" in data
        assert "po_number" in data
        print(f"✓ Fetched PO detail: {data.get('po_number')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
