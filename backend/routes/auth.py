"""
Authentication routes: login (email or username), register, password management, TOTP.
"""
from fastapi import APIRouter, Depends, HTTPException
import pyotp
from config import db, _raw_db
from utils import (
    hash_password, verify_password, create_token,
    get_current_user, check_perm, now_iso, new_id
)
from models import DEFAULT_PERMISSIONS

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
async def login(data: dict):
    """Authenticate user by email only (username no longer supported for new accounts)."""
    email = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Super admin — separate portal enforced (but still works here for backward compat)
    user = await _raw_db.users.find_one(
        {"$or": [{"email": email}, {"username": email}], "is_super_admin": True},
        {"_id": 0}
    )

    if not user:
        # Regular user — email only
        user = await _raw_db.users.find_one(
            {"$or": [{"email": email}, {"username": email}], "active": True},
            {"_id": 0}
        )

    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("active", True):
        raise HTTPException(status_code=401, detail="Account is inactive")

    org_id = user.get("organization_id")
    is_super = user.get("is_super_admin", False)

    # Check org subscription (skip for super admin and demo users)
    if org_id and not is_super:
        org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
        if org and org.get("plan") == "suspended":
            raise HTTPException(
                status_code=403,
                detail="Your organization's subscription is suspended. Please contact support."
            )

    token = create_token(user["id"], user["role"], org_id=org_id, is_super_admin=is_super)
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}

    # Attach subscription info for the frontend
    subscription = None
    if org_id:
        from routes.organizations import get_effective_plan, PLAN_LIMITS, get_grace_info, get_live_feature_flags
        org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
        if org:
            effective = get_effective_plan(org)
            grace = get_grace_info(org)
            flags = await get_live_feature_flags()
            subscription = {
                "plan": org.get("plan"),
                "effective_plan": effective,
                "status": org.get("subscription_status"),
                "trial_ends_at": org.get("trial_ends_at"),
                "features": flags.get(effective, flags.get("basic", {})),
                "max_branches": org.get("max_branches", 1),
                "max_users": org.get("max_users", 5),
                "org_name": org.get("name"),
                "grace_info": grace,
            }

    return {"token": token, "user": safe_user, "subscription": subscription}


@router.post("/register")
async def register(data: dict, user=Depends(get_current_user)):
    """Register a new user within the current org (admin only)."""
    check_perm(user, "settings", "manage_users")

    email = data.get("email", "").strip().lower()
    if email:
        existing = await _raw_db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

    existing_uname = await db.users.find_one({"username": data.get("username", "")}, {"_id": 0})
    if existing_uname:
        raise HTTPException(status_code=400, detail="Username already exists")

    role = data.get("role", "cashier")
    new_user = {
        "id": new_id(),
        "username": data.get("username", email.split("@")[0] if email else new_id()[:8]),
        "full_name": data.get("full_name", ""),
        "email": email,
        "password_hash": hash_password(data["password"]),
        "role": role,
        "branch_id": data.get("branch_id"),
        "permissions": data.get("permissions", DEFAULT_PERMISSIONS.get(role, DEFAULT_PERMISSIONS["cashier"])),
        "active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(new_user)
    safe = {k: v for k, v in new_user.items() if k not in ("password_hash", "_id")}
    return safe


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    result = {k: v for k, v in user.items() if k != "password_hash"}
    org_id = user.get("organization_id")
    if org_id:
        from routes.organizations import get_effective_plan, PLAN_LIMITS, get_grace_info, get_live_feature_flags
        org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
        if org:
            effective = get_effective_plan(org)
            grace = get_grace_info(org)
            flags = await get_live_feature_flags()
            result["subscription"] = {
                "plan": org.get("plan"),
                "effective_plan": effective,
                "status": org.get("subscription_status"),
                "trial_ends_at": org.get("trial_ends_at"),
                "features": flags.get(effective, flags.get("basic", {})),
                "max_branches": org.get("max_branches", 1),
                "max_users": org.get("max_users", 5),
                "org_name": org.get("name"),
                "grace_info": grace,
            }
    return result


@router.put("/change-password")
async def change_password(data: dict, user=Depends(get_current_user)):
    if not verify_password(data.get("current_password", ""), user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(data["new_password"])}}
    )
    return {"message": "Password changed"}


