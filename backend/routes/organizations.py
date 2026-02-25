"""
Organization management: registration, subscription, tenant info.
"""
from fastapi import APIRouter, HTTPException, Depends
from config import db, _raw_db, set_org_context
from utils import hash_password, now_iso, new_id
from utils.auth import get_current_user
from models import DEFAULT_PERMISSIONS
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/organizations", tags=["Organizations"])

# ---------------------------------------------------------------------------
# Plan definitions
# ---------------------------------------------------------------------------
PLAN_LIMITS = {
    "trial":    {"max_branches": 5,  "max_users": 0},   # 0 = unlimited
    "basic":    {"max_branches": 1,  "max_users": 5},
    "standard": {"max_branches": 2,  "max_users": 15},
    "pro":      {"max_branches": 5,  "max_users": 0},
    "founders": {"max_branches": 0,  "max_users": 0},   # Unlimited everything, never expires
    "suspended":{"max_branches": 0,  "max_users": 0},
}

PLAN_PRICING = {
    "basic":        {"php": 1500,  "usd": 30},
    "standard":     {"php": 4000,  "usd": 80},
    "pro":          {"php": 7500,  "usd": 150},
    "founders":     {"php": 0,     "usd": 0},     # Special — granted by admin
    "extra_branch": {"php": 1500,  "usd": 30},
}

PLAN_FEATURES = {
    "basic": {
        "purchase_orders": False,
        "supplier_management": False,
        "employee_management": False,
        "full_fund_management": False,
        "branch_transfers": False,
        "audit_center": False,
        "transaction_verification": False,
        "granular_permissions": False,
        "two_fa": False,
        "advanced_reports": False,
        "multi_branch": False,
    },
    "standard": {
        "purchase_orders": True,
        "supplier_management": True,
        "employee_management": True,
        "full_fund_management": True,
        "branch_transfers": True,
        "audit_center": "basic",
        "transaction_verification": False,
        "granular_permissions": False,
        "two_fa": False,
        "advanced_reports": True,
        "multi_branch": True,
    },
    "pro": {
        "purchase_orders": True,
        "supplier_management": True,
        "employee_management": True,
        "full_fund_management": True,
        "branch_transfers": True,
        "audit_center": "full",
        "transaction_verification": True,
        "granular_permissions": True,
        "two_fa": True,
        "advanced_reports": True,
        "multi_branch": True,
    },
}
# Trial gets all Pro features
PLAN_FEATURES["trial"] = PLAN_FEATURES["pro"]
PLAN_FEATURES["founders"] = {**PLAN_FEATURES["pro"]}  # All Pro features, never expires
PLAN_FEATURES["suspended"] = PLAN_FEATURES["basic"]
PLAN_FEATURES["grace_period"] = PLAN_FEATURES["pro"]
PLAN_FEATURES["expired"] = PLAN_FEATURES["basic"]

GRACE_PERIOD_DAYS = 3


def get_effective_plan(org: dict) -> str:
    """Return the plan to enforce (handles trial expiry + grace period)."""
    plan = org.get("plan", "basic")
    now = datetime.now(timezone.utc)

    # Founders = permanent, never expires
    if plan == "founders":
        return "founders"

    # Suspended = locked
    if plan == "suspended":
        return "suspended"

    # Trial expiry check
    if plan == "trial":
        trial_ends = org.get("trial_ends_at")
        if trial_ends:
            try:
                end_dt = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
                if now > end_dt:
                    grace_ends = end_dt + timedelta(days=GRACE_PERIOD_DAYS)
                    if now > grace_ends:
                        return "expired"
                    return "grace_period"
            except Exception:
                pass
        return "pro"  # Trial still active → all pro features

    # Paid plan expiry check (basic / standard / pro)
    # If subscription_expires_at is not set, the plan doesn't expire yet.
    # Admin must set it when activating a paid subscription.
    sub_expires = org.get("subscription_expires_at")
    if sub_expires and plan in ("basic", "standard", "pro"):
        try:
            exp_dt = datetime.fromisoformat(sub_expires.replace("Z", "+00:00"))
            if now > exp_dt:
                grace_ends = exp_dt + timedelta(days=GRACE_PERIOD_DAYS)
                if now > grace_ends:
                    return "expired"
                return "grace_period"
        except Exception:
            pass

    return plan


