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
    "suspended":{"max_branches": 0,  "max_users": 0},
}

PLAN_PRICING = {
    "basic":        {"php": 1500,  "usd": 30},
    "standard":     {"php": 4000,  "usd": 80},
    "pro":          {"php": 7500,  "usd": 150},
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
PLAN_FEATURES["suspended"] = PLAN_FEATURES["basic"]


def get_effective_plan(org: dict) -> str:
    """Return the plan to enforce (handles trial expiry)."""
    plan = org.get("plan", "basic")
    if plan == "trial":
        trial_ends = org.get("trial_ends_at")
        if trial_ends:
            try:
                end_dt = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > end_dt:
                    return "basic"  # trial expired → downgrade
            except Exception:
                pass
    return plan


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
    return {
        **{k: v for k, v in org.items()},
        "effective_plan": effective_plan,
        "features": PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["basic"]),
        "limits": PLAN_LIMITS.get(effective_plan, PLAN_LIMITS["basic"]),
        "pricing": PLAN_PRICING,
    }


@router.get("/plans")
async def get_plans():
    """Public: get plan definitions."""
    return {
        "plans": [
            {
                "key": "basic",
                "name": "Basic",
                "tagline": "Get your first branch running clean",
                "pricing": PLAN_PRICING["basic"],
                "limits": PLAN_LIMITS["basic"],
                "features": PLAN_FEATURES["basic"],
            },
            {
                "key": "standard",
                "name": "Standard",
                "tagline": "Run a real multi-branch operation",
                "pricing": PLAN_PRICING["standard"],
                "limits": PLAN_LIMITS["standard"],
                "features": PLAN_FEATURES["standard"],
                "popular": True,
            },
            {
                "key": "pro",
                "name": "Pro",
                "tagline": "Audit-grade control for serious businesses",
                "pricing": PLAN_PRICING["pro"],
                "limits": PLAN_LIMITS["pro"],
                "features": PLAN_FEATURES["pro"],
            },
        ],
        "extra_branch": PLAN_PRICING["extra_branch"],
        "trial_days": 14,
        "annual_discount_months": 2,
    }
