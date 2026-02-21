"""
Authentication routes: login, register, password management, TOTP setup.
"""
from fastapi import APIRouter, Depends, HTTPException
import pyotp
from config import db
from utils import (
    hash_password, verify_password, create_token,
    get_current_user, check_perm, now_iso, new_id
)
from models import DEFAULT_PERMISSIONS

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
async def login(data: dict):
    """Authenticate user and return JWT token."""
    user = await db.users.find_one(
        {"username": data.get("username"), "active": True},
        {"_id": 0}
    )
    if not user or not verify_password(data.get("password", ""), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["role"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}


@router.post("/register")
async def register(data: dict, user=Depends(get_current_user)):
    """Register a new user (admin only)."""
    check_perm(user, "settings", "manage_users")
    
    existing = await db.users.find_one({"username": data["username"]}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    role = data.get("role", "cashier")
    new_user = {
        "id": new_id(),
        "username": data["username"],
        "full_name": data.get("full_name", ""),
        "email": data.get("email", ""),
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
    """Get current user info."""
    return {k: v for k, v in user.items() if k != "password_hash"}


@router.put("/change-password")
async def change_password(data: dict, user=Depends(get_current_user)):
    """Change user's password."""
    if not verify_password(data.get("current_password", ""), user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(data["new_password"])}}
    )
    return {"message": "Password changed"}


@router.post("/verify-manager-pin")
async def verify_manager_pin(data: dict, user=Depends(get_current_user)):
    """
    Verify a PIN with optional role level requirement.
    required_level: "manager" (default) = any manager/admin PIN
                    "admin"              = only admin/owner PIN
    """
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
                "manager_name": mgr.get("full_name", mgr["username"]),
                "role": mgr["role"],
            }

    if required_level == "admin":
        return {"valid": False, "error": "Invalid — only admin PIN accepted for this action"}
    return {"valid": False}


@router.put("/set-manager-pin")
async def set_manager_pin(data: dict, user=Depends(get_current_user)):
    """Set manager PIN for credit approvals."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only managers/admins can set PINs")
    
    pin = data.get("pin", "")
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    
    await db.users.update_one({"id": user["id"]}, {"$set": {"manager_pin": pin}})
    return {"message": "PIN set successfully"}


# ── TOTP (Authenticator App) Endpoints ──────────────────────────────────────

@router.get("/totp/status")
async def get_totp_status(user=Depends(get_current_user)):
    """Get TOTP setup status for the current admin user."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return {
        "enabled": bool(user.get("totp_enabled")),
        "verified": bool(user.get("totp_verified")),
    }


@router.post("/totp/setup")
async def setup_totp(user=Depends(get_current_user)):
    """Generate a new TOTP secret and return the QR provisioning URI."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get("username", "admin"),
        issuer_name="AgriPOS"
    )
    # Store unverified secret (totp_enabled remains False until confirmed)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"totp_secret": secret, "totp_enabled": False, "totp_verified": False}}
    )
    return {"secret": secret, "qr_uri": provisioning_uri}


@router.post("/totp/verify-setup")
async def verify_totp_setup(data: dict, user=Depends(get_current_user)):
    """Confirm TOTP is working by entering the first generated code."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    code = data.get("code", "")
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
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
    """Disable TOTP for the current admin user."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"totp_secret": "", "totp_enabled": "", "totp_verified": ""}}
    )
    return {"message": "TOTP disabled"}


@router.post("/verify-admin-action")
async def verify_admin_action(data: dict, user=Depends(get_current_user)):
    """
    Verify a sensitive admin action via:
      mode='totp'     → 6-digit code from authenticator app (admin only)
      mode='password' → admin's full login password (fallback)
    Returns { valid, manager_id, manager_name, mode_used }
    """
    from routes.notifications import create_pin_notification

    mode = data.get("mode", "totp")
    code = data.get("code", "")
    context = data.get("context", "")

    if not code:
        raise HTTPException(status_code=400, detail="Code is required")

    admins = await db.users.find(
        {"role": "admin", "active": True}, {"_id": 0}
    ).to_list(20)

    for admin in admins:
        if mode == "totp":
            secret = admin.get("totp_secret")
            if secret and admin.get("totp_enabled"):
                totp = pyotp.TOTP(secret)
                if totp.verify(code, valid_window=1):
                    if context:
                        await create_pin_notification(
                            context, admin["id"],
                            admin.get("full_name", admin["username"])
                        )
                    return {
                        "valid": True,
                        "manager_id": admin["id"],
                        "manager_name": admin.get("full_name", admin["username"]),
                        "mode_used": "totp",
                    }
        elif mode == "password":
            if verify_password(code, admin.get("password_hash", "")):
                if context:
                    await create_pin_notification(
                        context, admin["id"],
                        admin.get("full_name", admin["username"])
                    )
                return {
                    "valid": True,
                    "manager_id": admin["id"],
                    "manager_name": admin.get("full_name", admin["username"]),
                    "mode_used": "password",
                }

    if mode == "totp":
        return {"valid": False, "error": "Invalid code — check your authenticator app"}
    return {"valid": False, "error": "Invalid password"}
