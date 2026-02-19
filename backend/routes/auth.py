"""
Authentication routes: login, register, password management.
"""
from fastapi import APIRouter, Depends, HTTPException
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
    """Verify manager/admin PIN for credit sale approval."""
    pin = data.get("pin", "")
    if not pin:
        raise HTTPException(status_code=400, detail="PIN required")
    
    # Find managers/admins with matching PIN
    managers = await db.users.find(
        {"role": {"$in": ["admin", "manager"]}, "active": True},
        {"_id": 0}
    ).to_list(100)
    
    for mgr in managers:
        # Check if PIN matches
        mgr_pin = mgr.get("manager_pin", "")
        if not mgr_pin:
            # Fallback: use last 4 chars of password hash as PIN
            mgr_pin = mgr.get("password_hash", "")[-4:]
        if mgr_pin and pin == mgr_pin:
            return {
                "valid": True,
                "manager_id": mgr["id"],
                "manager_name": mgr.get("full_name", mgr["username"])
            }
    
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
