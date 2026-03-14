"""
Document Lookup routes.
Generates unique document codes for printed receipts and provides
PIN-protected lookup for scanning QR codes or entering codes manually.
"""
from fastapi import APIRouter, HTTPException, Depends
from config import db
from utils import get_current_user, now_iso, new_id
import string, secrets

router = APIRouter(prefix="/doc", tags=["Document Lookup"])


def _generate_doc_code(length=8):
    """Generate a unique alphanumeric code (uppercase + digits, no ambiguous chars)."""
    alphabet = string.ascii_uppercase.replace('O', '').replace('I', '') + string.digits.replace('0', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def _ensure_unique_code():
    """Generate a code and ensure it doesn't already exist."""
    for _ in range(10):
        code = _generate_doc_code()
        existing = await db.doc_codes.find_one({"code": code}, {"_id": 0, "code": 1})
        if not existing:
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique code")


@router.post("/generate-code")
async def generate_doc_code(data: dict, user=Depends(get_current_user)):
    """
    Generate a unique document code for a document (invoice, PO, branch transfer).
    If one already exists, return it.
    Body: { doc_type: "invoice"|"purchase_order"|"branch_transfer", doc_id: "..." }
    """
    doc_type = data.get("doc_type", "")
    doc_id = data.get("doc_id", "")
    if not doc_type or not doc_id:
        raise HTTPException(status_code=400, detail="doc_type and doc_id required")

    # Check if code already exists for this document
    existing = await db.doc_codes.find_one(
        {"doc_type": doc_type, "doc_id": doc_id}, {"_id": 0}
    )
    if existing:
        return {"code": existing["code"], "doc_type": doc_type, "doc_id": doc_id}

    code = await _ensure_unique_code()
    await db.doc_codes.insert_one({
        "id": new_id(),
        "code": code,
        "doc_type": doc_type,
        "doc_id": doc_id,
        "org_id": user.get("org_id", ""),
        "created_at": now_iso(),
        "created_by": user.get("id", ""),
    })

    # Also store the code on the document itself for quick access
    collection_map = {
        "invoice": "invoices",
        "purchase_order": "purchase_orders",
        "branch_transfer": "branch_transfer_orders",
    }
    coll_name = collection_map.get(doc_type)
    if coll_name:
        coll = db[coll_name]
        await coll.update_one({"id": doc_id}, {"$set": {"doc_code": code}})

    return {"code": code, "doc_type": doc_type, "doc_id": doc_id}


@router.post("/lookup")
async def lookup_document(data: dict):
    """
    PIN-protected document lookup by code.
    Body: { code: "ABC12345", pin: "521325" }
    Returns document details based on type.
    """
    code = (data.get("code") or "").strip().upper()
    pin = (data.get("pin") or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="Document code required")
    if not pin:
        raise HTTPException(status_code=400, detail="PIN required")

    # Verify PIN
    from routes.verify import _resolve_pin
    verifier = await _resolve_pin(pin)
    if not verifier:
        raise HTTPException(status_code=403, detail="Invalid PIN")

    # Find document code
    doc_ref = await db.doc_codes.find_one({"code": code}, {"_id": 0})
    if not doc_ref:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_type = doc_ref["doc_type"]
    doc_id = doc_ref["doc_id"]

    # Fetch document based on type
    if doc_type == "invoice":
        doc = await db.invoices.find_one({"id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Invoice not found")
        # Get payment history
        payments = doc.get("payments", [])
        # Get customer info
        customer = None
        if doc.get("customer_id"):
            customer = await db.customers.find_one(
                {"id": doc["customer_id"]}, {"_id": 0, "name": 1, "phone": 1, "address": 1, "balance": 1}
            )
        return {
            "doc_type": "invoice",
            "document": doc,
            "payments": payments,
            "customer": customer,
            "verifier": verifier.get("verifier_name", ""),
        }

    elif doc_type == "purchase_order":
        doc = await db.purchase_orders.find_one({"id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="PO not found")
        # Get attached receipts
        uploads = await db.upload_sessions.find(
            {"record_type": "purchase_order", "record_id": doc_id},
            {"_id": 0}
        ).to_list(20)
        files = []
        for u in uploads:
            session_files = await db.uploaded_files.find(
                {"session_id": u["id"]}, {"_id": 0}
            ).to_list(50)
            files.extend(session_files)
        return {
            "doc_type": "purchase_order",
            "document": doc,
            "attached_files": files,
            "verifier": verifier.get("verifier_name", ""),
        }

    elif doc_type == "branch_transfer":
        doc = await db.branch_transfer_orders.find_one({"id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Transfer not found")
        # Get branch names
        from_branch = await db.branches.find_one({"id": doc.get("from_branch_id")}, {"_id": 0, "name": 1})
        to_branch = await db.branches.find_one({"id": doc.get("to_branch_id")}, {"_id": 0, "name": 1})
        # Get attached receipts/DR photos
        uploads = await db.upload_sessions.find(
            {"record_type": "branch_transfer", "record_id": doc_id},
            {"_id": 0}
        ).to_list(20)
        files = []
        for u in uploads:
            session_files = await db.uploaded_files.find(
                {"session_id": u["id"]}, {"_id": 0}
            ).to_list(50)
            files.extend(session_files)
        return {
            "doc_type": "branch_transfer",
            "document": doc,
            "from_branch_name": from_branch.get("name", "") if from_branch else "",
            "to_branch_name": to_branch.get("name", "") if to_branch else "",
            "attached_files": files,
            "verifier": verifier.get("verifier_name", ""),
        }

    raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")


@router.get("/by-ref/{doc_type}/{doc_id}")
async def get_doc_code_by_ref(doc_type: str, doc_id: str, user=Depends(get_current_user)):
    """Get existing doc code for a document (no PIN needed, just auth)."""
    doc_ref = await db.doc_codes.find_one(
        {"doc_type": doc_type, "doc_id": doc_id}, {"_id": 0}
    )
    if doc_ref:
        return {"code": doc_ref["code"]}
    return {"code": None}
