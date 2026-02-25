"""
Super Admin Authentication — separate portal at /admin
Steps:
  1. POST /api/admin-auth/login  → validate email + password → returns pending_token (5 min)
  2. POST /api/admin-auth/totp   → validate TOTP code + pending_token → returns full JWT
  3. POST /api/admin-auth/setup-totp  → first-time TOTP setup (generates QR + backup codes)
  4. POST /api/admin-auth/verify-setup → confirm first TOTP code + receive backup codes
  5. POST /api/admin-auth/recover → use a backup code to bypass TOTP
"""
import secrets
import hashlib
import pyotp
import jwt
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from config import _raw_db, JWT_SECRET
from utils import hash_password, verify_password, now_iso, new_id
from utils.auth import create_token

router = APIRouter(prefix="/admin-auth", tags=["Admin Auth"])

PENDING_TOTP_SECRET = JWT_SECRET + "_pending"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _make_pending_token(user_id: str) -> str:
    """Short-lived token that proves password was verified, awaiting TOTP."""
    payload = {
        "type": "pending_totp",
        "user_id": user_id,
        "exp": datetime.now(timezone.utc).timestamp() + 300,  # 5 min
    }
    return jwt.encode(payload, PENDING_TOTP_SECRET, algorithm="HS256")


def _verify_pending_token(token: str) -> str:
    """Returns user_id if valid pending token."""
    try:
        payload = jwt.decode(token, PENDING_TOTP_SECRET, algorithms=["HS256"])
        if payload.get("type") != "pending_totp":
            raise ValueError
        return payload["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please start over.")


# ---------------------------------------------------------------------------
# Step 1: Password validation
# ---------------------------------------------------------------------------
@router.post("/login")
async def admin_login(data: dict):
    """Validate super admin email + password. Returns pending_token for TOTP step."""
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = await _raw_db.users.find_one(
        {"email": email, "is_super_admin": True}, {"_id": 0}
    )

    # Generic error — don't reveal whether user exists
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    totp_ready = bool(user.get("totp_enabled") and user.get("totp_secret"))
    pending_token = _make_pending_token(user["id"])

    return {
        "pending_token": pending_token,
        "totp_ready": totp_ready,
        "message": "Password verified. Please complete TOTP verification." if totp_ready else "Setup your Google Authenticator to continue.",
    }


# ---------------------------------------------------------------------------
# Step 2a: TOTP verification
# ---------------------------------------------------------------------------
@router.post("/totp")
async def admin_totp(data: dict):
    """Verify TOTP code using pending_token. Returns full JWT on success."""
    pending_token = data.get("pending_token", "")
    code = data.get("code", "").strip()

    user_id = _verify_pending_token(pending_token)
    user = await _raw_db.users.find_one({"id": user_id, "is_super_admin": True}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    secret = user.get("totp_secret")
    if not secret or not user.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="TOTP not configured. Please set up Google Authenticator first.")

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid code. Check your Google Authenticator.")

    # Log the login
    await _raw_db.users.update_one(
        {"id": user_id},
        {"$set": {"last_admin_login": now_iso()}}
    )

    token = create_token(user["id"], "admin", org_id=None, is_super_admin=True)
    safe_user = {k: v for k, v in user.items() if k not in ("password_hash", "totp_secret", "_id")}
    return {"token": token, "user": safe_user}


# ---------------------------------------------------------------------------
# Step 2b: Recovery code (bypass TOTP)
# ---------------------------------------------------------------------------
@router.post("/recover")
async def admin_recover(data: dict):
    """Use a backup recovery code instead of TOTP."""
    pending_token = data.get("pending_token", "")
    recovery_code = data.get("recovery_code", "").strip().upper()

    user_id = _verify_pending_token(pending_token)
    user = await _raw_db.users.find_one({"id": user_id, "is_super_admin": True}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    stored_codes = user.get("backup_codes", [])
    code_hash = _hash_code(recovery_code)

    # Find the matching unused backup code
    matched = next((c for c in stored_codes if c["hash"] == code_hash and not c["used"]), None)
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid or already-used recovery code.")

    # Mark code as used
    updated_codes = [
        {**c, "used": True, "used_at": now_iso()} if c["hash"] == code_hash else c
        for c in stored_codes
    ]
    await _raw_db.users.update_one(
        {"id": user_id},
        {"$set": {"backup_codes": updated_codes, "last_admin_login": now_iso()}}
    )

    token = create_token(user["id"], "admin", org_id=None, is_super_admin=True)
    safe_user = {k: v for k, v in user.items() if k not in ("password_hash", "totp_secret", "_id")}
    return {"token": token, "user": safe_user, "warning": "Recovery code used. Please set up Google Authenticator again."}


# ---------------------------------------------------------------------------
# TOTP Setup (first time)
# ---------------------------------------------------------------------------
@router.post("/setup-totp")
async def setup_totp(data: dict):
    """Generate TOTP secret and QR code for first-time setup."""
    pending_token = data.get("pending_token", "")
    user_id = _verify_pending_token(pending_token)

    user = await _raw_db.users.find_one({"id": user_id, "is_super_admin": True}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(
        name=user.get("email", "superadmin"),
        issuer_name="AgriBooks Platform Admin"
    )

    # Store unverified secret
    await _raw_db.users.update_one(
        {"id": user_id},
        {"$set": {"totp_secret": secret, "totp_enabled": False, "totp_verified": False}}
    )

    return {"secret": secret, "qr_uri": qr_uri, "pending_token": pending_token}


@router.post("/verify-setup")
async def verify_totp_setup(data: dict):
    """Verify first TOTP code, enable TOTP, generate backup codes."""
    pending_token = data.get("pending_token", "")
    code = data.get("code", "").strip()

    user_id = _verify_pending_token(pending_token)
    user = await _raw_db.users.find_one({"id": user_id, "is_super_admin": True}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    secret = user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="No TOTP secret found. Run setup first.")

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return {"verified": False, "error": "Invalid code — check your Google Authenticator"}

    # Generate 8 backup codes
    plain_codes = [f"{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}" for _ in range(8)]
    hashed_codes = [{"hash": _hash_code(c), "used": False, "created_at": now_iso()} for c in plain_codes]

    await _raw_db.users.update_one(
        {"id": user_id},
        {"$set": {
            "totp_enabled": True,
            "totp_verified": True,
            "backup_codes": hashed_codes,
            "totp_setup_at": now_iso(),
        }}
    )

    # Send backup codes via email
    from services.email_service import send_superadmin_backup_codes
    user_email = user.get("email", "")
    if user_email:
        await send_superadmin_backup_codes(user_email, plain_codes)

    # Issue full JWT now that TOTP is verified
    token = create_token(user["id"], "admin", org_id=None, is_super_admin=True)

    return {
        "verified": True,
        "backup_codes": plain_codes,
        "token": token,
        "message": "TOTP enabled! Backup codes sent to your email. Store them safely.",
    }


# ---------------------------------------------------------------------------
# Status check (no auth needed — just checks if TOTP is set up)
# ---------------------------------------------------------------------------
@router.get("/status")
async def admin_portal_status():
    """Check portal readiness — generic response for security."""
    # Don't reveal whether super admin exists or TOTP status
    return {"portal": "active"}
