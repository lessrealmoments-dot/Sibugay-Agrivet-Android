"""
Tests for Supplier CRUD endpoints

Features tested:
- GET /suppliers - List all suppliers
- POST /suppliers - Create a new supplier
- PUT /suppliers/{id} - Update supplier details
- DELETE /suppliers/{id} - Soft delete a supplier
- GET /suppliers/search - Search suppliers by name
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in response"
    return data["token"]

@pytest.fixture(scope="module")
def api_client(auth_token):
    """Shared requests session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestSupplierCRUD:
    """Test Supplier CRUD operations"""
    
    def test_list_suppliers(self, api_client):
        """Test GET /suppliers returns list of suppliers"""
        response = api_client.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200, f"Failed to list suppliers: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} suppliers")
    
    def test_create_supplier_success(self, api_client):
        """Test POST /suppliers creates a new supplier"""
        unique_name = f"TEST_Supplier_{uuid.uuid4().hex[:8]}"
        create_payload = {
            "name": unique_name,
            "contact_person": "John Doe",
            "phone": "09123456789",
            "email": "john@testsupplier.com",
            "address": "123 Test Street, Test City",
            "notes": "Test supplier created for testing"
        }
        response = api_client.post(f"{BASE_URL}/api/suppliers", json=create_payload)
        assert response.status_code == 200, f"Failed to create supplier: {response.text}"
        
        data = response.json()
        assert data["name"] == unique_name, "Name mismatch"
        assert data["contact_person"] == "John Doe", "Contact person mismatch"
        assert data["phone"] == "09123456789", "Phone mismatch"
        assert data["email"] == "john@testsupplier.com", "Email mismatch"
        assert data["address"] == "123 Test Street, Test City", "Address mismatch"
        assert "id" in data, "No ID returned"
        
        # Verify persistence via GET
        get_response = api_client.get(f"{BASE_URL}/api/suppliers")
        assert get_response.status_code == 200
        suppliers = get_response.json()
        found = [s for s in suppliers if s["name"] == unique_name]
        assert len(found) == 1, f"Supplier not found after creation"
        print(f"Created supplier: {data['name']} with ID: {data['id']}")
        
        # Return for cleanup
        return data
    
    def test_create_supplier_name_required(self, api_client):
        """Test POST /suppliers fails without name"""
        response = api_client.post(f"{BASE_URL}/api/suppliers", json={
            "contact_person": "No Name Person",
            "phone": "09123456789"
        })
        assert response.status_code == 400, f"Should fail without name, got: {response.status_code}"
        assert "required" in response.json().get("detail", "").lower(), "Should mention name is required"
    
    def test_create_supplier_duplicate_name(self, api_client):
        """Test POST /suppliers fails with duplicate name"""
        unique_name = f"TEST_DupSupplier_{uuid.uuid4().hex[:8]}"
        
        # Create first supplier
        response1 = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert response2.status_code == 400, f"Should fail on duplicate, got: {response2.status_code}"
        assert "exists" in response2.json().get("detail", "").lower(), "Should mention supplier exists"
    
    def test_update_supplier(self, api_client):
        """Test PUT /suppliers/{id} updates supplier details"""
        # Create a supplier first
        unique_name = f"TEST_UpdateSupplier_{uuid.uuid4().hex[:8]}"
        create_response = api_client.post(f"{BASE_URL}/api/suppliers", json={
            "name": unique_name,
            "contact_person": "Original Person"
        })
        assert create_response.status_code == 200
        supplier_id = create_response.json()["id"]
        
        # Update the supplier
        update_payload = {
            "contact_person": "Updated Person",
            "phone": "09999999999",
            "email": "updated@email.com"
        }
        update_response = api_client.put(f"{BASE_URL}/api/suppliers/{supplier_id}", json=update_payload)
        assert update_response.status_code == 200, f"Failed to update: {update_response.text}"
        
        updated = update_response.json()
        assert updated["contact_person"] == "Updated Person", "Contact person not updated"
        assert updated["phone"] == "09999999999", "Phone not updated"
        assert updated["email"] == "updated@email.com", "Email not updated"
        
        # Verify via GET
        get_response = api_client.get(f"{BASE_URL}/api/suppliers")
        suppliers = get_response.json()
        found = [s for s in suppliers if s["id"] == supplier_id]
        assert len(found) == 1
        assert found[0]["contact_person"] == "Updated Person"
        print(f"Updated supplier {supplier_id}")
    
    def test_delete_supplier(self, api_client):
        """Test DELETE /suppliers/{id} soft deletes supplier"""
        # Create a supplier to delete
        unique_name = f"TEST_DeleteSupplier_{uuid.uuid4().hex[:8]}"
        create_response = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert create_response.status_code == 200
        supplier_id = create_response.json()["id"]
        
        # Delete the supplier
        delete_response = api_client.delete(f"{BASE_URL}/api/suppliers/{supplier_id}")
        assert delete_response.status_code == 200, f"Failed to delete: {delete_response.text}"
        
        # Verify it's no longer in list (soft deleted)
        get_response = api_client.get(f"{BASE_URL}/api/suppliers")
        suppliers = get_response.json()
        found = [s for s in suppliers if s["id"] == supplier_id]
        assert len(found) == 0, "Deleted supplier should not appear in list"
        print(f"Deleted supplier {supplier_id}")
    
    def test_search_suppliers(self, api_client):
        """Test GET /suppliers/search?q= returns matching suppliers"""
        # Create a supplier with unique name for search
        unique_prefix = f"SRCH_{uuid.uuid4().hex[:6]}"
        unique_name = f"TEST_{unique_prefix}_SearchSupplier"
        create_response = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert create_response.status_code == 200
        
        # Search for it
        search_response = api_client.get(f"{BASE_URL}/api/suppliers/search", params={"q": unique_prefix})
        assert search_response.status_code == 200, f"Search failed: {search_response.text}"
        
        results = search_response.json()
        assert isinstance(results, list), "Search should return a list"
        found = [r for r in results if unique_prefix in r.get("name", "")]
        assert len(found) >= 1, f"Supplier not found in search results"
        print(f"Search for '{unique_prefix}' returned {len(results)} results")


class TestSupplierPurchaseOrderIntegration:
    """Test supplier integration with Purchase Orders"""
    
    def test_supplier_appears_in_po_vendor_list(self, api_client):
        """Test that suppliers appear in PO vendor list after creation"""
        # Create a unique supplier
        unique_name = f"TEST_POInteg_{uuid.uuid4().hex[:8]}"
        create_response = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert create_response.status_code == 200
        
        # Search should find it
        search_response = api_client.get(f"{BASE_URL}/api/suppliers/search", params={"q": unique_name[:10]})
        assert search_response.status_code == 200
        results = search_response.json()
        found = [r for r in results if unique_name in r.get("name", "")]
        assert len(found) >= 1, "Created supplier should appear in search"
        print(f"Supplier {unique_name} found in search for PO creation")
    
    def test_quick_create_supplier_minimal_fields(self, api_client):
        """Test quick-create supplier with minimal fields (just name)"""
        unique_name = f"TEST_Quick_{uuid.uuid4().hex[:8]}"
        
        # Quick create with just name
        response = api_client.post(f"{BASE_URL}/api/suppliers", json={"name": unique_name})
        assert response.status_code == 200, f"Quick create failed: {response.text}"
        
        data = response.json()
        assert data["name"] == unique_name
        assert "id" in data
        # Optional fields should be empty strings
        assert data.get("contact_person", "") == ""
        assert data.get("phone", "") == ""
        print(f"Quick-created supplier: {unique_name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
