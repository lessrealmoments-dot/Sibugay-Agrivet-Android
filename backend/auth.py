"""
Authentication helpers and middleware for AgriPOS
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
import bcrypt
import jwt

from database import db, JWT_SECRET

security = HTTPBearer()

DEFAULT_PERMISSIONS = {
    "admin": {
        "branches": {"view": True, "create": True, "edit": True, "delete": True},
        "products": {"view": True, "create": True, "edit": True, "delete": True},
        "inventory": {"view": True, "adjust": True, "transfer": True},
        "pos": {"view": True, "sell": True, "void": True},
        "customers": {"view": True, "create": True, "edit": True, "delete": True},
        "price_schemes": {"view": True, "create": True, "edit": True, "delete": True},
        "accounting": {"view": True, "create": True, "edit": True, "delete": True},
        "reports": {"view": True, "export": True},
        "settings": {"view": True, "manage_users": True, "manage_roles": True},
    },
    "manager": {
        "branches": {"view": True, "create": False, "edit": True, "delete": False},
        "products": {"view": True, "create": True, "edit": True, "delete": False},
        "inventory": {"view": True, "adjust": True, "transfer": True},
        "pos": {"view": True, "sell": True, "void": True},
        "customers": {"view": True, "create": True, "edit": True, "delete": False},
        "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
        "accounting": {"view": True, "create": True, "edit": True, "delete": False},
        "reports": {"view": True, "export": True},
        "settings": {"view": True, "manage_users": False, "manage_roles": False},
    },
    "cashier": {
        "branches": {"view": True, "create": False, "edit": False, "delete": False},
        "products": {"view": True, "create": False, "edit": False, "delete": False},
        "inventory": {"view": True, "adjust": False, "transfer": False},
        "pos": {"view": True, "sell": True, "void": False},
        "customers": {"view": True, "create": True, "edit": False, "delete": False},
        "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
        "accounting": {"view": False, "create": False, "edit": False, "delete": False},
        "reports": {"view": False, "export": False},
        "settings": {"view": False, "manage_users": False, "manage_roles": False},
    },
}

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, role: str) -> str:
    payload = {"user_id": user_id, "role": role, "exp": datetime.now(timezone.utc).timestamp() + 86400}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user or not user.get("active", True):
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def check_perm(user: dict, module: str, action: str):
    if user.get("role") == "admin":
        return
    perms = user.get("permissions", {})
    if not perms.get(module, {}).get(action, False):
        raise HTTPException(status_code=403, detail=f"No permission: {module}.{action}")