def get_grace_info(org: dict) -> dict:
    """Returns grace period details for frontend banners."""
    plan = org.get("plan", "basic")
    now = datetime.now(timezone.utc)
    effective = get_effective_plan(org)

    if effective == "grace_period":
        # Find when grace ends
        ref_date = None
        if plan == "trial":
            ref = org.get("trial_ends_at")
        else:
            ref = org.get("subscription_expires_at")
        if ref:
            try:
                end_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
                grace_ends = end_dt + timedelta(days=GRACE_PERIOD_DAYS)
                days_left = max(0, (grace_ends - now).days)
                return {
                    "in_grace": True,
                    "days_left": days_left,
                    "locked_at": grace_ends.strftime("%B %d, %Y"),
                }
            except Exception:
                pass
    return {"in_grace": False, "days_left": None, "locked_at": None}


# ---------------------------------------------------------------------------
# Public: self-registration
# ---------------------------------------------------------------------------
@router.post("/register")
async def register_organization(data: dict):
    """Create a new organization + admin user. No auth required."""
    required = ["company_name", "admin_email", "admin_password", "admin_name"]
    for f in required:
        if not data.get(f):
            raise HTTPException(status_code=400, detail=f"Missing: {f}")

    email = data["admin_email"].lower().strip()

    # Check email not already used
    existing = await _raw_db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = now_iso()
    org_id = new_id()
    admin_id = new_id()
    trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    # Create organization
    org = {
        "id": org_id,
        "name": data["company_name"],
        "owner_email": email,
        "phone": data.get("phone", ""),
        "address": data.get("address", ""),
        "plan": "trial",
        "subscription_status": "trial",
        "trial_ends_at": trial_end,
        "max_branches": PLAN_LIMITS["trial"]["max_branches"],
        "max_users": PLAN_LIMITS["trial"]["max_users"],
        "extra_branches": 0,
        "annual_billing": False,
        "is_demo": False,
        "created_at": now,
    }
    await _raw_db.organizations.insert_one(org)

    # Set org context so inserts get organization_id automatically
    set_org_context(org_id)

    # Create admin user
    admin_user = {
        "id": admin_id,
        "username": email.split("@")[0],
        "full_name": data["admin_name"],
        "email": email,
        "password_hash": hash_password(data["admin_password"]),
        "role": "admin",
        "organization_id": org_id,
        "branch_id": None,
        "manager_pin": data.get("manager_pin", "1234"),
        "permissions": DEFAULT_PERMISSIONS.get("admin", {}),
        "active": True,
        "created_at": now,
    }
    await _raw_db.users.insert_one(admin_user)

    # Create default price schemes
    default_schemes = [
        {"id": new_id(), "name": "Retail", "key": "retail", "description": "Standard retail price",
         "calculation_method": "percent_plus_capital", "calculation_value": 30,
         "base_scheme": "cost_price", "active": True, "created_at": now, "organization_id": org_id},
        {"id": new_id(), "name": "Wholesale", "key": "wholesale", "description": "Wholesale price",
         "calculation_method": "percent_plus_capital", "calculation_value": 15,
         "base_scheme": "cost_price", "active": True, "created_at": now, "organization_id": org_id},
        {"id": new_id(), "name": "Special", "key": "special", "description": "Special customer price",
         "calculation_method": "percent_minus_retail", "calculation_value": 10,
         "base_scheme": "retail", "active": True, "created_at": now, "organization_id": org_id},
    ]
    await _raw_db.price_schemes.insert_many(default_schemes)

    # Create company settings
    await _raw_db.settings.update_one(
        {"key": "company_info", "organization_id": org_id},
        {"$set": {
            "key": "company_info",
            "organization_id": org_id,
            "value": {
                "name": data["company_name"],
                "email": email,
                "phone": data.get("phone", ""),
                "currency": "PHP",
                "date_format": "MM/DD/YYYY",
            },
            "updated_at": now,
        }},
        upsert=True
    )

    set_org_context(None)

    # Send welcome email (async, non-blocking)
    import asyncio
    from services.email_service import send_welcome
    asyncio.create_task(send_welcome(
        email,
        data["company_name"],
        trial_end[:10]
    ))

    return {
        "success": True,
        "message": "Organization created! You have a 14-day free trial with all Pro features.",
        "organization_id": org_id,
        "trial_ends_at": trial_end,
        "next_step": "Complete setup by creating your first branch via /api/setup/initialize-org",
    }


