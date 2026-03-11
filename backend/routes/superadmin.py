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


# ---------------------------------------------------------------------------
# Approve / Reject Subscriptions (with email notification)
# ---------------------------------------------------------------------------
@router.post("/organizations/{org_id}/approve-subscription")
async def approve_subscription(org_id: str, data: dict, user=Depends(require_super_admin)):
    """
    Approve a pending subscription: activate the plan, send approval email to customer.
    Body: { plan, extra_branches, subscription_expires_at (optional), note }
    """
    import asyncio
    from services.email_service import send_subscription_activated

    org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    plan = data.get("plan", org.get("plan", "basic"))
    extra = int(data.get("extra_branches", 0))
    base_limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["basic"])["max_branches"]

    auto_expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    expires_at = data.get("subscription_expires_at") or auto_expiry

    update = {
        "plan": plan,
        "subscription_status": "active",
        "subscription_expires_at": expires_at if plan not in ("founders",) else None,
        "max_branches": 0 if plan == "founders" else base_limit + extra,
        "max_users": 0 if plan == "founders" else PLAN_LIMITS.get(plan, PLAN_LIMITS["basic"])["max_users"],
        "extra_branches": extra,
        "admin_notes": data.get("note", ""),
        "approved_at": now_iso(),
        "approved_by": user.get("email", ""),
        "rejection_reason": None,
        "updated_at": now_iso(),
    }
    await _raw_db.organizations.update_one({"id": org_id}, {"$set": update})

    # Mark any pending payment submissions as approved
    await _raw_db.payment_submissions.update_many(
        {"organization_id": org_id, "status": "pending"},
        {"$set": {"status": "approved", "reviewed_at": now_iso(), "reviewed_by": user.get("email", "")}}
    )

    owner_email = org.get("owner_email", "")
    if owner_email:
        expires_display = expires_at[:10] if expires_at else ""
        asyncio.create_task(send_subscription_activated(owner_email, org["name"], plan, expires_display))

    updated = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    return updated


@router.post("/organizations/{org_id}/reject-subscription")
async def reject_subscription(org_id: str, data: dict, user=Depends(require_super_admin)):
    """
    Reject a pending subscription payment. Sends rejection email with reason.
    Body: { reason, plan (the plan they were trying to get) }
    """
    import asyncio
    from services.email_service import send_subscription_rejected

    org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    reason = data.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    plan = data.get("plan", org.get("plan", "trial"))

    await _raw_db.organizations.update_one({"id": org_id}, {"$set": {
        "rejection_reason": reason,
        "rejected_at": now_iso(),
        "rejected_by": user.get("email", ""),
        "updated_at": now_iso(),
    }})

    # Mark pending submissions as rejected
    await _raw_db.payment_submissions.update_many(
        {"organization_id": org_id, "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": now_iso(), "reviewed_by": user.get("email", ""), "rejection_reason": reason}}
    )

    owner_email = org.get("owner_email", "")
    if owner_email:
        asyncio.create_task(send_subscription_rejected(owner_email, org["name"], plan, reason))

    return {"message": f"Subscription rejected. Email sent to {owner_email}."}


# ---------------------------------------------------------------------------
# Payment Proof Submissions
# ---------------------------------------------------------------------------
@router.get("/payment-submissions")
async def list_payment_submissions(
    status: str = "pending",
    user=Depends(require_super_admin)
):
    """List payment proof submissions from customers."""
    query = {}
    if status and status != "all":
        query["status"] = status

    subs = await _raw_db.payment_submissions.find(query, {"_id": 0}).sort("submitted_at", -1).to_list(100)

    # Enrich with org info
    for s in subs:
        org = await _raw_db.organizations.find_one({"id": s.get("organization_id")}, {"_id": 0, "name": 1, "owner_email": 1, "plan": 1, "subscription_status": 1})
        if org:
            s["org_name"] = org.get("name", "")
            s["owner_email"] = org.get("owner_email", "")
            s["current_plan"] = org.get("plan", "")
            s["subscription_status"] = org.get("subscription_status", "")

    return {"submissions": subs, "total": len(subs)}



