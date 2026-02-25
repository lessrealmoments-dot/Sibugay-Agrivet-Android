"""
Transaction Verification routes.
Allows authorized personnel to verify POs, Expenses, and Branch Transfers.

PIN hierarchy (in order of check):
  1. Admin PIN  — stored in system_settings as hashed value
  2. Admin TOTP — admin's Google Authenticator code
  3. Auditor PIN — any user with is_auditor=True and auditor_pin set

A verified transaction shows a badge. Discrepancies are noted (not immediately
applied to inventory). They accumulate in the discrepancy_log and are resolved
at the end of the audit via "Apply Correction" or "Dismiss".
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
import pyotp
from config import db
from utils import get_current_user, now_iso, new_id, hash_password, verify_password
from utils.security import log_failed_pin_attempt

router = APIRouter(prefix="/verify", tags=["Verification"])

VERIFIABLE_TYPES = {
    "purchase_order": "db.purchase_orders",
    "expense": "db.expenses",
    "branch_transfer": "db.branch_transfer_orders",
}

COLLECTION_MAP = {
    "purchase_order": "purchase_orders",
    "expense": "expenses",
    "branch_transfer": "branch_transfer_orders",
}


# ─────────────────────────────────────────────────────────────────────────────
#  PIN Verification helper
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_pin(pin: str) -> Optional[dict]:
    """
    Returns verifier info dict if pin matches any of:
      - Admin PIN (system_settings.admin_pin)
      - Admin TOTP
      - Auditor PIN (user with is_auditor=True)
    Returns None if no match.
    """
    if not pin:
        return None

    # 1. Admin PIN (plain PIN stored in system settings)
    admin_pin_doc = await db.system_settings.find_one({"key": "admin_pin"}, {"_id": 0})
    if admin_pin_doc:
        stored = admin_pin_doc.get("pin_hash", "")
        if stored and verify_password(pin, stored):
            return {"verifier_id": "system_admin", "verifier_name": "Admin", "method": "admin_pin"}

    # 2. Admin TOTP (6-digit code)
    if len(pin) == 6 and pin.isdigit():
        admins = await db.users.find(
            {"role": "admin", "active": True, "totp_enabled": True}, {"_id": 0}
        ).to_list(10)
        for admin in admins:
            secret = admin.get("totp_secret")
            if secret:
                totp = pyotp.TOTP(secret)
                if totp.verify(pin, valid_window=1):
                    return {
                        "verifier_id": admin["id"],
                        "verifier_name": admin.get("full_name", admin["username"]),
                        "method": "totp",
                    }

    # 3. Auditor PIN
    auditors = await db.users.find(
        {"is_auditor": True, "active": True}, {"_id": 0}
    ).to_list(50)
    for auditor in auditors:
        auditor_pin = auditor.get("auditor_pin", "")
        if auditor_pin and pin == auditor_pin:
            return {
                "verifier_id": auditor["id"],
                "verifier_name": auditor.get("full_name", auditor["username"]),
                "method": "auditor_pin",
            }

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Admin PIN management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin-pin/set")
async def set_admin_pin(data: dict, user=Depends(get_current_user)):
    """Set or change the admin verification PIN (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    pin = str(data.get("pin", ""))
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")

    await db.system_settings.update_one(
        {"key": "admin_pin"},
        {"$set": {
            "key": "admin_pin",
            "pin_hash": hash_password(pin),
            "set_by": user["id"],
            "set_at": now_iso(),
        }},
        upsert=True,
    )
    return {"message": "Admin PIN set successfully"}


@router.get("/admin-pin/status")
async def admin_pin_status(user=Depends(get_current_user)):
    """Check if admin PIN has been set."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    doc = await db.system_settings.find_one({"key": "admin_pin"}, {"_id": 0})
    return {"configured": bool(doc and doc.get("pin_hash"))}


# ─────────────────────────────────────────────────────────────────────────────
#  Verify a transaction
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{doc_type}/{doc_id}")
async def verify_transaction(
    doc_type: str,
    doc_id: str,
    data: dict,
    user=Depends(get_current_user),
):
    """
    Verify a transaction. Requires valid admin/auditor PIN.
    Optionally records a discrepancy with expected vs found values.
    """
    if doc_type not in COLLECTION_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid document type: {doc_type}. Must be one of: {list(COLLECTION_MAP.keys())}")

    collection = getattr(db, COLLECTION_MAP[doc_type])
    doc = await collection.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pin = str(data.get("pin", ""))
    verifier = await _resolve_pin(pin)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid PIN — not recognized as admin PIN, TOTP, or auditor PIN")

    has_discrepancy = bool(data.get("has_discrepancy", False))
    discrepancy_note = data.get("discrepancy_note", "")
    expected_qty = data.get("expected_qty")
    found_qty = data.get("found_qty")
    unit = data.get("unit", "")
    unit_cost = float(data.get("unit_cost", 0))
    item_description = data.get("item_description", "")

    # Compute value impact
    value_impact = None
    if has_discrepancy and expected_qty is not None and found_qty is not None:
        variance = float(found_qty) - float(expected_qty)
        value_impact = round(variance * unit_cost, 2)

    verification = {
        "verified": True,
        "verified_by_id": verifier["verifier_id"],
        "verified_by_name": verifier["verifier_name"],
        "verified_method": verifier["method"],
        "verified_at": now_iso(),
        "verification_status": "discrepancy" if has_discrepancy else "clean",
        "has_discrepancy": has_discrepancy,
        "discrepancy": {
            "note": discrepancy_note,
            "item_description": item_description,
            "expected_qty": expected_qty,
            "found_qty": found_qty,
            "unit": unit,
            "unit_cost": unit_cost,
            "value_impact": value_impact,
            "resolved": False,
            "resolution": None,
            "resolved_at": None,
            "resolved_by": None,
        } if has_discrepancy else None,
    }

    await collection.update_one({"id": doc_id}, {"$set": verification})

    # Log discrepancy separately for quick querying
    if has_discrepancy:
        branch_id = doc.get("branch_id", "")
        # Get doc date for the report
        doc_date = (
            doc.get("purchase_date") or doc.get("date") or
            doc.get("created_at", "")[:10]
        )
        doc_number = (
            doc.get("po_number") or doc.get("order_number") or
            doc.get("id", "")
        )
        doc_title = (
            doc.get("vendor") or doc.get("description") or doc.get("order_number", "")
        )

        log_entry = {
            "id": new_id(),
            "doc_type": doc_type,
            "doc_id": doc_id,
            "doc_number": doc_number,
            "doc_title": doc_title,
            "doc_date": doc_date,
            "branch_id": branch_id,
            "item_description": item_description,
            "expected_qty": expected_qty,
            "found_qty": found_qty,
            "unit": unit,
            "unit_cost": unit_cost,
            "value_impact": value_impact,
            "note": discrepancy_note,
            "verified_by_name": verifier["verifier_name"],
            "verified_at": now_iso(),
            "resolved": False,
            "resolution": None,
            "resolved_at": None,
            "resolved_by": None,
        }
        await db.discrepancy_log.insert_one(log_entry)

    return {
        "message": "Transaction verified",
        "verified_by": verifier["verifier_name"],
        "method": verifier["method"],
        "status": "discrepancy" if has_discrepancy else "clean",
    }


@router.delete("/{doc_type}/{doc_id}")
async def unverify_transaction(
    doc_type: str,
    doc_id: str,
    user=Depends(get_current_user),
):
    """Remove verification from a transaction (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if doc_type not in COLLECTION_MAP:
        raise HTTPException(status_code=400, detail="Invalid document type")

    collection = getattr(db, COLLECTION_MAP[doc_type])
    await collection.update_one(
        {"id": doc_id},
        {"$unset": {
            "verified": "", "verified_by_id": "", "verified_by_name": "",
            "verified_method": "", "verified_at": "", "verification_status": "",
            "has_discrepancy": "", "discrepancy": "",
        }}
    )
    # Remove from discrepancy log
    await db.discrepancy_log.delete_many({"doc_id": doc_id, "resolved": False})
    return {"message": "Verification removed"}


# ─────────────────────────────────────────────────────────────────────────────
#  Discrepancy Report
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/discrepancies")
async def list_discrepancies(
    branch_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    doc_type: Optional[str] = None,
    user=Depends(get_current_user),
):
    """List all discrepancy log entries."""
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    elif user.get("branch_id") and user.get("role") not in ["admin"]:
        query["branch_id"] = user["branch_id"]
    if resolved is not None:
        query["resolved"] = resolved
    if doc_type:
        query["doc_type"] = doc_type

    entries = await db.discrepancy_log.find(query, {"_id": 0}).sort("verified_at", -1).to_list(500)
    return {"discrepancies": entries, "total": len(entries)}


@router.post("/discrepancies/{log_id}/resolve")
async def resolve_discrepancy(
    log_id: str,
    data: dict,
    user=Depends(get_current_user),
):
    """
    Resolve a discrepancy:
      action='apply'  → creates an inventory correction (if applicable)
      action='dismiss' → marks as dismissed with justification
    """
    entry = await db.discrepancy_log.find_one({"id": log_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Discrepancy log entry not found")
    if entry.get("resolved"):
        raise HTTPException(status_code=400, detail="Already resolved")

    action = data.get("action", "dismiss")  # 'apply' | 'dismiss'
    justification = data.get("justification", "")

    resolution_note = f"{action.upper()}: {justification}" if justification else action.upper()

    await db.discrepancy_log.update_one(
        {"id": log_id},
        {"$set": {
            "resolved": True,
            "resolution": action,
            "resolution_note": resolution_note,
            "resolved_at": now_iso(),
            "resolved_by": user.get("full_name", user["username"]),
        }}
    )

    # Also update the parent document's discrepancy.resolved flag
    if entry.get("doc_type") and entry.get("doc_id") and entry["doc_type"] in COLLECTION_MAP:
        collection = getattr(db, COLLECTION_MAP[entry["doc_type"]])
        await collection.update_one(
            {"id": entry["doc_id"]},
            {"$set": {
                "discrepancy.resolved": True,
                "discrepancy.resolution": resolution_note,
                "discrepancy.resolved_at": now_iso(),
                "discrepancy.resolved_by": user.get("full_name", user["username"]),
                "verification_status": "resolved",
            }}
        )

    return {"message": f"Discrepancy {action}d successfully"}