@router.put("/update-profile")
async def update_profile(data: dict, user=Depends(get_current_user)):
    """Update email or full_name."""
    update = {}
    if "full_name" in data:
        update["full_name"] = data["full_name"]
    if "email" in data:
        new_email = data["email"].strip().lower()
        existing = await _raw_db.users.find_one(
            {"email": new_email, "id": {"$ne": user["id"]}}, {"_id": 0}
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        update["email"] = new_email
    if update:
        update["updated_at"] = now_iso()
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    return {"message": "Profile updated"}


@router.post("/verify-manager-pin")
async def verify_manager_pin(data: dict, user=Depends(get_current_user)):
    from routes.notifications import create_pin_notification
    pin = data.get("pin", "")
    if not pin:
        raise HTTPException(status_code=400, detail="PIN required")

    required_level = data.get("required_level", "manager")
    allowed_roles = ["admin"] if required_level == "admin" else ["admin", "manager"]

    managers = await db.users.find(
        {"role": {"$in": allowed_roles}, "active": True}, {"_id": 0}
    ).to_list(100)

    for mgr in managers:
        mgr_pin = mgr.get("manager_pin", "")
        if not mgr_pin:
            mgr_pin = mgr.get("password_hash", "")[-4:]
        if mgr_pin and pin == mgr_pin:
            context = data.get("context")
            if context:
                await create_pin_notification(context, mgr["id"], mgr.get("full_name", mgr["username"]))
            return {
                "valid": True,
                "manager_id": mgr["id"],
                "manager_name": mgr.get("full_name", mgr.get("username", "")),
                "role": mgr["role"],
            }

    if required_level == "admin":
        return {"valid": False, "error": "Invalid — only admin PIN accepted for this action"}
    return {"valid": False}


@router.put("/set-manager-pin")
async def set_manager_pin(data: dict, user=Depends(get_current_user)):
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only managers/admins can set PINs")
    pin = data.get("pin", "")
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    await db.users.update_one({"id": user["id"]}, {"$set": {"manager_pin": pin}})
    return {"message": "PIN set successfully"}


# ── TOTP ──────────────────────────────────────────────────────────────────────

@router.get("/totp/status")
async def get_totp_status(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return {"enabled": bool(user.get("totp_enabled")), "verified": bool(user.get("totp_verified"))}


@router.post("/totp/setup")
async def setup_totp(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get("email") or user.get("username", "admin"),
        issuer_name="AgriBooks"
    )
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"totp_secret": secret, "totp_enabled": False, "totp_verified": False}}
    )
    return {"secret": secret, "qr_uri": provisioning_uri}


@router.post("/totp/verify-setup")
async def verify_totp_setup(data: dict, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    code = data.get("code", "")
    fresh = await _raw_db.users.find_one({"id": user["id"]}, {"_id": 0})
    secret = fresh.get("totp_secret") if fresh else None
    if not secret:
        raise HTTPException(status_code=400, detail="No TOTP secret found. Run setup first.")
    totp = pyotp.TOTP(secret)
    if totp.verify(code, valid_window=1):
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"totp_enabled": True, "totp_verified": True}}
        )
        return {"verified": True}
    return {"verified": False, "error": "Invalid code — try again"}


@router.delete("/totp/disable")
async def disable_totp(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"totp_secret": "", "totp_enabled": "", "totp_verified": ""}}
    )
    return {"message": "TOTP disabled"}


@router.post("/verify-admin-action")
async def verify_admin_action(data: dict, user=Depends(get_current_user)):
    from routes.notifications import create_pin_notification
    from utils.security import log_failed_pin_attempt
    mode = data.get("mode", "totp")
    code = data.get("code", "")
    context = data.get("context", "")

    if not code:
        raise HTTPException(status_code=400, detail="Code is required")

    admins = await db.users.find({"role": "admin", "active": True}, {"_id": 0}).to_list(20)
    first_admin = admins[0] if admins else None
    admin_name = first_admin.get("full_name", first_admin.get("username", "Admin")) if first_admin else "Admin"
    admin_id = first_admin["id"] if first_admin else "system"

    # ── Owner PIN mode ────────────────────────────────────────────────────────
    if mode == "pin":
        pin_doc = await db.system_settings.find_one({"key": "admin_pin"}, {"_id": 0})
        if pin_doc and pin_doc.get("pin_hash"):
            if verify_password(str(code), pin_doc["pin_hash"]):
                if context and first_admin:
                    await create_pin_notification(context, admin_id, admin_name)
                return {"valid": True, "manager_id": admin_id, "manager_name": admin_name, "mode_used": "pin"}
        await log_failed_pin_attempt(user, context or "Admin action authorization", "admin_action")
        return {"valid": False, "error": "Invalid Owner PIN"}

    for admin in admins:
        # ── TOTP mode ─────────────────────────────────────────────────────────
        if mode == "totp":
            secret = admin.get("totp_secret")
            if secret and admin.get("totp_enabled"):
                totp = pyotp.TOTP(secret)
                if totp.verify(code, valid_window=1):
                    if context:
                        await create_pin_notification(
                            context, admin["id"],
                            admin.get("full_name", admin.get("username", ""))
                        )
                    return {
                        "valid": True,
                        "manager_id": admin["id"],
                        "manager_name": admin.get("full_name", admin.get("username", "")),
                        "mode_used": "totp",
                    }
        # ── Password mode ─────────────────────────────────────────────────────
        elif mode == "password":
            if verify_password(code, admin.get("password_hash", "")):
                if context:
                    await create_pin_notification(
                        context, admin["id"],
                        admin.get("full_name", admin.get("username", ""))
                    )
                return {
                    "valid": True,
                    "manager_id": admin["id"],
                    "manager_name": admin.get("full_name", admin.get("username", "")),
                    "mode_used": "password",
                }

    # All attempts failed — log it
    await log_failed_pin_attempt(user, context or "Admin action authorization", "admin_action")
    if mode == "totp":
        return {"valid": False, "error": "Invalid code — check your authenticator app"}
    return {"valid": False, "error": "Invalid password"}
