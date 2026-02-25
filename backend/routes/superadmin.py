"""
Super Admin routes: platform-level management across all organizations.
Access: janmarkeahig@gmail.com only (is_super_admin=True).
"""
from fastapi import APIRouter, Depends, HTTPException
from config import _raw_db
from utils import now_iso, new_id
from utils.auth import get_current_user
from routes.organizations import PLAN_LIMITS, PLAN_PRICING, get_effective_plan
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/superadmin", tags=["Super Admin"])


def require_super_admin(user=Depends(get_current_user)):
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# ---------------------------------------------------------------------------
# Platform Stats
# ---------------------------------------------------------------------------
@router.get("/stats")
async def platform_stats(user=Depends(require_super_admin)):
    now = datetime.now(timezone.utc)
    total_orgs = await _raw_db.organizations.count_documents({})
    trial_orgs = await _raw_db.organizations.count_documents({"plan": "trial"})
    active_orgs = await _raw_db.organizations.count_documents({"subscription_status": "active"})
    founders_orgs = await _raw_db.organizations.count_documents({"plan": "founders"})
    suspended_orgs = await _raw_db.organizations.count_documents({"plan": "suspended"})
    total_users = await _raw_db.users.count_documents({"active": True, "is_super_admin": {"$ne": True}})

    # Expiring trials in next 7 days
    week_out = (now + timedelta(days=7)).isoformat()
    expiring_soon = await _raw_db.organizations.count_documents({
        "plan": "trial",
        "trial_ends_at": {"$lt": week_out, "$gt": now.isoformat()}
    })

    plan_counts = {}
    for plan in ["basic", "standard", "pro", "founders"]:
        plan_counts[plan] = await _raw_db.organizations.count_documents({"plan": plan})

    return {
        "total_organizations": total_orgs,
        "trial": trial_orgs,
        "active": active_orgs,
        "founders": founders_orgs,
        "suspended": suspended_orgs,
        "total_users": total_users,
        "expiring_soon": expiring_soon,
        "by_plan": plan_counts,
    }


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
@router.get("/organizations")
async def list_organizations(user=Depends(require_super_admin)):
    orgs = await _raw_db.organizations.find({}, {"_id": 0}).to_list(500)
    result = []
    for org in orgs:
        branch_count = await _raw_db.branches.count_documents({"organization_id": org["id"], "active": True})
        user_count = await _raw_db.users.count_documents({"organization_id": org["id"], "active": True})
        org["branch_count"] = branch_count
        org["user_count"] = user_count
        org["effective_plan"] = get_effective_plan(org)
        result.append(org)
    return result


@router.get("/organizations/{org_id}")
async def get_organization(org_id: str, user=Depends(require_super_admin)):
    org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    branch_count = await _raw_db.branches.count_documents({"organization_id": org_id, "active": True})
    user_count = await _raw_db.users.count_documents({"organization_id": org_id, "active": True})
    org["branch_count"] = branch_count
    org["user_count"] = user_count
    org["effective_plan"] = get_effective_plan(org)
    return org


@router.get("/organizations/{org_id}/branches")
async def get_org_branches(org_id: str, user=Depends(require_super_admin)):
    """List all branches for an organization."""
    branches = await _raw_db.branches.find(
        {"organization_id": org_id},
        {"_id": 0, "id": 1, "name": 1, "address": 1, "active": 1, "is_main": 1, "created_at": 1}
    ).to_list(100)
    return branches


@router.get("/organizations/{org_id}/users")
async def get_org_users(org_id: str, user=Depends(require_super_admin)):
    """List all users for an organization."""
    users = await _raw_db.users.find(
        {"organization_id": org_id},
        {"_id": 0, "id": 1, "username": 1, "full_name": 1, "email": 1, "role": 1, "active": 1, "created_at": 1}
    ).to_list(100)
    return users


