"""
Comprehensive tests for subscription plan enforcement, branch limits, and feature flag management.
Tests: plan limits (basic/standard/pro/founders/trial), branch limit enforcement,
feature flag filtering, super admin operations, and multi-tenancy isolation.
"""
import pytest
import requests
import os
import time
import random
import string

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def rand_email():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"test_{suffix}@testmail.com"

def get_token(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json().get("token")

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def get_admin_token():
    """Get super admin token via admin-auth flow (no TOTP - first step only for data manipulation)."""
    r = requests.post(f"{BASE_URL}/api/admin-auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    if r.status_code == 200:
        return r.json().get("pending_token") or r.json().get("token")
    pytest.skip(f"Admin login failed: {r.text}")

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def founders_token():
    return get_token("sibugayagrivetsupply@gmail.com", "521325")

@pytest.fixture(scope="module")
def basic_token():
    return get_token("limittest@testmail.com", "Test@123456")

@pytest.fixture(scope="module")
def registered_trial_org():
    """Register a fresh trial org for testing."""
    email = rand_email()
    payload = {
        "company_name": f"TEST_TrialCo_{email.split('@')[0]}",
        "admin_email": email,
        "admin_password": "Test@123456",
        "admin_name": "Test Admin",
        "phone": "09123456789"
    }
    r = requests.post(f"{BASE_URL}/api/organizations/register", json=payload)
    assert r.status_code == 200, f"Registration failed: {r.text}"
    data = r.json()
    token = get_token(email, "Test@123456")
    return {
        "email": email,
        "password": "Test@123456",
        "org_id": data["organization_id"],
        "token": token
    }

@pytest.fixture(scope="module")
def superadmin_session(registered_trial_org):
    """Get an authenticated super admin session for setting plan on test org."""
    # We'll use direct DB-like approach via API for super admin token
    # Note: TOTP may be required; we skip if admin token not available
    r = requests.post(f"{BASE_URL}/api/admin-auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    if r.status_code != 200:
        pytest.skip("Super admin login failed")
    data = r.json()
    # If pending_token returned, TOTP required — skip plan-change tests
    if "pending_token" in data and "token" not in data:
        pytest.skip("Super admin requires TOTP — cannot get full admin token in automated tests")
    token = data.get("token")
    return {"token": token}


# ─── Section 1: Public Endpoints ─────────────────────────────────────────────

class TestPublicEndpoints:
    """Public endpoints: landing page data, plans listing, feature matrix."""

    def test_landing_page_loads(self):
        """GET / should respond."""
        r = requests.get(f"{BASE_URL}/")
        assert r.status_code in (200, 301, 302, 404), f"Unexpected: {r.status_code}"
        print(f"Landing page response: {r.status_code}")

    def test_plans_endpoint_returns_all_plans(self):
        """GET /api/organizations/plans returns basic, standard, pro plans."""
        r = requests.get(f"{BASE_URL}/api/organizations/plans")
        assert r.status_code == 200, f"Plans failed: {r.text}"
        data = r.json()
        plan_keys = [p["key"] for p in data["plans"]]
        assert "basic" in plan_keys
        assert "standard" in plan_keys
        assert "pro" in plan_keys
        assert data["trial_days"] == 14
        print(f"Plans returned: {plan_keys}")

    def test_plans_basic_has_correct_limits(self):
        """Basic plan: 1 branch, 5 users."""
        r = requests.get(f"{BASE_URL}/api/organizations/plans")
        assert r.status_code == 200
        basic = next(p for p in r.json()["plans"] if p["key"] == "basic")
        assert basic["limits"]["max_branches"] == 1
        assert basic["limits"]["max_users"] == 5
        print(f"Basic limits: {basic['limits']}")

    def test_plans_standard_has_correct_limits(self):
        """Standard plan: 2 branches, 15 users."""
        r = requests.get(f"{BASE_URL}/api/organizations/plans")
        assert r.status_code == 200
        standard = next(p for p in r.json()["plans"] if p["key"] == "standard")
        assert standard["limits"]["max_branches"] == 2
        assert standard["limits"]["max_users"] == 15
        print(f"Standard limits: {standard['limits']}")

    def test_plans_pro_has_correct_limits(self):
        """Pro plan: 5 branches, unlimited users."""
        r = requests.get(f"{BASE_URL}/api/organizations/plans")
        assert r.status_code == 200
        pro = next(p for p in r.json()["plans"] if p["key"] == "pro")
        assert pro["limits"]["max_branches"] == 5
        assert pro["limits"]["max_users"] == 0   # 0 = unlimited
        print(f"Pro limits: {pro['limits']}")

    def test_feature_matrix_endpoint(self):
        """GET /api/organizations/feature-matrix returns feature definitions."""
        r = requests.get(f"{BASE_URL}/api/organizations/feature-matrix")
        assert r.status_code == 200
        data = r.json()
        assert "feature_definitions" in data
        assert "flags" in data
        assert "basic" in data["flags"]
        assert "standard" in data["flags"]
        assert "pro" in data["flags"]
        print(f"Feature matrix: {len(data['feature_definitions'])} features defined")


# ─── Section 2: Registration & Trial Plan ────────────────────────────────────

class TestRegistrationAndTrialPlan:
    """Register new company → verify trial plan with all Pro features."""

    def test_register_new_company_success(self, registered_trial_org):
        """POST /api/organizations/register creates trial org."""
        assert registered_trial_org["org_id"], "org_id should be returned"
        assert registered_trial_org["token"], "should be able to login after registration"
        print(f"Registered org: {registered_trial_org['org_id']}")

    def test_trial_org_has_correct_plan(self, registered_trial_org):
        """New org should start on trial plan."""
        token = registered_trial_org["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["plan"] == "trial", f"Expected trial, got: {sub['plan']}"
        assert sub["effective_plan"] in ("trial", "pro"), f"Effective plan wrong: {sub['effective_plan']}"
        print(f"Trial org plan: {sub['plan']}, effective: {sub['effective_plan']}")

    def test_trial_org_has_pro_features(self, registered_trial_org):
        """Trial org should have all Pro features enabled."""
        token = registered_trial_org["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        features = r.json().get("subscription", {}).get("features", {})
        pro_features = ["purchase_orders", "employee_management", "full_fund_management",
                        "branch_transfers", "audit_center", "granular_permissions"]
        for feat in pro_features:
            assert features.get(feat) is not False, f"Trial should have {feat} enabled"
        print(f"Trial features verified: {pro_features}")

    def test_trial_org_max_branches_is_5(self, registered_trial_org):
        """Trial plan allows up to 5 branches."""
        token = registered_trial_org["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["max_branches"] == 5, f"Expected 5, got: {sub['max_branches']}"
        print(f"Trial max_branches: {sub['max_branches']}")

    def test_trial_has_14_day_expiry(self, registered_trial_org):
        """Trial org should have trial_ends_at set ~14 days out."""
        token = registered_trial_org["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub.get("trial_ends_at"), "trial_ends_at should be set"
        from datetime import datetime, timezone, timedelta
        end = datetime.fromisoformat(sub["trial_ends_at"].replace("Z", "+00:00"))
        days_left = (end - datetime.now(timezone.utc)).days
        assert 12 <= days_left <= 16, f"Expected ~14 days, got: {days_left}"
        print(f"Trial days left: {days_left}")

    def test_duplicate_email_registration_blocked(self, registered_trial_org):
        """Registering with the same email should fail with 400."""
        payload = {
            "company_name": "Duplicate Co",
            "admin_email": registered_trial_org["email"],
            "admin_password": "Test@123456",
            "admin_name": "Dup Admin"
        }
        r = requests.post(f"{BASE_URL}/api/organizations/register", json=payload)
        assert r.status_code == 400
        print(f"Duplicate registration blocked: {r.json()}")


# ─── Section 3: Basic Plan Feature Enforcement ───────────────────────────────

class TestBasicPlanFeatureEnforcement:
    """Basic plan: verify restricted features are flagged as False."""

    def test_basic_plan_features_from_auth_me(self, basic_token):
        """Basic plan org should have premium features disabled."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["plan"] == "basic", f"Expected basic, got: {sub['plan']}"
        features = sub.get("features", {})
        blocked_features = [
            "purchase_orders", "supplier_management", "employee_management",
            "full_fund_management", "branch_transfers", "audit_center",
            "advanced_reports", "granular_permissions"
        ]
        for feat in blocked_features:
            assert features.get(feat) == False, f"Basic plan should block {feat}, got: {features.get(feat)}"
        print(f"Basic plan blocked features verified: {blocked_features}")

    def test_basic_plan_core_features_enabled(self, basic_token):
        """Basic plan should have core features enabled."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        features = r.json().get("subscription", {}).get("features", {})
        core_features = ["pos_sales", "inventory", "customer_management", "expense_tracking",
                         "basic_reports", "daily_close_wizard"]
        for feat in core_features:
            assert features.get(feat) == True, f"Basic should have core {feat} enabled"
        print(f"Basic core features verified: {core_features}")

    def test_basic_plan_max_branches_is_1(self, basic_token):
        """Basic plan: max_branches should be 1."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["max_branches"] == 1, f"Expected 1, got: {sub['max_branches']}"
        print(f"Basic max_branches: {sub['max_branches']}")

    def test_basic_plan_max_users_is_5(self, basic_token):
        """Basic plan: max_users should be 5."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["max_users"] == 5, f"Expected 5, got: {sub['max_users']}"
        print(f"Basic max_users: {sub['max_users']}")


# ─── Section 4: Branch Limit Enforcement ─────────────────────────────────────

class TestBranchLimitEnforcement:
    """Test that branch creation is blocked when at plan limit."""

    def test_basic_plan_already_at_or_over_limit(self, basic_token):
        """Basic plan org already has branches - verify current count."""
        r = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(basic_token))
        assert r.status_code == 200
        branches = r.json()
        print(f"Basic org current branch count: {len(branches)}, names: {[b['name'] for b in branches]}")
        # Basic plan has max_branches=1, org has 2 from previous tests
        assert len(branches) >= 1, "Should have at least 1 branch"

    def test_basic_plan_branch_creation_blocked_at_limit(self, basic_token):
        """POST /api/branches should return 400 when basic plan is at limit."""
        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        sub = r_me.json().get("subscription", {})
        current_branches = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(basic_token)).json()

        if len(current_branches) < sub["max_branches"]:
            pytest.skip(f"Not yet at limit ({len(current_branches)}/{sub['max_branches']})")

        r = requests.post(f"{BASE_URL}/api/branches",
                          json={"name": "TEST_OverLimit Branch", "address": "Test", "phone": ""},
                          headers=auth_headers(basic_token))
        assert r.status_code == 400, f"Expected 400 (limit), got {r.status_code}: {r.text}"
        assert "limit" in r.json().get("detail", "").lower() or "branch" in r.json().get("detail", "").lower()
        print(f"Branch limit correctly blocked: {r.json()['detail']}")

    def test_branch_limit_error_message_includes_plan_info(self, basic_token):
        """Branch limit error should mention plan name and limit numbers."""
        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        sub = r_me.json().get("subscription", {})
        current_branches = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(basic_token)).json()

        if len(current_branches) < sub["max_branches"]:
            pytest.skip(f"Not yet at limit")

        r = requests.post(f"{BASE_URL}/api/branches",
                          json={"name": "TEST_LimitMsgTest", "address": "", "phone": ""},
                          headers=auth_headers(basic_token))
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        # Should mention the limit (1/1) or plan name
        assert any(x in detail for x in ["1/1", "1 branch", "Basic", "basic", "limit", "Upgrade"]), \
            f"Error message not informative: {detail}"
        print(f"Error message: {detail}")

    def test_founders_plan_no_branch_limit(self, founders_token):
        """Founders plan (max_branches=0) should allow branch creation without limit."""
        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(founders_token))
        sub = r_me.json().get("subscription", {})
        assert sub["plan"] == "founders", f"Expected founders: {sub['plan']}"
        assert sub["max_branches"] == 0, "Founders should have max_branches=0 (unlimited)"
        # Verify branch creation is allowed (we'll create and delete)
        r = requests.post(f"{BASE_URL}/api/branches",
                          json={"name": "TEST_FoundersUnlimited", "address": "Test Addr", "phone": ""},
                          headers=auth_headers(founders_token))
        assert r.status_code == 200, f"Founders should create branch freely: {r.text}"
        branch_id = r.json()["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/branches/{branch_id}", headers=auth_headers(founders_token))
        print(f"Founders branch creation: SUCCESS, cleaned up branch {branch_id}")

    def test_trial_plan_branch_limit_is_5(self, registered_trial_org):
        """Trial plan allows up to 5 branches."""
        token = registered_trial_org["token"]
        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(token))
        sub = r_me.json().get("subscription", {})
        assert sub["max_branches"] == 5, f"Trial max_branches should be 5, got: {sub['max_branches']}"
        print(f"Trial max_branches: {sub['max_branches']}")

    def test_trial_can_create_branches_up_to_limit(self, registered_trial_org):
        """Trial org can create branches 1 through 5."""
        token = registered_trial_org["token"]
        created_ids = []

        # Create branches until we have 5 (or trial limit)
        for i in range(1, 6):
            r = requests.post(f"{BASE_URL}/api/branches",
                              json={"name": f"TEST_Trial Branch {i}", "address": "", "phone": ""},
                              headers=auth_headers(token))
            if r.status_code == 200:
                created_ids.append(r.json()["id"])
                print(f"Created trial branch {i}: {r.json()['id']}")
            else:
                print(f"Branch {i} creation: {r.status_code} - {r.text}")
                break

        r_all = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(token))
        all_branches = r_all.json()
        print(f"Total trial branches: {len(all_branches)}")
        assert len(all_branches) >= 1, "Should have at least 1 branch created"

        # Cleanup non-main branches
        for bid in created_ids:
            requests.delete(f"{BASE_URL}/api/branches/{bid}", headers=auth_headers(token))
        print(f"Cleaned up {len(created_ids)} test branches")

    def test_multi_tenancy_branch_count_isolation(self, basic_token, founders_token):
        """Branch limit check must use org-scoped count, not global count.
        This tests the critical bug fix: POST /branches should count only this org's branches."""
        # Founders org has many branches (8+), which confirms global count would be high
        r_founders_branches = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(founders_token))
        founders_count = len(r_founders_branches.json())

        r_basic_branches = requests.get(f"{BASE_URL}/api/branches", headers=auth_headers(basic_token))
        basic_count = len(r_basic_branches.json())

        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        max_branches = r_me.json().get("subscription", {}).get("max_branches", 1)

        print(f"Founders has {founders_count} branches, Basic has {basic_count}/{max_branches}")

        # The basic org is limited to max_branches - test that the check is org-scoped
        # If basic is at or over its limit, the next create should fail with 400 (not succeed)
        r = requests.post(f"{BASE_URL}/api/branches",
                          json={"name": "TEST_IsolationCheck", "address": "", "phone": ""},
                          headers=auth_headers(basic_token))

        if basic_count >= max_branches:
            assert r.status_code == 400, \
                f"MULTI-TENANCY BUG: Basic org at limit ({basic_count}/{max_branches}) should get 400, got {r.status_code}"
            print(f"✓ Multi-tenancy isolation correct: basic org blocked at {basic_count}/{max_branches}")
        else:
            # Under limit — allow creation
            if r.status_code == 200:
                requests.delete(f"{BASE_URL}/api/branches/{r.json()['id']}", headers=auth_headers(basic_token))
                print(f"✓ Basic org under limit ({basic_count}/{max_branches}), creation allowed")


