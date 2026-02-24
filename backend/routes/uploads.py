"""
Receipt Upload routes: QR-based photo upload linked to any record.
Supports: purchase_order, expense, payment, return, branch_transfer, inventory_correction.
Files stored in /app/uploads/ (swap to R2 later by changing storage layer).
Upload links expire in 1 hour. Up to 10 photos per record.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pathlib import Path
import secrets
import os
import mimetypes
from config import db
from utils import get_current_user, now_iso, new_id

router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES = 10

# ─────────────────────────────────────────────────────────────────────────────
#  Record type display labels
# ─────────────────────────────────────────────────────────────────────────────
RECORD_TYPE_LABELS = {
    "purchase_order": "Purchase Order",
    "expense": "Expense",
    "payment": "Supplier Payment",
    "return": "Customer Return",
    "branch_transfer": "Branch Transfer",
    "inventory_correction": "Inventory Correction",
    "invoice": "Sales Invoice",
}


async def _get_record_summary(record_type: str, record_id: str) -> dict:
    """Fetch a brief summary of the linked record for display on the upload page."""
    summary = {"type_label": RECORD_TYPE_LABELS.get(record_type, record_type), "record_id": record_id}
    try:
        if record_type == "purchase_order":
            po = await db.purchase_orders.find_one({"id": record_id}, {"_id": 0})
            if po:
                summary.update({
                    "title": po.get("po_number", ""),
                    "description": f"{po.get('vendor', '')} · DR: {po.get('dr_number', 'N/A')}",
                    "amount": po.get("grand_total") or po.get("subtotal", 0),
                    "date": po.get("purchase_date", ""),
                    "status": po.get("status", ""),
                })
        elif record_type == "expense":
            exp = await db.expenses.find_one({"id": record_id}, {"_id": 0})
            if exp:
                summary.update({
                    "title": exp.get("description", "Expense"),
                    "description": f"{exp.get('category', '')} · {exp.get('payment_method', '')}",
                    "amount": exp.get("amount", 0),
                    "date": exp.get("date", ""),
                    "reference": exp.get("reference_number", ""),
                })
        elif record_type == "payment":
            po = await db.purchase_orders.find_one({"id": record_id}, {"_id": 0})
            if po:
                summary.update({
                    "title": f"Payment — {po.get('vendor', '')}",
                    "description": f"{po.get('po_number', '')} · {po.get('payment_method_detail', 'Cash')}",
                    "amount": po.get("amount_paid", 0),
                    "date": po.get("purchase_date", ""),
                })
        elif record_type == "return":
            ret = await db.returns.find_one({"id": record_id}, {"_id": 0})
            if ret:
                summary.update({
                    "title": ret.get("rma_number", "Return"),
                    "description": f"{ret.get('customer_name', '')} · {ret.get('reason', '')}",
                    "amount": ret.get("refund_amount", 0),
                    "date": ret.get("return_date", ""),
                })
        elif record_type == "branch_transfer":
            bt = await db.branch_transfer_orders.find_one({"id": record_id}, {"_id": 0})
            if bt:
                from_b = await db.branches.find_one({"id": bt.get("from_branch_id")}, {"_id": 0, "name": 1})
                to_b = await db.branches.find_one({"id": bt.get("to_branch_id")}, {"_id": 0, "name": 1})
                summary.update({
                    "title": bt.get("order_number", "Transfer"),
                    "description": f"{from_b.get('name', '') if from_b else ''} → {to_b.get('name', '') if to_b else ''}",
                    "amount": bt.get("total_at_transfer_capital", 0),
                    "date": bt.get("created_at", "")[:10],
                })
    except Exception:
        pass
    return summary


# ─────────────────────────────────────────────────────────────────────────────
#  Generate upload link
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate-link")
async def generate_upload_link(data: dict, user=Depends(get_current_user)):
    """
    Generate a 1-hour upload link and QR for a record.
    Returns: token, upload_url, qr_data.
    """
    record_type = data.get("record_type", "")
    record_id = data.get("record_id", "")
    if not record_type or not record_id:
        raise HTTPException(status_code=400, detail="record_type and record_id required")

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    summary = await _get_record_summary(record_type, record_id)

    doc = {
        "id": new_id(),
        "token": token,
        "token_expires_at": expires_at,
        "record_type": record_type,
        "record_id": record_id,
        "record_summary": summary,
        "files": [],
        "file_count": 0,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.upload_sessions.insert_one(doc)
    del doc["_id"]

    return {
        "token": token,
        "expires_at": expires_at,
        "record_summary": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Public: get record summary for the upload page (no auth, token only)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/preview/{token}")
async def get_upload_preview(token: str):
    """Public endpoint — shows record summary for phone upload page."""
    session = await db.upload_sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Upload link not found")

    expires_at = session.get("token_expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="Upload link has expired. Ask the branch to generate a new link.")
        except ValueError:
            pass

    return {
        "record_summary": session.get("record_summary", {}),
        "file_count": session.get("file_count", 0),
        "max_files": MAX_FILES,
        "expired": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Public: upload files via token (no auth, token only)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload/{token}")
async def upload_files(
    token: str,
    files: List[UploadFile] = File(...),
):
    """Public endpoint — accepts photo uploads from mobile. No login required."""
    session = await db.upload_sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Upload link not found")

    expires_at = session.get("token_expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="Upload link has expired")
        except ValueError:
            pass

    current_count = session.get("file_count", 0)
    if current_count + len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed. Already has {current_count}."
        )

    record_dir = UPLOAD_DIR / session["record_type"] / session["record_id"]
    record_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for file in files:
        file_id = new_id()
        ext = Path(file.filename).suffix if file.filename else ".jpg"
        safe_ext = ext.lower() if ext.lower() in (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".pdf") else ".jpg"
        filename = f"{file_id}{safe_ext}"
        filepath = record_dir / filename

        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        saved.append({
            "id": file_id,
            "filename": file.filename or filename,
            "stored_path": str(filepath),
            "content_type": file.content_type or "image/jpeg",
            "size": len(content),
            "uploaded_at": now_iso(),
        })

    await db.upload_sessions.update_one(
        {"token": token},
        {
            "$push": {"files": {"$each": saved}},
            "$inc": {"file_count": len(saved)},
        }
    )

    return {"uploaded": len(saved), "total_files": current_count + len(saved)}


# ─────────────────────────────────────────────────────────────────────────────
#  Get uploads for a record (auth required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/record/{record_type}/{record_id}")
async def get_record_uploads(
    record_type: str,
    record_id: str,
    user=Depends(get_current_user),
):
    """Get all upload sessions for a record, most recent first."""
    sessions = await db.upload_sessions.find(
        {"record_type": record_type, "record_id": record_id},
        {"_id": 0, "token": 0}  # exclude token from response
    ).sort("created_at", -1).to_list(20)
    total_files = sum(s.get("file_count", 0) for s in sessions)
    return {"sessions": sessions, "total_files": total_files}


# ─────────────────────────────────────────────────────────────────────────────
#  Serve a file (auth required)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate-view-token")
async def generate_view_token(data: dict, user=Depends(get_current_user)):
    """
    Generate a 1-hour read-only view token for a record's uploaded photos.
    Used to create a 'View on Phone' QR code.
    """
    record_type = data.get("record_type", "")
    record_id = data.get("record_id", "")
    if not record_type or not record_id:
        raise HTTPException(status_code=400, detail="record_type and record_id required")

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    summary = await _get_record_summary(record_type, record_id)

    doc = {
        "id": new_id(),
        "token": token,
        "token_type": "view",
        "token_expires_at": expires_at,
        "record_type": record_type,
        "record_id": record_id,
        "record_summary": summary,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.view_tokens.insert_one(doc)
    return {"token": token, "expires_at": expires_at, "record_summary": summary}


@router.get("/view-session/{token}")
async def get_view_session(token: str):
    """
    Public endpoint — returns record summary + all uploaded files for the view QR.
    No auth required (token is the security).
    """
    view_doc = await db.view_tokens.find_one({"token": token, "token_type": "view"}, {"_id": 0})
    if not view_doc:
        raise HTTPException(status_code=404, detail="View link not found or expired")

    expires_at = view_doc.get("token_expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="View link has expired.")
        except ValueError:
            pass

    record_type = view_doc["record_type"]
    record_id = view_doc["record_id"]

    # Get all files for this record
    sessions = await db.upload_sessions.find(
        {"record_type": record_type, "record_id": record_id},
        {"_id": 0, "token": 0}
    ).sort("created_at", -1).to_list(20)
    total_files = sum(s.get("file_count", 0) for s in sessions)

    # Get verification status
    collection_map = {
        "purchase_order": "purchase_orders",
        "expense": "expenses",
        "branch_transfer": "branch_transfer_orders",
    }
    verification = {}
    if record_type in collection_map:
        coll = getattr(db, collection_map[record_type])
        doc = await coll.find_one({"id": record_id}, {"_id": 0,
            "verified": 1, "verified_by_name": 1, "verified_at": 1,
            "verification_status": 1, "has_discrepancy": 1, "discrepancy": 1
        })
        if doc:
            verification = {
                "verified": doc.get("verified", False),
                "verified_by_name": doc.get("verified_by_name"),
                "verified_at": doc.get("verified_at"),
                "verification_status": doc.get("verification_status"),
                "has_discrepancy": doc.get("has_discrepancy", False),
                "discrepancy": doc.get("discrepancy"),
            }

    return {
        "record_summary": view_doc.get("record_summary", {}),
        "record_type": record_type,
        "record_id": record_id,
        "sessions": sessions,
        "total_files": total_files,
        "verification": verification,
        "expires_at": expires_at,
    }


@router.get("/file/{record_type}/{record_id}/{file_id}")
async def serve_file(
    record_type: str,
    record_id: str,
    file_id: str,
):
    """
    Serve an uploaded file. No auth required — UUID file IDs are unguessable
    (128-bit random, same security model as S3/R2 pre-signed URLs).
    """
    session = await db.upload_sessions.find_one(
        {"record_type": record_type, "record_id": record_id, "files.id": file_id},
        {"_id": 0, "files": 1}
    )
    if not session:
        raise HTTPException(status_code=404, detail="File not found")

    file_meta = next((f for f in session.get("files", []) if f["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    filepath = Path(file_meta.get("stored_path", ""))
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File data not found on server")

    media_type = file_meta.get("content_type", "image/jpeg")
    return FileResponse(path=str(filepath), media_type=media_type, filename=file_meta.get("filename", "file"))