@router.put("/organizations/{org_id}/subscription")
async def update_subscription(org_id: str, data: dict, user=Depends(require_super_admin)):
    """Update an organization's plan/subscription."""
    plan = data.get("plan")
    valid_plans = ["trial", "basic", "standard", "pro", "founders", "suspended"]
    if plan and plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose: {valid_plans}")

    existing = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Organization not found")

    update = {"updated_at": now_iso()}

    effective_plan = plan or existing.get("plan", "basic")
    if plan:
        update["plan"] = plan
        if plan == "founders":
            update["subscription_status"] = "active"
            update["subscription_expires_at"] = None   # Founders never expires
            update["max_branches"] = 0                 # Unlimited
            update["max_users"] = 0
            update["extra_branches"] = 0
        elif plan == "suspended":
            update["subscription_status"] = "suspended"
        elif plan == "trial":
            update["subscription_status"] = "trial"
        else:
            update["subscription_status"] = "active"

    # Extra branches (skip for founders — unlimited)
    if effective_plan != "founders":
        extra = int(data.get("extra_branches", existing.get("extra_branches", 0)))
        base_limit = PLAN_LIMITS.get(effective_plan, PLAN_LIMITS["basic"])["max_branches"]
        update["max_branches"] = base_limit + extra
        update["extra_branches"] = extra
        update["max_users"] = PLAN_LIMITS.get(effective_plan, PLAN_LIMITS["basic"])["max_users"]

    # Trial extension
    if "trial_days" in data and int(data.get("trial_days", 0)) > 0:
        trial_end = (datetime.now(timezone.utc) + timedelta(days=int(data["trial_days"]))).isoformat()
        update["trial_ends_at"] = trial_end
        update["plan"] = "trial"
        update["subscription_status"] = "trial"

    # Subscription expiry for paid plans
    # If admin provides a date, use it. Otherwise auto-set 30 days when activating a paid plan.
    if "subscription_expires_at" in data:
        update["subscription_expires_at"] = data["subscription_expires_at"] or None
    elif plan in ("basic", "standard", "pro") and not existing.get("subscription_expires_at"):
        # Auto-set 30 days from today as default when first activating a paid plan
        auto_expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        update["subscription_expires_at"] = auto_expiry

    if "notes" in data:
        update["admin_notes"] = data["notes"]

    await _raw_db.organizations.update_one({"id": org_id}, {"$set": update})
    updated = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})

    # Email notification
    if updated and updated.get("owner_email"):
        import asyncio
        from services.email_service import send_subscription_activated
        new_plan = update.get("plan", updated.get("plan", "basic"))
        if new_plan not in ("suspended", "trial"):
            asyncio.create_task(send_subscription_activated(
                updated["owner_email"], updated["name"], new_plan,
                data.get("expires_display", "")
            ))

    updated["branch_count"] = await _raw_db.branches.count_documents({"organization_id": org_id, "active": True})
    updated["user_count"] = await _raw_db.users.count_documents({"organization_id": org_id, "active": True})
    updated["effective_plan"] = get_effective_plan(updated)
    return updated


@router.put("/organizations/{org_id}/info")
async def update_org_info(org_id: str, data: dict, user=Depends(require_super_admin)):
    """Update organization name/contact info."""
    allowed = ["name", "owner_email", "phone", "address", "admin_notes"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    await _raw_db.organizations.update_one({"id": org_id}, {"$set": update})
    return await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})


# ---------------------------------------------------------------------------
# Feature Flags Management
# ---------------------------------------------------------------------------
@router.get("/settings/features")
async def get_feature_flags(user=Depends(require_super_admin)):
    """Get current feature flags for all plans."""
    from routes.organizations import FEATURE_DEFINITIONS, DEFAULT_FEATURE_FLAGS, get_live_feature_flags
    flags = await get_live_feature_flags()
    return {
        "feature_definitions": FEATURE_DEFINITIONS,
        "flags": {
            "basic": flags.get("basic", DEFAULT_FEATURE_FLAGS["basic"]),
            "standard": flags.get("standard", DEFAULT_FEATURE_FLAGS["standard"]),
            "pro": flags.get("pro", DEFAULT_FEATURE_FLAGS["pro"]),
        },
        "last_updated": (await _raw_db.platform_settings.find_one(
            {"key": "feature_flags"}, {"_id": 0, "updated_at": 1}
        ) or {}).get("updated_at"),
    }


@router.put("/settings/features")
async def update_feature_flags(data: dict, user=Depends(require_super_admin)):
    """Save updated feature flags. Trial always mirrors Pro automatically."""
    from routes.organizations import DEFAULT_FEATURE_FLAGS
    flags = data.get("flags", {})
    # Trial always = Pro
    flags["trial"] = flags.get("pro", DEFAULT_FEATURE_FLAGS["pro"])
    # Grace period = Pro (full access during grace)
    flags["grace_period"] = flags.get("pro", DEFAULT_FEATURE_FLAGS["pro"])
    flags["expired"] = flags.get("basic", DEFAULT_FEATURE_FLAGS["basic"])

    await _raw_db.platform_settings.update_one(
        {"key": "feature_flags"},
        {"$set": {
            "key": "feature_flags",
            "value": flags,
            "updated_at": now_iso(),
            "updated_by": user.get("email"),
        }},
        upsert=True
    )
    return {"success": True, "flags": flags, "message": "Feature flags updated and live immediately."}
@router.get("/settings/payment")
async def get_payment_settings(user=Depends(require_super_admin)):
    """Get platform payment configuration."""
    setting = await _raw_db.platform_settings.find_one({"key": "payment_methods"}, {"_id": 0})
    if not setting:
        return {"key": "payment_methods", "value": {}}
    # Strip QR base64 preview from response for speed — frontend requests full when needed
    return setting


@router.put("/settings/payment")
async def update_payment_settings(data: dict, user=Depends(require_super_admin)):
    """Update platform payment configuration (QR codes, account numbers)."""
    now = now_iso()
    await _raw_db.platform_settings.update_one(
        {"key": "payment_methods"},
        {"$set": {
            "key": "payment_methods",
            "value": data.get("value", {}),
            "updated_at": now,
            "updated_by": user.get("email"),
        }},
        upsert=True
    )
    result = await _raw_db.platform_settings.find_one({"key": "payment_methods"}, {"_id": 0})
    return result


# ---------------------------------------------------------------------------
# Public: Payment info for Upgrade page
# ---------------------------------------------------------------------------
@router.get("/public/payment-info")
async def get_public_payment_info():
    """Public endpoint: returns payment methods for the upgrade page."""
    setting = await _raw_db.platform_settings.find_one({"key": "payment_methods"}, {"_id": 0})
    if not setting:
        return {"configured": False, "methods": {}}
    return {"configured": True, "methods": setting.get("value", {})}