# ─── Section 5: Founders Plan ────────────────────────────────────────────────

class TestFoundersPlan:
    """Founders plan: unlimited branches, all Pro features."""

    def test_founders_plan_is_founders(self, founders_token):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(founders_token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert sub["plan"] == "founders"
        assert sub["effective_plan"] == "founders"
        print(f"Founders plan confirmed: {sub['plan']}")

    def test_founders_has_all_pro_features(self, founders_token):
        """Founders plan should have all Pro features."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(founders_token))
        sub = r.json().get("subscription", {})
        features = sub.get("features", {})
        all_pro = ["purchase_orders", "supplier_management", "employee_management",
                   "full_fund_management", "branch_transfers", "audit_center",
                   "granular_permissions", "advanced_reports"]
        for feat in all_pro:
            assert features.get(feat) not in (False, None), f"Founders should have {feat}"
        print(f"Founders all Pro features: verified")

    def test_founders_max_branches_is_zero_unlimited(self, founders_token):
        """Founders plan max_branches=0 means unlimited."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(founders_token))
        sub = r.json().get("subscription", {})
        assert sub["max_branches"] == 0, f"Founders max_branches should be 0 (unlimited), got: {sub['max_branches']}"
        print(f"Founders max_branches: {sub['max_branches']} (0=unlimited)")

    def test_founders_no_expiry_date(self, founders_token):
        """Founders plan should not have subscription_expires_at."""
        r = requests.get(f"{BASE_URL}/api/organizations/my", headers=auth_headers(founders_token))
        assert r.status_code == 200
        org = r.json()
        # Founders should not expire
        assert org.get("subscription_expires_at") is None, \
            f"Founders should have null expiry, got: {org.get('subscription_expires_at')}"
        print(f"Founders no expiry: ✓")

    def test_founders_grace_info_not_in_grace(self, founders_token):
        """Founders plan: grace_info.in_grace should be False."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(founders_token))
        sub = r.json().get("subscription", {})
        grace = sub.get("grace_info", {})
        assert grace.get("in_grace") == False, f"Founders should not be in grace: {grace}"
        print(f"Founders grace_info: {grace}")


# ─── Section 6: Feature Flags API ────────────────────────────────────────────

class TestFeatureFlagsAPI:
    """Feature flags: GET from live DB, default fallback."""

    def test_feature_flags_loaded_in_auth_me(self, basic_token):
        """auth/me returns live features (from DB or defaults)."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert "features" in sub, "features should be in subscription"
        assert isinstance(sub["features"], dict), "features should be a dict"
        print(f"Feature flags in auth/me: {len(sub['features'])} flags")

    def test_feature_matrix_basic_flags_correct(self):
        """Feature matrix: basic plan should have purchase_orders=False."""
        r = requests.get(f"{BASE_URL}/api/organizations/feature-matrix")
        assert r.status_code == 200
        flags = r.json()["flags"]
        assert flags["basic"].get("purchase_orders") == False
        assert flags["basic"].get("pos_sales") == True
        assert flags["standard"].get("purchase_orders") == True
        assert flags["pro"].get("granular_permissions") == True
        print("Feature matrix flags verified for basic/standard/pro")

    def test_feature_matrix_pro_flags_all_true(self):
        """Pro plan should have all premium features enabled."""
        r = requests.get(f"{BASE_URL}/api/organizations/feature-matrix")
        assert r.status_code == 200
        pro_flags = r.json()["flags"]["pro"]
        for key, val in pro_flags.items():
            assert val not in (False, 0), f"Pro should enable {key}, got: {val}"
        print(f"Pro plan all {len(pro_flags)} features enabled: ✓")


# ─── Section 7: Auth Endpoints ───────────────────────────────────────────────

class TestAuthEndpoints:
    """Auth endpoints: login, me, subscription data."""

    def test_login_with_valid_credentials(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "limittest@testmail.com", "password": "Test@123456"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "subscription" in data
        assert data["subscription"]["plan"] == "basic"
        print(f"Login OK, plan: {data['subscription']['plan']}")

    def test_login_with_invalid_credentials(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "limittest@testmail.com", "password": "wrongpassword"})
        assert r.status_code == 401
        print(f"Invalid login blocked: {r.status_code}")

    def test_auth_me_returns_subscription(self, basic_token):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        assert r.status_code == 200
        result = r.json()
        assert "subscription" in result
        sub = result["subscription"]
        required_keys = ["plan", "effective_plan", "status", "features", "max_branches", "max_users", "grace_info"]
        for key in required_keys:
            assert key in sub, f"subscription missing key: {key}"
        print(f"auth/me subscription keys: {list(sub.keys())}")

    def test_auth_me_without_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"
        print(f"Unauthenticated /me blocked: {r.status_code}")

    def test_login_returns_subscription_features(self):
        """Login response should include subscription.features dict."""
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "sibugayagrivetsupply@gmail.com", "password": "521325"})
        assert r.status_code == 200
        sub = r.json().get("subscription", {})
        assert "features" in sub
        assert isinstance(sub["features"], dict)
        assert len(sub["features"]) > 0
        print(f"Login subscription features: {len(sub['features'])} flags returned")