# ---------------------------------------------------------------------------
# Data Migration: Fix Partial Invoices with Wrong fund_source
# ---------------------------------------------------------------------------
@router.post("/migrations/fix-partial-fund-source")
async def fix_partial_fund_source(data: dict = None, user=Depends(require_super_admin)):
    """
    One-time migration: fix partial invoices that were incorrectly assigned
    fund_source='digital' due to is_digital_payment('Partial') returning True.

    For each corrupted invoice:
    1. Set fund_source → 'cashier'
    2. Remove incorrect digital_platform and receipt_status fields
    3. Move cash (amount_paid) from digital wallet → cashier wallet
    4. Log every change for audit trail

    Safe to run multiple times (idempotent).
    """
    dry_run = (data or {}).get("dry_run", False)
    fixes = []

    # Find all corrupted partial invoices across the entire database
    corrupted = await _raw_db.invoices.find(
        {
            "payment_type": "partial",
            "fund_source": "digital",
            "digital_platform": "Partial",
        },
        {"_id": 0}
    ).to_list(1000)

    if not corrupted:
        return {"message": "No corrupted partial invoices found. Nothing to fix.", "fixed": 0}

    for inv in corrupted:
        inv_id = inv.get("id", "")
        inv_num = inv.get("invoice_number", "")
        branch_id = inv.get("branch_id", "")
        amount_paid = float(inv.get("amount_paid", 0))
        org_id = inv.get("_org_id", "unknown")

        fix_record = {
            "invoice_id": inv_id,
            "invoice_number": inv_num,
            "branch_id": branch_id,
            "org_id": org_id,
            "amount_paid": amount_paid,
            "action": "dry_run" if dry_run else "fixed",
        }

        if not dry_run:
            # 1. Fix the invoice record
            await _raw_db.invoices.update_one(
                {"id": inv_id},
                {
                    "$set": {"fund_source": "cashier"},
                    "$unset": {"digital_platform": "", "receipt_status": ""},
                }
            )

            # 2. Fix the payment records inside the invoice
            await _raw_db.invoices.update_one(
                {"id": inv_id},
                {"$set": {"payments.$[elem].fund_source": "cashier"}},
                array_filters=[{"elem.fund_source": "digital"}],
            )

            # 3. Move cash from digital wallet → cashier wallet
            if amount_paid > 0 and branch_id:
                ref_text = f"Migration fix: partial invoice {inv_num} — cash moved from digital to cashier"

                # Deduct from digital wallet
                digital_wallet = await _raw_db.fund_wallets.find_one(
                    {"branch_id": branch_id, "type": "digital", "active": True, "_org_id": org_id},
                    {"_id": 0}
                )
                if digital_wallet:
                    await _raw_db.fund_wallets.update_one(
                        {"id": digital_wallet["id"]},
                        {"$inc": {"balance": -round(amount_paid, 2)}}
                    )
                    await _raw_db.wallet_movements.insert_one({
                        "id": new_id(),
                        "_org_id": org_id,
                        "wallet_id": digital_wallet["id"],
                        "branch_id": branch_id,
                        "type": "migration_correction",
                        "amount": -round(amount_paid, 2),
                        "reference": ref_text,
                        "created_at": now_iso(),
                    })

                # Add to cashier wallet
                cashier_wallet = await _raw_db.fund_wallets.find_one(
                    {"branch_id": branch_id, "type": "cashier", "active": True, "_org_id": org_id},
                    {"_id": 0}
                )
                if cashier_wallet:
                    await _raw_db.fund_wallets.update_one(
                        {"id": cashier_wallet["id"]},
                        {"$inc": {"balance": round(amount_paid, 2)}}
                    )
                    await _raw_db.wallet_movements.insert_one({
                        "id": new_id(),
                        "_org_id": org_id,
                        "wallet_id": cashier_wallet["id"],
                        "branch_id": branch_id,
                        "type": "migration_correction",
                        "amount": round(amount_paid, 2),
                        "reference": ref_text,
                        "created_at": now_iso(),
                    })

                fix_record["wallet_moved"] = True
                fix_record["digital_wallet_found"] = bool(digital_wallet)
                fix_record["cashier_wallet_found"] = bool(cashier_wallet)

        fixes.append(fix_record)

    return {
        "message": f"{'DRY RUN — ' if dry_run else ''}Fixed {len(fixes)} corrupted partial invoice(s)",
        "dry_run": dry_run,
        "fixed": len(fixes),
        "details": fixes,
    }