# ---------------------------------------------------------------------------
# Authenticated: get own org info
# ---------------------------------------------------------------------------
@router.get("/my")
async def get_my_organization(user=Depends(get_current_user)):
    """Get the current user's organization info."""
    if user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admins don't belong to an organization")
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=404, detail="No organization found")
    org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    effective_plan = get_effective_plan(org)
    grace_info = get_grace_info(org)
    from routes.organizations import get_live_feature_flags
    flags = await get_live_feature_flags()
    return {
        **{k: v for k, v in org.items()},
        "effective_plan": effective_plan,
        "grace_info": grace_info,
        "features": flags.get(effective_plan, PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["basic"])),
        "limits": PLAN_LIMITS.get(effective_plan, PLAN_LIMITS["basic"]),
        "pricing": PLAN_PRICING,
    }


@router.get("/payment-info")
async def get_payment_info():
    """Public: payment method details for the upgrade page."""
    setting = await _raw_db.platform_settings.find_one({"key": "payment_methods"}, {"_id": 0})
    if not setting:
        return {"configured": False, "methods": {}}
    return {"configured": True, "methods": setting.get("value", {})}


# ---------------------------------------------------------------------------
# Feature Definitions (source of truth for all feature metadata)
# ---------------------------------------------------------------------------
FEATURE_DEFINITIONS = [
    # Core — always included in every plan
    {"key": "pos_sales",           "name": "POS & Sales",                  "description": "Point of sale, split payments (Cash/Digital/Credit), void & reopen",        "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    {"key": "inventory",           "name": "Inventory Management",          "description": "Products, repacks, stock tracking, adjustments",                             "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    {"key": "customer_management", "name": "Customer Management",           "description": "Customer profiles, purchase history, AR balance tracking",                   "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    {"key": "expense_tracking",    "name": "Expense Tracking",              "description": "Record, categorize and manage business expenses",                            "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    {"key": "basic_reports",       "name": "Basic Reports",                 "description": "Daily sales summary, inventory level reports",                               "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    {"key": "daily_close_wizard",  "name": "Daily Close Wizard",            "description": "Guided end-of-day closing, Z-Report, cash reconciliation",                  "category": "Core",         "locked_on": ["basic","standard","pro","trial"]},
    # Operations
    {"key": "purchase_orders",     "name": "Purchase Orders",              "description": "Full PO workflow: create, receive, edit, reopen with audit trail",           "category": "Operations",   "locked_on": []},
    {"key": "supplier_management", "name": "Supplier Management",          "description": "Supplier profiles, purchase history, accounts payable",                      "category": "Operations",   "locked_on": []},
    {"key": "employee_management", "name": "Employee & Cash Advances",     "description": "Employee profiles, cash advance requests and tracking",                      "category": "Operations",   "locked_on": []},
    # Finance
    {"key": "full_fund_management","name": "4-Wallet Fund Management",     "description": "Cashier, Safe, Digital (GCash/Maya), Bank — all tracked separately",        "category": "Finance",      "locked_on": []},
    {"key": "advanced_reports",    "name": "Advanced Financial Reports",   "description": "AR aging, inventory movement, income statements",                            "category": "Finance",      "locked_on": []},
    # Multi-Branch
    {"key": "multi_branch",        "name": "Multi-Branch Support",         "description": "Multiple branch management with consolidated owner view",                    "category": "Multi-Branch", "locked_on": []},
    {"key": "branch_transfers",    "name": "Branch Transfers",             "description": "Transfer stock between branches with cost tracking",                         "category": "Multi-Branch", "locked_on": []},
    {"key": "repack_pricing",      "name": "Transfer Repack Pricing",      "description": "Set destination sell prices when transferring repacked products",             "category": "Multi-Branch", "locked_on": []},
    # Audit
    {"key": "audit_center",        "name": "Standard Audit Trail",         "description": "Transaction history, basic audit logs, timeline view",                       "category": "Audit",        "locked_on": []},
    {"key": "full_audit_center",   "name": "Full Audit Center",            "description": "Audit scoring, rule-based insights, discrepancy detection",                  "category": "Audit",        "locked_on": []},
    {"key": "transaction_verify",  "name": "Transaction Verification",     "description": "Manager PIN verification, discrepancy flagging and resolution workflow",     "category": "Audit",        "locked_on": []},
    # Security
    {"key": "granular_permissions","name": "Granular Role Permissions",    "description": "Custom per-user access control for every module and action",                 "category": "Security",     "locked_on": []},
    {"key": "two_fa",              "name": "2FA Security (TOTP)",          "description": "Google Authenticator two-factor authentication for admin accounts",           "category": "Security",     "locked_on": []},
]

DEFAULT_FEATURE_FLAGS = {
    "basic": {
        "pos_sales": True, "inventory": True, "customer_management": True,
        "expense_tracking": True, "basic_reports": True, "daily_close_wizard": True,
        "purchase_orders": False, "supplier_management": False, "employee_management": False,
        "full_fund_management": False, "advanced_reports": False,
        "multi_branch": False, "branch_transfers": False, "repack_pricing": False,
        "audit_center": False, "full_audit_center": False, "transaction_verify": False,
        "granular_permissions": False, "two_fa": False,
    },
    "standard": {
        "pos_sales": True, "inventory": True, "customer_management": True,
        "expense_tracking": True, "basic_reports": True, "daily_close_wizard": True,
        "purchase_orders": True, "supplier_management": True, "employee_management": True,
        "full_fund_management": True, "advanced_reports": True,
        "multi_branch": True, "branch_transfers": True, "repack_pricing": False,
        "audit_center": True, "full_audit_center": False, "transaction_verify": False,
        "granular_permissions": False, "two_fa": False,
    },
    "pro": {
        "pos_sales": True, "inventory": True, "customer_management": True,
        "expense_tracking": True, "basic_reports": True, "daily_close_wizard": True,
        "purchase_orders": True, "supplier_management": True, "employee_management": True,
        "full_fund_management": True, "advanced_reports": True,
        "multi_branch": True, "branch_transfers": True, "repack_pricing": True,
        "audit_center": True, "full_audit_center": True, "transaction_verify": True,
        "granular_permissions": True, "two_fa": True,
    },
}
DEFAULT_FEATURE_FLAGS["trial"] = DEFAULT_FEATURE_FLAGS["pro"]


async def get_live_feature_flags() -> dict:
    """Fetch feature flags from DB, fall back to defaults."""
    setting = await _raw_db.platform_settings.find_one({"key": "feature_flags"}, {"_id": 0})
    if setting and setting.get("value"):
        flags = setting["value"]
        # Ensure trial always mirrors pro
        flags["trial"] = flags.get("pro", DEFAULT_FEATURE_FLAGS["pro"])
        return flags
    return DEFAULT_FEATURE_FLAGS


@router.get("/feature-matrix")
async def get_feature_matrix():
    """Public: full feature matrix for landing page pricing table."""
    flags = await get_live_feature_flags()
    return {
        "feature_definitions": FEATURE_DEFINITIONS,
        "flags": {
            "basic":    flags.get("basic",    DEFAULT_FEATURE_FLAGS["basic"]),
            "standard": flags.get("standard", DEFAULT_FEATURE_FLAGS["standard"]),
            "pro":      flags.get("pro",      DEFAULT_FEATURE_FLAGS["pro"]),
        },
        "plan_pricing": PLAN_PRICING,
        "plan_limits": {
            "basic": PLAN_LIMITS["basic"],
            "standard": PLAN_LIMITS["standard"],
            "pro": PLAN_LIMITS["pro"],
        },
    }


@router.get("/plans")
async def get_plans():
    """Public: get plan definitions with live feature flags."""
    flags = await get_live_feature_flags()
    return {
        "plans": [
            {
                "key": "basic",
                "name": "Basic",
                "tagline": "Get your first branch running clean",
                "pricing": PLAN_PRICING["basic"],
                "limits": PLAN_LIMITS["basic"],
                "features": flags.get("basic", DEFAULT_FEATURE_FLAGS["basic"]),
            },
            {
                "key": "standard",
                "name": "Standard",
                "tagline": "Run a real multi-branch operation",
                "pricing": PLAN_PRICING["standard"],
                "limits": PLAN_LIMITS["standard"],
                "features": flags.get("standard", DEFAULT_FEATURE_FLAGS["standard"]),
                "popular": True,
            },
            {
                "key": "pro",
                "name": "Pro",
                "tagline": "Audit-grade control for serious businesses",
                "pricing": PLAN_PRICING["pro"],
                "limits": PLAN_LIMITS["pro"],
                "features": flags.get("pro", DEFAULT_FEATURE_FLAGS["pro"]),
            },
        ],
        "extra_branch": PLAN_PRICING["extra_branch"],
        "trial_days": 14,
        "annual_discount_months": 2,
    }
