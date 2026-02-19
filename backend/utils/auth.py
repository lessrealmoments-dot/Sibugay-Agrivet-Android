"""
Authentication utilities: password hashing, JWT tokens, permission checking.
"""
import bcrypt
import jwt
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import db, JWT_SECRET

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc).timestamp() + 86400  # 24 hours
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get the current authenticated user."""
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
    """Check if user has permission for a specific action on a module.
    Admin role always has full access.
    Maps legacy module names to new structure for backward compatibility.
    """
    if user.get("role") == "admin":
        return
    
    # Legacy module name mapping
    module_map = {
        "pos": "sales",  # pos.sell -> sales.create, pos.void -> sales.void
    }
    actual_module = module_map.get(module, module)
    
    # Legacy action mapping
    action_map = {
        ("pos", "sell"): ("sales", "create"),
        ("accounting", "create"): ("accounting", "receive_payment"),
    }
    if (module, action) in action_map:
        actual_module, action = action_map[(module, action)]
    
    perms = user.get("permissions", {})
    module_perms = perms.get(actual_module, {})
    
    if not module_perms.get(action, False):
        raise HTTPException(status_code=403, detail=f"No permission: {actual_module}.{action}")


def has_perm(user: dict, module: str, action: str) -> bool:
    """Check permission without raising exception - returns boolean."""
    if user.get("role") == "admin":
        return True
    
    module_map = {"pos": "sales"}
    actual_module = module_map.get(module, module)
    
    perms = user.get("permissions", {})
    return perms.get(actual_module, {}).get(action, False)
