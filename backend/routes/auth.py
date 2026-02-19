"""
Authentication routes for AgriPOS
"""
from fastapi import APIRouter, HTTPException, Depends

import sys
sys.path.insert(0, '/app/backend')

from database import db, now_iso, new_id
from auth import (
    get_current_user, check_perm, hash_password, verify_password, 
    create_token, DEFAULT_PERMISSIONS
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login")
async def login(data: dict):
    user = await db.users.find_one({"username": data.get("username"), "active": True}, {"_id": 0})
    if not user or not verify_password(data.get("password", ""), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["id"], user["role"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}

@router.post("/register")
async def register(data: dict, user=Depends(get_current_user)):
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
    return {k: v for k, v in user.items() if k != "password_hash"}

@router.put("/change-password")
async def change_password(data: dict, user=Depends(get_current_user)):
    if not verify_password(data.get("current_password", ""), user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(data["new_password"])}})
    return {"message": "Password changed"}
