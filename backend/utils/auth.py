"""
Authentication utilities: password hashing, JWT tokens, permission checking.
"""
import bcrypt
import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import db, JWT_SECRET, set_org_context

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str, org_id: str = None, is_super_admin: bool = False) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc).timestamp() + 86400,  # 24h
    }
    if org_id:
        payload["org_id"] = org_id
    if is_super_admin:
        payload["is_super_admin"] = True
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: decode JWT, set org context, return user. Also checks for delegation tokens."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    is_super_admin = payload.get("is_super_admin", False)
    org_id = payload.get("org_id")

    # Set org context for tenant isolation (None = super admin = unscoped)
    set_org_context(None if is_super_admin else org_id)

    # Find user — login uses no context so this is an unscoped lookup by id
    from config import _raw_db
    user = await _raw_db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Check for delegated module access from JWT payload
    if payload.get("delegations"):
        user["_delegations"] = payload["delegations"]

    return user


def check_perm(user: dict, module: str, action: str):
    if user.get("role") == "admin" or user.get("is_super_admin"):
        return
    module_map = {"pos": "sales"}
    actual_module = module_map.get(module, module)
    action_map = {
        ("pos", "sell"): ("sales", "create"),
        ("accounting", "create"): ("accounting", "receive_payment"),
    }
    if (module, action) in action_map:
        actual_module, action = action_map[(module, action)]
    perms = user.get("permissions", {})
    if not perms.get(actual_module, {}).get(action, False):
        # Check if user has a delegation override for this module
        delegations = user.get("_delegations", {})
        if actual_module in delegations:
            return  # Delegated access granted
        raise HTTPException(status_code=403, detail=f"No permission: {actual_module}.{action}")


def has_perm(user: dict, module: str, action: str) -> bool:
    if user.get("role") == "admin" or user.get("is_super_admin"):
        return True
    module_map = {"pos": "sales"}
    actual_module = module_map.get(module, module)
    perms = user.get("permissions", {})
    return perms.get(actual_module, {}).get(action, False)
