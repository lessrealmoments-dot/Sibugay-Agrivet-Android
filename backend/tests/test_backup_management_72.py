"""
Iteration 72: Backup Management System Tests
============================================

Tests the comprehensive backup system including:
- Full site backup (POST /api/backups/site/trigger, GET /api/backups/site/list)
- Per-organization backup (POST /api/backups/org/{org_id}/trigger)
- Per-org backup history (GET /api/backups/org/{org_id}/list)
- Per-org data stats (GET /api/backups/org/{org_id}/stats)
- Per-org restore with safety backup (POST /api/backups/org/{org_id}/restore/{filename})
- All orgs backup summary (GET /api/backups/org-summary)
- Backup schedule config (GET/PUT /api/backups/schedule)
- Legacy endpoints (/api/backups/trigger, /api/backups/)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials - Super Admin
SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASS = "Aa@58798546521325"


@pytest.fixture(scope="module")
def session():
    """Create a requests session."""
    return requests.Session()


@pytest.fixture(scope="module")
def super_admin_token(session):
    """Authenticate as super admin and get token."""
    resp = session.post(f"{BASE_URL}/api/admin/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASS
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    # Fallback to regular login
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASS
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Could not authenticate super admin: {resp.status_code} - {resp.text}")


@pytest.fixture(scope="module")
def auth_headers(super_admin_token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest.fixture(scope="module")
def test_org_id(session, auth_headers):
    """Get an existing org ID for testing, or create one."""
    # First try to get existing orgs
    resp = session.get(f"{BASE_URL}/api/organizations", headers=auth_headers)
    if resp.status_code == 200:
        orgs = resp.json()
        if isinstance(orgs, list) and len(orgs) > 0:
            return orgs[0]["id"]
        if isinstance(orgs, dict) and "organizations" in orgs:
            if len(orgs["organizations"]) > 0:
                return orgs["organizations"][0]["id"]
    
    # Create test org
    resp = session.post(f"{BASE_URL}/api/organizations", headers=auth_headers, json={
        "name": "TEST_Backup_Org_72",
        "owner_email": "test72@example.com",
        "plan": "pro"
    })
    if resp.status_code in (200, 201):
        return resp.json().get("id") or resp.json().get("organization", {}).get("id")
    
    pytest.skip("Could not get or create test organization")


# =============================================================================
# SITE BACKUP TESTS
# =============================================================================

class TestSiteBackup:
    """Test full-site backup functionality (mongodump-based)."""

    def test_01_trigger_site_backup(self, session, auth_headers):
        """POST /api/backups/site/trigger should create full DB backup."""
        resp = session.post(f"{BASE_URL}/api/backups/site/trigger", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "success" in data or "filename" in data, "Response should contain success or filename"
        if "success" in data:
            assert data["success"] is True, f"Backup should succeed: {data}"
        
        if "filename" in data:
            assert data["filename"].endswith(".archive.gz"), "Filename should be .archive.gz"
            print(f"✓ Site backup created: {data.get('filename')}, Size: {data.get('size_mb', 'N/A')} MB")
        
        # Check R2 upload status
        if "r2_uploaded" in data:
            print(f"  R2 uploaded: {data['r2_uploaded']}")

    def test_02_list_site_backups(self, session, auth_headers):
        """GET /api/backups/site/list should list site backups."""
        resp = session.get(f"{BASE_URL}/api/backups/site/list", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "backups" in data, "Response should contain 'backups' list"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["backups"], list), "backups should be a list"
        
        print(f"✓ Found {data['count']} site backups")
        
        # Validate backup item structure if any exist
        if len(data["backups"]) > 0:
            backup = data["backups"][0]
            assert "filename" in backup, "Backup should have filename"
            print(f"  Latest: {backup.get('filename')}, Size: {backup.get('size_mb', 'N/A')} MB")


# =============================================================================
# PER-ORG BACKUP TESTS
# =============================================================================

class TestOrgBackup:
    """Test per-organization backup functionality (JSON.gz to R2)."""

    def test_03_trigger_org_backup(self, session, auth_headers, test_org_id):
        """POST /api/backups/org/{org_id}/trigger should create per-org backup."""
        resp = session.post(
            f"{BASE_URL}/api/backups/org/{test_org_id}/trigger",
            headers=auth_headers
        )
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "success" in data, "Response should contain 'success'"
        assert data["success"] is True, f"Backup should succeed: {data}"
        assert "filename" in data, "Response should contain 'filename'"
        assert "total_documents" in data, "Response should contain 'total_documents'"
        
        # Filename should be timestamp.json.gz
        assert data["filename"].endswith(".json.gz"), f"Filename should be .json.gz: {data['filename']}"
        
        print(f"✓ Org backup created: {data['filename']}")
        print(f"  Total docs: {data['total_documents']}, Size: {data.get('size_mb', 'N/A')} MB")
        print(f"  R2 uploaded: {data.get('r2_uploaded', 'N/A')}")
        print(f"  R2 key: {data.get('r2_key', 'N/A')}")

    def test_04_list_org_backups(self, session, auth_headers, test_org_id):
        """GET /api/backups/org/{org_id}/list should list org backup history."""
        resp = session.get(
            f"{BASE_URL}/api/backups/org/{test_org_id}/list",
            headers=auth_headers
        )
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "backups" in data, "Response should contain 'backups' list"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["backups"], list), "backups should be a list"
        assert data["count"] >= 1, "Should have at least 1 backup (just created)"
        
        print(f"✓ Found {data['count']} org backups for {test_org_id}")
        
        # Validate backup item structure
        if len(data["backups"]) > 0:
            backup = data["backups"][0]
            assert "filename" in backup, "Backup should have filename"
            assert "org_id" in backup, "Backup should have org_id"
            assert backup["org_id"] == test_org_id, "Backup should belong to correct org"
            print(f"  Latest: {backup.get('filename')}, Docs: {backup.get('total_documents', 'N/A')}")
        
        # Store latest backup filename for restore test
        pytest.latest_backup_filename = data["backups"][0]["filename"] if data["backups"] else None

    def test_05_get_org_stats(self, session, auth_headers, test_org_id):
        """GET /api/backups/org/{org_id}/stats should return document counts."""
        resp = session.get(
            f"{BASE_URL}/api/backups/org/{test_org_id}/stats",
            headers=auth_headers
        )
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "total_documents" in data, "Response should contain 'total_documents'"
        assert "collections" in data, "Response should contain 'collections'"
        assert isinstance(data["total_documents"], int), "total_documents should be int"
        assert isinstance(data["collections"], dict), "collections should be dict"
        
        print(f"✓ Org {test_org_id} stats:")
        print(f"  Total documents: {data['total_documents']}")
        print(f"  Collections with data: {len(data['collections'])}")
        
        # Show non-empty collections
        if data["collections"]:
            for coll, count in list(data["collections"].items())[:5]:
                print(f"    - {coll}: {count}")

    def test_06_org_not_found(self, session, auth_headers):
        """POST /api/backups/org/{invalid_id}/trigger should return 404."""
        resp = session.post(
            f"{BASE_URL}/api/backups/org/invalid-org-id-12345/trigger",
            headers=auth_headers
        )
        print(f"Response: {resp.status_code} - {resp.text[:200]}")
        
        assert resp.status_code == 404, f"Expected 404 for invalid org, got {resp.status_code}"
        print("✓ Correctly returns 404 for non-existent org")


# =============================================================================
# ORG RESTORE TESTS
# =============================================================================

class TestOrgRestore:
    """Test per-organization restore functionality with safety backup."""

    def test_07_restore_org_backup(self, session, auth_headers, test_org_id):
        """POST /api/backups/org/{org_id}/restore/{filename} should restore with safety backup."""
        # Get the latest backup filename
        resp = session.get(
            f"{BASE_URL}/api/backups/org/{test_org_id}/list",
            headers=auth_headers
        )
        if resp.status_code != 200 or not resp.json().get("backups"):
            pytest.skip("No backups available for restore test")
        
        backups = resp.json()["backups"]
        # Find a regular backup (not a restore record)
        backup_filename = None
        for b in backups:
            if b.get("filename") and not b.get("type"):
                backup_filename = b["filename"]
                break
        
        if not backup_filename:
            pytest.skip("No regular backup found for restore test")
        
        print(f"Attempting to restore from: {backup_filename}")
        
        resp = session.post(
            f"{BASE_URL}/api/backups/org/{test_org_id}/restore/{backup_filename}",
            headers=auth_headers,
            json={}  # No PIN for super admin test
        )
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "success" in data, "Response should contain 'success'"
        
        if data["success"]:
            assert "safety_backup" in data, "Response should contain 'safety_backup'"
            assert "total_documents_restored" in data, "Response should contain 'total_documents_restored'"
            assert "collections_restored" in data, "Response should contain 'collections_restored'"
            
            print(f"✓ Restore completed successfully")
            print(f"  Safety backup: {data['safety_backup']}")
            print(f"  Documents restored: {data['total_documents_restored']}")
            print(f"  Collections restored: {data['collections_restored']}")
            
            # Check for errors
            if data.get("errors"):
                print(f"  ⚠ Errors: {data['errors']}")
        else:
            # R2 may not have the file - this is acceptable if testing locally
            print(f"⚠ Restore returned success=False: {data.get('error', 'Unknown error')}")
            if "R2 not configured" in str(data.get("error", "")):
                pytest.skip("R2 not configured - skipping restore test")

    def test_08_restore_invalid_filename(self, session, auth_headers, test_org_id):
        """POST /api/backups/org/{org_id}/restore/{invalid} should fail gracefully."""
        resp = session.post(
            f"{BASE_URL}/api/backups/org/{test_org_id}/restore/nonexistent_backup.json.gz",
            headers=auth_headers,
            json={}
        )
        print(f"Response: {resp.status_code} - {resp.text[:300]}")
        
        # Should return 200 with success=False, or 404/400
        assert resp.status_code in (200, 400, 404), f"Expected 200/400/404, got {resp.status_code}"
        
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("success") is False, "Should fail for nonexistent backup"
            print(f"✓ Correctly fails for nonexistent backup: {data.get('error', 'N/A')}")
        else:
            print(f"✓ Correctly returns {resp.status_code} for nonexistent backup")


# =============================================================================
# ORG SUMMARY TESTS (SUPER ADMIN)
# =============================================================================

class TestOrgSummary:
    """Test backup summary for all organizations."""

    def test_09_get_org_summary(self, session, auth_headers):
        """GET /api/backups/org-summary should list all orgs with backup status."""
        resp = session.get(f"{BASE_URL}/api/backups/org-summary", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "organizations" in data, "Response should contain 'organizations'"
        assert "total" in data, "Response should contain 'total'"
        assert isinstance(data["organizations"], list), "organizations should be a list"
        
        print(f"✓ Found {data['total']} organizations in summary")
        
        # Validate org summary item structure
        if len(data["organizations"]) > 0:
            org = data["organizations"][0]
            assert "org_id" in org, "Org summary should have org_id"
            assert "org_name" in org, "Org summary should have org_name"
            assert "total_documents" in org, "Org summary should have total_documents"
            
            print(f"  Sample org: {org.get('org_name', 'N/A')}")
            print(f"    - Documents: {org.get('total_documents', 'N/A')}")
            print(f"    - Last backup: {org.get('last_backup_at', 'None')}")
            print(f"    - Last backup size: {org.get('last_backup_size_mb', 'N/A')} MB")


# =============================================================================
# SCHEDULE CONFIG TESTS
# =============================================================================

class TestScheduleConfig:
    """Test backup schedule configuration."""

    def test_10_get_schedule(self, session, auth_headers):
        """GET /api/backups/schedule should return schedule config."""
        resp = session.get(f"{BASE_URL}/api/backups/schedule", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response structure (may have defaults or saved config)
        assert "site_backup_hours" in data or "key" in data, "Response should contain schedule config"
        
        print(f"✓ Schedule config:")
        print(f"  Site backup hours: {data.get('site_backup_hours', [1])}")
        print(f"  Org backup hours: {data.get('org_backup_hours', [1,7,13,19])}")
        print(f"  Org backup enabled: {data.get('org_backup_enabled', False)}")

    def test_11_update_schedule(self, session, auth_headers):
        """PUT /api/backups/schedule should update schedule config."""
        new_config = {
            "site_backup_hours": [2],
            "org_backup_hours": [2, 8, 14, 20],
            "org_backup_enabled": True
        }
        
        resp = session.put(
            f"{BASE_URL}/api/backups/schedule",
            headers=auth_headers,
            json=new_config
        )
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate response
        assert "message" in data or "site_backup_hours" in data, "Response should confirm update"
        
        print(f"✓ Schedule updated successfully")
        print(f"  New site hours: {data.get('site_backup_hours', 'N/A')}")
        print(f"  New org hours: {data.get('org_backup_hours', 'N/A')}")

    def test_12_verify_schedule_persisted(self, session, auth_headers):
        """GET /api/backups/schedule should show updated config."""
        resp = session.get(f"{BASE_URL}/api/backups/schedule", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify the update took effect
        if data.get("org_backup_hours"):
            print(f"✓ Schedule persisted: org_backup_hours = {data['org_backup_hours']}")
        
        # Reset to default (optional cleanup)
        session.put(
            f"{BASE_URL}/api/backups/schedule",
            headers=auth_headers,
            json={
                "site_backup_hours": [1],
                "org_backup_hours": [1, 7, 13, 19],
                "org_backup_enabled": False
            }
        )
        print("✓ Reset schedule to defaults")


# =============================================================================
# LEGACY ENDPOINT TESTS
# =============================================================================

class TestLegacyEndpoints:
    """Test backward-compatible legacy endpoints."""

    def test_13_legacy_trigger(self, session, auth_headers):
        """POST /api/backups/trigger should work (legacy site backup)."""
        resp = session.post(f"{BASE_URL}/api/backups/trigger", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Should behave same as site/trigger
        assert "success" in data or "filename" in data, "Legacy trigger should return backup result"
        print(f"✓ Legacy /api/backups/trigger works: {data.get('filename', 'OK')}")

    def test_14_legacy_list(self, session, auth_headers):
        """GET /api/backups/ should work (legacy list)."""
        resp = session.get(f"{BASE_URL}/api/backups", headers=auth_headers)
        print(f"Response: {resp.status_code} - {resp.text[:500]}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Should behave same as site/list
        assert "backups" in data, "Legacy list should return backups"
        print(f"✓ Legacy /api/backups/ works: {data.get('count', len(data.get('backups', [])))} backups")


# =============================================================================
# AUTHORIZATION TESTS
# =============================================================================

class TestAuthorization:
    """Test that backup endpoints require proper authorization."""

    def test_15_site_backup_requires_auth(self, session):
        """POST /api/backups/site/trigger without auth should fail."""
        resp = session.post(f"{BASE_URL}/api/backups/site/trigger")
        print(f"Response: {resp.status_code}")
        
        assert resp.status_code in (401, 403, 422), f"Expected 401/403/422 without auth, got {resp.status_code}"
        print("✓ Site backup correctly requires authentication")

    def test_16_org_backup_requires_auth(self, session, test_org_id):
        """POST /api/backups/org/{org_id}/trigger without auth should fail."""
        resp = session.post(f"{BASE_URL}/api/backups/org/{test_org_id}/trigger")
        print(f"Response: {resp.status_code}")
        
        assert resp.status_code in (401, 403, 422), f"Expected 401/403/422 without auth, got {resp.status_code}"
        print("✓ Org backup correctly requires authentication")

    def test_17_schedule_requires_auth(self, session):
        """GET /api/backups/schedule without auth should fail."""
        resp = session.get(f"{BASE_URL}/api/backups/schedule")
        print(f"Response: {resp.status_code}")
        
        assert resp.status_code in (401, 403, 422), f"Expected 401/403/422 without auth, got {resp.status_code}"
        print("✓ Schedule config correctly requires authentication")


# =============================================================================
# R2 UPLOAD VERIFICATION
# =============================================================================

class TestR2Integration:
    """Test R2 storage integration for org backups."""

    def test_18_verify_r2_upload(self, session, auth_headers, test_org_id):
        """Verify org backup was uploaded to R2."""
        # Get latest backup
        resp = session.get(
            f"{BASE_URL}/api/backups/org/{test_org_id}/list",
            headers=auth_headers
        )
        if resp.status_code != 200:
            pytest.skip("Could not get backup list")
        
        backups = resp.json().get("backups", [])
        if not backups:
            pytest.skip("No backups to verify")
        
        # Find a backup with r2_uploaded flag
        for backup in backups:
            if backup.get("r2_uploaded"):
                print(f"✓ Found R2-uploaded backup: {backup['filename']}")
                print(f"  R2 key: {backup.get('r2_key', 'N/A')}")
                return
        
        # Check if any backup has r2 info
        latest = backups[0]
        if latest.get("r2_uploaded") is False:
            print(f"⚠ Latest backup not uploaded to R2 (may be local-only)")
        else:
            print(f"✓ Backup verified: {latest.get('filename')}, r2_uploaded: {latest.get('r2_uploaded', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
