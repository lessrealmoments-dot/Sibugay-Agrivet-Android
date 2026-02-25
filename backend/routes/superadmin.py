"""
Super Admin routes: platform-level management across all organizations.
Access: janmarkeahig@gmail.com only (is_super_admin=True).
"""
from fastapi import APIRouter, Depends, HTTPException
from config import _raw_db
from utils import hash_password, now_iso, new_id
from utils.auth import get_current_user
from routes.organizations import PLAN_LIMITS, PLAN_PRICING, get_effective_plan
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/superadmin", tags=["Super Admin"])


def require_super_admin(user=Depends(get_current_user)):
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
@router.get("/organizations")
async def list_organizations(user=Depends(require_super_admin)):
    orgs = await _raw_db.organizations.find({}, {"_id": 0}).to_list(500)
    result = []
    for org in orgs:
        # Count branches and users for each org
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
    return org


@router.put("/organizations/{org_id}/subscription")
async def update_subscription(org_id: str, data: dict, user=Depends(require_super_admin)):
    """Update an organization's plan/subscription status."""
    plan = data.get("plan")
    valid_plans = ["trial", "basic", "standard", "pro", "suspended"]
    if plan and plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose: {valid_plans}")

    update = {"updated_at": now_iso()}
    if plan:
        update["plan"] = plan
        update["subscription_status"] = "trial" if plan == "trial" else ("suspended" if plan == "suspended" else "active")
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["basic"])
        update["max_branches"] = limits["max_branches"] + data.get("extra_branches", 0)
        update["max_users"] = limits["max_users"]

    if "extra_branches" in data:
        update["extra_branches"] = int(data["extra_branches"])
        existing = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
        if existing:
            base_plan = plan or existing.get("plan", "basic")
            base_limit = PLAN_LIMITS.get(base_plan, PLAN_LIMITS["basic"])["max_branches"]
            update["max_branches"] = base_limit + int(data["extra_branches"])

    if "trial_days" in data:
        days = int(data["trial_days"])
        trial_end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        update["trial_ends_at"] = trial_end
        update["plan"] = "trial"
        update["subscription_status"] = "trial"

    if "notes" in data:
        update["admin_notes"] = data["notes"]

    await _raw_db.organizations.update_one({"id": org_id}, {"$set": update})
    updated = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})

    # Send email notification to org owner
    if updated and updated.get("owner_email"):
        import asyncio
        from services.email_service import send_subscription_activated
        new_plan = update.get("plan", updated.get("plan", "basic"))
        if new_plan not in ("suspended", "trial"):
            expires_str = data.get("expires_display", "")
            asyncio.create_task(send_subscription_activated(
                updated["owner_email"], updated["name"], new_plan, expires_str
            ))

    return updated


@router.delete("/organizations/{org_id}/suspend")
async def suspend_organization(org_id: str, user=Depends(require_super_admin)):
    await _raw_db.organizations.update_one(
        {"id": org_id},
        {"$set": {"plan": "suspended", "subscription_status": "suspended", "updated_at": now_iso()}}
    )
    return {"message": "Organization suspended"}


# ---------------------------------------------------------------------------
# Stats dashboard
# ---------------------------------------------------------------------------
@router.get("/stats")
async def platform_stats(user=Depends(require_super_admin)):
    total_orgs = await _raw_db.organizations.count_documents({})
    trial_orgs = await _raw_db.organizations.count_documents({"plan": "trial"})
    active_orgs = await _raw_db.organizations.count_documents({"subscription_status": "active"})
    suspended_orgs = await _raw_db.organizations.count_documents({"plan": "suspended"})
    total_users = await _raw_db.users.count_documents({"active": True, "is_super_admin": {"$ne": True}})

    plan_counts = {}
    for plan in ["basic", "standard", "pro"]:
        plan_counts[plan] = await _raw_db.organizations.count_documents({"plan": plan})

    return {
        "total_organizations": total_orgs,
        "trial": trial_orgs,
        "active": active_orgs,
        "suspended": suspended_orgs,
        "total_users": total_users,
        "by_plan": plan_counts,
    }


# ---------------------------------------------------------------------------
# Demo org management
# ---------------------------------------------------------------------------
@router.post("/demo/reset")
async def reset_demo_org(data: dict, user=Depends(require_super_admin)):
    """Reset the demo organization data to its original snapshot."""
    demo_org = await _raw_db.organizations.find_one({"is_demo": True}, {"_id": 0})
    if not demo_org:
        raise HTTPException(status_code=404, detail="No demo organization found")

    demo_org_id = demo_org["id"]

    # Collections to reset (delete all demo org data)
    RESETABLE = [
        'branches', 'products', 'inventory', 'customers', 'invoices', 'sales',
        'purchase_orders', 'suppliers', 'employees', 'movements', 'fund_wallets',
        'wallet_movements', 'fund_transfers', 'expenses', 'branch_prices',
        'branch_transfer_orders', 'count_sheets', 'daily_closings', 'sales_log',
        'returns', 'discrepancy_log', 'safe_lots', 'accounts_payable',
    ]
    for col_name in RESETABLE:
        await _raw_db[col_name].delete_many({"organization_id": demo_org_id})

    return {"message": "Demo org data cleared. Re-seed via /api/superadmin/demo/seed"}
