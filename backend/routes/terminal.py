"""
AgriSmart Terminal — Device pairing & session management.
YouTube TV-style login: terminal shows a 6-char code, PC enters it to pair.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
import secrets
import string
from config import db, _raw_db
from utils import get_current_user, now_iso, new_id, create_token

router = APIRouter(prefix="/terminal", tags=["Terminal"])

CODE_CHARS = string.ascii_uppercase + string.digits
CODE_LENGTH = 6
CODE_EXPIRY_MINUTES = 5


def _generate_code() -> str:
    """Generate a random 6-char alphanumeric code (uppercase + digits)."""
    return ''.join(secrets.choice(CODE_CHARS) for _ in range(CODE_LENGTH))


@router.post("/generate-code")
async def generate_pairing_code():
    """
    Terminal requests a pairing code. No auth required.
    Returns a 6-char code that the user enters on their PC.
    Code expires in 5 minutes.
    """
    # Generate unique code (retry if collision)
    for _ in range(10):
        code = _generate_code()
        existing = await _raw_db.terminal_codes.find_one(
            {"code": code, "status": "pending",
             "expires_at": {"$gt": now_iso()}},
            {"_id": 0}
        )
        if not existing:
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate unique code")

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRY_MINUTES)).isoformat()

    doc = {
        "id": new_id(),
        "code": code,
        "status": "pending",
        "created_at": now_iso(),
        "expires_at": expires_at,
    }
    await _raw_db.terminal_codes.insert_one(doc)

    return {"code": code, "expires_in": CODE_EXPIRY_MINUTES * 60}


@router.get("/poll/{code}")
async def poll_pairing_status(code: str):
    """
    Terminal polls this to check if the code has been paired.
    Returns status: 'pending' | 'paired' | 'expired'.
    When paired, returns token + session data.
    """
    code = code.upper().strip()
    doc = await _raw_db.terminal_codes.find_one({"code": code}, {"_id": 0})

    if not doc:
        return {"status": "invalid"}

    # Check expiry
    if doc["status"] == "pending":
        expires = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires:
            await _raw_db.terminal_codes.update_one(
                {"code": code}, {"$set": {"status": "expired"}}
            )
            return {"status": "expired"}

    if doc["status"] == "paired":
        # Return session data
        session = await _raw_db.terminal_sessions.find_one(
            {"code": code}, {"_id": 0}
        )
        if session:
            return {
                "status": "paired",
                "token": session["token"],
                "terminal_id": session["terminal_id"],
                "branch_id": session["branch_id"],
                "branch_name": session.get("branch_name", ""),
                "user_name": session.get("user_name", ""),
                "organization_id": session.get("organization_id", ""),
            }

    return {"status": doc["status"]}


@router.post("/pair")
async def pair_terminal(data: dict, user=Depends(get_current_user)):
    """
    PC user enters the 6-char code + selects a branch to pair.
    Creates a terminal session with an auth token.
    """
    code = (data.get("code") or "").upper().strip()
    branch_id = data.get("branch_id")

    if not code or len(code) != CODE_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid pairing code")
    if not branch_id:
        raise HTTPException(status_code=400, detail="Branch ID required")

    # Verify code
    doc = await _raw_db.terminal_codes.find_one(
        {"code": code, "status": "pending"}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Code not found or already used")

    # Check expiry
    expires = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires:
        await _raw_db.terminal_codes.update_one(
            {"code": code}, {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=410, detail="Code expired — generate a new one on the terminal")

    # Verify branch exists
    branch = await db.branches.find_one({"id": branch_id}, {"_id": 0})
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    org_id = user.get("organization_id")
    terminal_id = new_id()

    # Create auth token for the terminal (same as regular user token)
    token = create_token(user["id"], user["role"], org_id=org_id)

    # Create terminal session
    session = {
        "id": new_id(),
        "terminal_id": terminal_id,
        "code": code,
        "branch_id": branch_id,
        "branch_name": branch.get("name", ""),
        "user_id": user["id"],
        "user_name": user.get("full_name", user.get("username", "")),
        "organization_id": org_id,
        "token": token,
        "status": "active",
        "paired_at": now_iso(),
        "last_seen": now_iso(),
    }
    await _raw_db.terminal_sessions.insert_one(session)

    # Update code status
    await _raw_db.terminal_codes.update_one(
        {"code": code},
        {"$set": {"status": "paired", "paired_at": now_iso(), "terminal_id": terminal_id}}
    )

    return {
        "message": f"Terminal paired to {branch.get('name', branch_id)}",
        "terminal_id": terminal_id,
        "branch_name": branch.get("name", ""),
    }


@router.get("/session")
async def get_terminal_session(user=Depends(get_current_user)):
    """Validate current terminal session and return branch info."""
    session = await _raw_db.terminal_sessions.find_one(
        {"user_id": user["id"], "status": "active"},
        {"_id": 0},
        sort=[("paired_at", -1)]
    )
    if not session:
        raise HTTPException(status_code=404, detail="No active terminal session")

    # Update last seen
    await _raw_db.terminal_sessions.update_one(
        {"terminal_id": session["terminal_id"]},
        {"$set": {"last_seen": now_iso()}}
    )

    branch = await db.branches.find_one({"id": session["branch_id"]}, {"_id": 0})

    return {
        "terminal_id": session["terminal_id"],
        "branch_id": session["branch_id"],
        "branch_name": session.get("branch_name", branch.get("name", "") if branch else ""),
        "user_name": session.get("user_name", ""),
        "paired_at": session["paired_at"],
    }


@router.get("/active")
async def list_active_terminals(user=Depends(get_current_user)):
    """List all active terminal sessions for the current org."""
    org_id = user.get("organization_id")
    query = {"status": "active"}
    if org_id:
        query["organization_id"] = org_id

    sessions = await _raw_db.terminal_sessions.find(
        query, {"_id": 0, "token": 0}
    ).sort("paired_at", -1).to_list(50)

    return sessions


@router.post("/disconnect/{terminal_id}")
async def disconnect_terminal(terminal_id: str, user=Depends(get_current_user)):
    """Disconnect/unpair a terminal."""
    result = await _raw_db.terminal_sessions.update_one(
        {"terminal_id": terminal_id},
        {"$set": {"status": "disconnected", "disconnected_at": now_iso()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Terminal not found")

    return {"message": "Terminal disconnected"}
