"""
Tests for SaaS Multi-tenancy Features:
- Landing page / plans endpoint
- Organization self-registration
- Login with email or username
- Super admin access
- /auth/me subscription info
- Regular user cannot access superadmin endpoints
- Existing user (owner/521325) login
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test registration data (unique email to avoid conflicts)
TEST_ORG_EMAIL = f"test_saas_{int(time.time())}@testcompany.com"
TEST_ORG_COMPANY = f"Test Company {int(time.time())}"
TEST_ORG_PASSWORD = "TestPass@1234"
TEST_ORG_NAME = "Test Admin User"

SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
SUPER_ADMIN_PASSWORD = "Aa@58798546521325"
OWNER_USERNAME = "owner"
OWNER_PASSWORD = "521325"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def owner_token(session):
    """Get token for existing owner user."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": OWNER_USERNAME,
        "password": OWNER_PASSWORD
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Owner login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def super_admin_token(session):
    """Get token for super admin."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Super admin login failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def new_org_token(session):
    """Register a new org and get token."""
    # Register new org
    reg_resp = session.post(f"{BASE_URL}/api/organizations/register", json={
        "company_name": TEST_ORG_COMPANY,
        "admin_email": TEST_ORG_EMAIL,
        "admin_password": TEST_ORG_PASSWORD,
        "admin_name": TEST_ORG_NAME,
        "phone": "+63 9123456789"
    })
    if reg_resp.status_code not in [200, 201]:
        pytest.skip(f"Registration failed: {reg_resp.status_code} {reg_resp.text}")

    # Login with new org email
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ORG_EMAIL,
        "password": TEST_ORG_PASSWORD
    })
    if login_resp.status_code != 200:
        pytest.skip(f"New org login failed: {login_resp.status_code} {login_resp.text}")
    return login_resp.json().get("token")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Plans endpoint (public)
# ─────────────────────────────────────────────────────────────────────────────
class TestPlansEndpoint:
    """Public plans API - no auth required"""

    def test_plans_returns_200(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_plans_has_three_plans(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        data = resp.json()
        assert "plans" in data, "Response missing 'plans' key"
        assert len(data["plans"]) == 3, f"Expected 3 plans, got {len(data['plans'])}"

    def test_plans_basic_php_1500(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        plans = {p["key"]: p for p in resp.json()["plans"]}
        assert "basic" in plans
        assert plans["basic"]["pricing"]["php"] == 1500, f"Basic PHP price wrong: {plans['basic']['pricing']['php']}"

    def test_plans_standard_php_4000(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        plans = {p["key"]: p for p in resp.json()["plans"]}
        assert "standard" in plans
        assert plans["standard"]["pricing"]["php"] == 4000

    def test_plans_pro_php_7500(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        plans = {p["key"]: p for p in resp.json()["plans"]}
        assert "pro" in plans
        assert plans["pro"]["pricing"]["php"] == 7500

    def test_plans_has_trial_info(self, session):
        resp = session.get(f"{BASE_URL}/api/organizations/plans")
        data = resp.json()
        assert "trial_days" in data
        assert data["trial_days"] == 14


# ─────────────────────────────────────────────────────────────────────────────
# 2. Organization self-registration
# ─────────────────────────────────────────────────────────────────────────────
class TestOrganizationRegistration:
    """Test new company self-registration"""

    def test_register_new_org_success(self, session):
        unique_email = f"reg_{int(time.time())}@newcompany.com"
        resp = session.post(f"{BASE_URL}/api/organizations/register", json={
            "company_name": "New Company Ltd",
            "admin_email": unique_email,
            "admin_password": "SecurePass@123",
            "admin_name": "New Admin"
        })
        assert resp.status_code in [200, 201], f"Registration failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        assert "organization_id" in data
        assert "trial_ends_at" in data

    def test_register_duplicate_email_fails(self, session):
        # Register a fresh email first
        dup_email = f"dup_test_{int(time.time())}@duptest.com"
        first = session.post(f"{BASE_URL}/api/organizations/register", json={
            "company_name": "First Company",
            "admin_email": dup_email,
            "admin_password": "FirstPass@123",
            "admin_name": "First Admin"
        })
        assert first.status_code in [200, 201], f"First registration failed: {first.status_code}"

        # Try to register with same email again
        resp = session.post(f"{BASE_URL}/api/organizations/register", json={
            "company_name": "Duplicate Company",
            "admin_email": dup_email,
            "admin_password": "DupPass@123",
            "admin_name": "Dup Admin"
        })
        # Should fail with 400 (email already registered)
        assert resp.status_code in [400, 409], f"Expected 400/409 for duplicate email, got {resp.status_code}"

    def test_register_missing_required_fields_fails(self, session):
        resp = session.post(f"{BASE_URL}/api/organizations/register", json={
            "company_name": "Incomplete Company"
            # Missing admin_email, admin_password, admin_name
        })
        assert resp.status_code == 400, f"Expected 400 for missing fields, got {resp.status_code}"

    def test_register_creates_trial_subscription(self, session):
        unique_email = f"trial_{int(time.time())}@trialtest.com"
        resp = session.post(f"{BASE_URL}/api/organizations/register", json={
            "company_name": "Trial Test Corp",
            "admin_email": unique_email,
            "admin_password": "TrialPass@123",
            "admin_name": "Trial Admin"
        })
        assert resp.status_code in [200, 201]
        data = resp.json()
        # Verify trial info in response
        assert "trial_ends_at" in data
        trial_end = data["trial_ends_at"]
        assert trial_end is not None and len(trial_end) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Login tests
# ─────────────────────────────────────────────────────────────────────────────
class TestLogin:
    """Test login with email and username"""

    def test_owner_login_with_username(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": OWNER_USERNAME,
            "password": OWNER_PASSWORD
        })
        assert resp.status_code == 200, f"Owner login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) > 0

    def test_owner_login_returns_user(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": OWNER_USERNAME,
            "password": OWNER_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert data["user"]["username"] == OWNER_USERNAME or data["user"].get("role") is not None

    def test_super_admin_login_with_email(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Super admin login failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data

    def test_super_admin_has_is_super_admin_flag(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"].get("is_super_admin") is True

    def test_new_org_login_with_email(self, session):
        # new_org_token fixture already registers, just login directly
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ORG_EMAIL,
            "password": TEST_ORG_PASSWORD
        })
        assert resp.status_code == 200, f"New org email login failed: {resp.status_code} {resp.text}"

    def test_invalid_credentials_returns_401(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent@fake.com",
            "password": "WrongPassword"
        })
        assert resp.status_code == 401

    def test_login_returns_subscription_for_org_user(self, session):
        """New org user's login should include subscription info"""
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ORG_EMAIL,
            "password": TEST_ORG_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        # Subscription info should be present
        assert "subscription" in data, "No subscription key in login response"
        sub = data["subscription"]
        assert sub is not None
        assert "plan" in sub
        assert "effective_plan" in sub

    def test_login_new_org_has_trial_plan(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ORG_EMAIL,
            "password": TEST_ORG_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        sub = data.get("subscription", {})
        assert sub.get("plan") == "trial", f"Expected trial plan, got: {sub.get('plan')}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. /auth/me endpoint
# ─────────────────────────────────────────────────────────────────────────────
class TestAuthMe:
    """Test /auth/me returns correct user + subscription info"""

    def test_auth_me_with_owner_token(self, session, owner_token):
        resp = session.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data or "username" in data

    def test_auth_me_with_new_org_token(self, session, new_org_token):
        resp = session.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {new_org_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "subscription" in data, "auth/me should return subscription for org user"

    def test_auth_me_subscription_has_plan(self, session, new_org_token):
        resp = session.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {new_org_token}"})
        data = resp.json()
        sub = data.get("subscription", {})
        assert "plan" in sub
        assert "effective_plan" in sub
        assert "features" in sub

    def test_auth_me_trial_features(self, session, new_org_token):
        resp = session.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {new_org_token}"})
        data = resp.json()
        sub = data.get("subscription", {})
        features = sub.get("features", {})
        # Trial should have all Pro features
        assert features.get("audit_center") == "full"
        assert features.get("transaction_verification") is True

    def test_auth_me_without_token_returns_401(self, session):
        resp = session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 5. Super admin endpoints
# ─────────────────────────────────────────────────────────────────────────────
class TestSuperAdmin:
    """Test super admin access and organization management"""

    def test_superadmin_stats_accessible(self, session, super_admin_token):
        resp = session.get(f"{BASE_URL}/api/superadmin/stats",
                          headers={"Authorization": f"Bearer {super_admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_organizations" in data
        assert "trial" in data
        assert "active" in data

    def test_superadmin_stats_shows_positive_org_count(self, session, super_admin_token):
        resp = session.get(f"{BASE_URL}/api/superadmin/stats",
                          headers={"Authorization": f"Bearer {super_admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_organizations"] >= 1

    def test_superadmin_list_organizations(self, session, super_admin_token):
        resp = session.get(f"{BASE_URL}/api/superadmin/organizations",
                          headers={"Authorization": f"Bearer {super_admin_token}"})
        assert resp.status_code == 200
        orgs = resp.json()
        assert isinstance(orgs, list)
        assert len(orgs) >= 1

    def test_superadmin_orgs_have_required_fields(self, session, super_admin_token):
        resp = session.get(f"{BASE_URL}/api/superadmin/organizations",
                          headers={"Authorization": f"Bearer {super_admin_token}"})
        orgs = resp.json()
        assert len(orgs) > 0
        org = orgs[0]
        required_fields = ["id", "name", "plan", "subscription_status"]
        for field in required_fields:
            assert field in org, f"Missing field '{field}' in org: {org.keys()}"

    def test_regular_user_cannot_access_superadmin(self, session, owner_token):
        """Regular admin user should not access superadmin endpoints"""
        resp = session.get(f"{BASE_URL}/api/superadmin/stats",
                          headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_unauthenticated_cannot_access_superadmin(self, session):
        resp = session.get(f"{BASE_URL}/api/superadmin/stats")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_superadmin_stats_has_by_plan_breakdown(self, session, super_admin_token):
        resp = session.get(f"{BASE_URL}/api/superadmin/stats",
                          headers={"Authorization": f"Bearer {super_admin_token}"})
        data = resp.json()
        assert "by_plan" in data
        assert "total_users" in data


# ─────────────────────────────────────────────────────────────────────────────
# 6. Dashboard loads after login
# ─────────────────────────────────────────────────────────────────────────────
class TestDashboardAfterLogin:
    """Verify existing app features still work after multi-tenancy migration"""

    def test_owner_can_access_dashboard(self, session, owner_token):
        resp = session.get(f"{BASE_URL}/api/dashboard/summary",
                          headers={"Authorization": f"Bearer {owner_token}"})
        # Should return 200 (may return 400 if no branch selected)
        assert resp.status_code in [200, 400], f"Unexpected status: {resp.status_code} {resp.text}"

    def test_owner_can_list_branches(self, session, owner_token):
        resp = session.get(f"{BASE_URL}/api/branches",
                          headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_owner_can_list_products(self, session, owner_token):
        resp = session.get(f"{BASE_URL}/api/products",
                          headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200

    def test_new_org_has_empty_branches(self, session, new_org_token):
        """New org should have no branches yet"""
        resp = session.get(f"{BASE_URL}/api/branches",
                          headers={"Authorization": f"Bearer {new_org_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # New org starts with 0 branches (no default branch created by registration)
        assert len(data) == 0, f"New org should have 0 branches initially, got {len(data)}"

    def test_new_org_data_isolated_from_owner_data(self, session, owner_token, new_org_token):
        """New org should not see owner's products"""
        owner_resp = session.get(f"{BASE_URL}/api/products",
                                headers={"Authorization": f"Bearer {owner_token}"})
        new_org_resp = session.get(f"{BASE_URL}/api/products",
                                  headers={"Authorization": f"Bearer {new_org_token}"})
        assert owner_resp.status_code == 200
        assert new_org_resp.status_code == 200

        # Get product counts
        owner_data = owner_resp.json()
        new_org_data = new_org_resp.json()

        owner_count = owner_data.get("total", len(owner_data.get("products", []))) if isinstance(owner_data, dict) else len(owner_data)
        new_org_count = new_org_data.get("total", len(new_org_data.get("products", []))) if isinstance(new_org_data, dict) else len(new_org_data)

        # New org should have 0 products, owner org may have some
        assert new_org_count == 0, f"New org should have 0 products (tenant isolation), got {new_org_count}"