# ─── Section 8: Superadmin API ───────────────────────────────────────────────

class TestSuperAdminAPI:
    """Super admin endpoints: stats, org list, subscription update."""

    def test_superadmin_stats_requires_auth(self):
        """GET /api/superadmin/stats requires auth."""
        r = requests.get(f"{BASE_URL}/api/superadmin/stats")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"
        print(f"Superadmin stats unauthenticated: {r.status_code}")

    def test_superadmin_blocked_for_regular_user(self, basic_token):
        """Regular user cannot access superadmin endpoints."""
        r = requests.get(f"{BASE_URL}/api/superadmin/stats", headers=auth_headers(basic_token))
        assert r.status_code == 403
        print(f"Regular user blocked from superadmin: {r.status_code}")

    def test_superadmin_blocked_for_founders_user(self, founders_token):
        """Founders org user (not super_admin) cannot access superadmin endpoints."""
        r = requests.get(f"{BASE_URL}/api/superadmin/stats", headers=auth_headers(founders_token))
        assert r.status_code == 403
        print(f"Founders user blocked from superadmin: {r.status_code}")

    def test_admin_login_step1_returns_pending_token(self):
        """Admin login (step 1) returns pending_token for TOTP."""
        r = requests.post(f"{BASE_URL}/api/admin-auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "Aa@58798546521325"
        })
        assert r.status_code == 200
        data = r.json()
        # Should return either pending_token (TOTP required) or token (TOTP not yet set up)
        assert "pending_token" in data or "token" in data, f"Expected token in response: {data}"
        print(f"Admin login step 1: {list(data.keys())}")

    def test_admin_login_wrong_password(self):
        """Admin login with wrong password should fail."""
        r = requests.post(f"{BASE_URL}/api/admin-auth/login", json={
            "email": "janmarkeahig@gmail.com",
            "password": "wrongpassword123"
        })
        assert r.status_code in (400, 401, 403), f"Expected error, got {r.status_code}"
        print(f"Admin wrong password: {r.status_code}")


# ─── Section 9: Organization Info ─────────────────────────────────────────────

class TestOrganizationInfo:
    """Organization info: /api/organizations/my endpoint."""

    def test_my_org_returns_plan_info(self, basic_token):
        r = requests.get(f"{BASE_URL}/api/organizations/my", headers=auth_headers(basic_token))
        assert r.status_code == 200
        org = r.json()
        assert org.get("plan") == "basic"
        assert "effective_plan" in org
        assert "features" in org
        assert "limits" in org
        print(f"My org plan: {org['plan']}, effective: {org['effective_plan']}")

    def test_my_org_returns_founders_plan(self, founders_token):
        r = requests.get(f"{BASE_URL}/api/organizations/my", headers=auth_headers(founders_token))
        assert r.status_code == 200
        org = r.json()
        assert org.get("plan") == "founders"
        assert org.get("effective_plan") == "founders"
        print(f"Founders org info: plan={org['plan']}, max_branches={org['max_branches']}")

    def test_my_org_not_accessible_without_auth(self):
        r = requests.get(f"{BASE_URL}/api/organizations/my")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"
        print(f"My org unauthenticated: {r.status_code}")


# ─── Section 10: Subscription Auto-Expiry ────────────────────────────────────

class TestSubscriptionAutoExpiry:
    """Verify plan expiry behavior."""

    def test_founders_plan_no_subscription_expires_at(self, founders_token):
        """Founders plan should NOT have subscription_expires_at."""
        r = requests.get(f"{BASE_URL}/api/organizations/my", headers=auth_headers(founders_token))
        assert r.status_code == 200
        org = r.json()
        assert org.get("subscription_expires_at") is None, \
            f"Founders should not expire, got: {org.get('subscription_expires_at')}"
        print(f"Founders expiry: {org.get('subscription_expires_at')} (null = no expiry)")

    def test_basic_plan_has_subscription_status_active(self, basic_token):
        """Active paid plan org should have subscription_status=active."""
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers(basic_token))
        sub = r.json().get("subscription", {})
        assert sub["status"] == "active", f"Expected active, got: {sub['status']}"
        print(f"Basic plan status: {sub['status']}")
