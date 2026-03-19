"""
AgriDocs — Business Document Cloud
Upload, organize, search, and track compliance documents per branch.
Supports multi-month tagging, expiry tracking, and QR phone uploads.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pathlib import Path
import secrets
from config import db, get_org_context
from utils import get_current_user, now_iso, new_id
from utils.r2_storage import upload_file, get_presigned_url, delete_file

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".doc", ".docx", ".xls", ".xlsx"}

# ─────────────────────────────────────────────────────────────────────────────
#  Category Definitions
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = {
    "business_registration": {
        "label": "Business Registration",
        "icon": "building",
        "sub_categories": {
            "dti_certificate": {"label": "DTI Certificate", "period_type": "validity"},
            "sec_certificate": {"label": "SEC Certificate of Incorporation", "period_type": "one_time"},
            "articles_of_incorporation": {"label": "Articles of Incorporation / Partnership", "period_type": "one_time"},
            "business_name_registration": {"label": "Business Name Registration", "period_type": "validity"},
            "gis": {"label": "General Information Sheet (GIS)", "period_type": "annual"},
        },
    },
    "lgu_permits": {
        "label": "LGU / Local Permits",
        "icon": "landmark",
        "sub_categories": {
            "mayors_permit": {"label": "Mayor's / Business Permit", "period_type": "annual"},
            "barangay_clearance": {"label": "Barangay Clearance", "period_type": "annual"},
            "zoning_clearance": {"label": "Zoning Clearance", "period_type": "one_time"},
            "occupancy_permit": {"label": "Occupancy Permit", "period_type": "one_time"},
            "building_permit": {"label": "Building Permit", "period_type": "one_time"},
            "fsic": {"label": "Fire Safety Inspection Certificate (FSIC)", "period_type": "annual"},
            "sanitary_permit": {"label": "Sanitary Permit", "period_type": "annual"},
        },
    },
    "bir": {
        "label": "BIR",
        "icon": "receipt",
        "sub_categories": {
            "form_2303": {"label": "BIR Form 2303 (COR)", "period_type": "one_time"},
            "atp": {"label": "Authority to Print (ATP) / POS Accreditation", "period_type": "validity"},
            "books_of_accounts": {"label": "Registered Books of Accounts", "period_type": "one_time"},
            "sample_receipts": {"label": "Sample Official Receipts / Sales Invoices", "period_type": "one_time"},
            "notice_to_issue": {"label": "Notice to Issue Receipt/Invoice", "period_type": "one_time"},
            "bir_permit_pos": {"label": "BIR Permit to Use (POS)", "period_type": "validity"},
            "1601c": {"label": "1601-C (Withholding Tax - Compensation)", "period_type": "monthly"},
            "0619e": {"label": "0619-E (Expanded Withholding Tax)", "period_type": "monthly"},
            "2550m": {"label": "2550M (Monthly VAT)", "period_type": "monthly"},
            "2550q": {"label": "2550Q (Quarterly VAT)", "period_type": "quarterly"},
            "2551q": {"label": "2551Q (Percentage Tax)", "period_type": "quarterly"},
            "1701q": {"label": "1701Q / 1702Q (Quarterly Income Tax)", "period_type": "quarterly"},
            "annual_itr": {"label": "1701 / 1702 (Annual Income Tax Return)", "period_type": "annual"},
            "annual_registration": {"label": "Annual Registration (0605)", "period_type": "annual"},
            "alphalist": {"label": "Alphalist / 2316", "period_type": "annual"},
        },
    },
    "employer_compliance": {
        "label": "Employer & Employee Compliance",
        "icon": "users",
        "sub_categories": {
            "sss_registration": {"label": "SSS Employer Registration", "period_type": "one_time"},
            "philhealth_registration": {"label": "PhilHealth Employer Registration", "period_type": "one_time"},
            "pagibig_registration": {"label": "Pag-IBIG Employer Registration", "period_type": "one_time"},
            "sss_contributions": {"label": "SSS Contributions", "period_type": "monthly"},
            "philhealth_contributions": {"label": "PhilHealth RF-1 / Remittance", "period_type": "monthly"},
            "pagibig_contributions": {"label": "Pag-IBIG Remittance", "period_type": "monthly"},
            "employee_contracts": {"label": "Employee Contracts", "period_type": "one_time"},
            "payroll_records": {"label": "Payroll Records", "period_type": "monthly"},
            "id_copies_201": {"label": "ID Copies / 201 Files", "period_type": "one_time"},
        },
    },
    "agrivet": {
        "label": "Industry-Specific (Agrivet)",
        "icon": "leaf",
        "audit_sensitive": True,
        "sub_categories": {
            "bai_license": {"label": "BAI License to Operate", "period_type": "annual", "audit_sensitive": True},
            "fda_lto": {"label": "FDA License to Operate", "period_type": "validity", "audit_sensitive": True},
            "fda_cpr": {"label": "FDA Certificate of Product Registration (CPR)", "period_type": "validity", "audit_sensitive": True},
            "fpa_handler_license": {"label": "FPA Handler License", "period_type": "validity", "audit_sensitive": True},
            "fpa_safety_dispenser": {"label": "FPA Safety Dispenser Accreditation", "period_type": "validity", "audit_sensitive": True},
            "denr_clearance": {"label": "DENR Clearance / ECC", "period_type": "validity"},
            "product_registration": {"label": "Product Registration Certificates", "period_type": "validity", "audit_sensitive": True},
        },
    },
    "other": {
        "label": "Other / Miscellaneous",
        "icon": "folder",
        "sub_categories": {
            "contracts_agreements": {"label": "Contracts & Agreements", "period_type": "validity"},
            "financial_reports": {"label": "Financial Reports", "period_type": "annual"},
            "bank_statements": {"label": "Bank Statements", "period_type": "monthly"},
            "loan_documents": {"label": "Loan Documents", "period_type": "one_time"},
            "miscellaneous": {"label": "Miscellaneous", "period_type": "one_time"},
        },
    },
}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _get_org_id() -> str:
    return get_org_context() or "default"


# ─────────────────────────────────────────────────────────────────────────────
#  Get categories
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(user=Depends(get_current_user)):
    """Return all document categories and sub-categories."""
    return CATEGORIES


# ─────────────────────────────────────────────────────────────────────────────
#  Upload document
# ─────────────────────────────────────────────────────────────────────────────

@router.post("")
async def upload_document(
    files: List[UploadFile] = File(...),
    name: str = Form(""),
    description: str = Form(""),
    category: str = Form(...),
    sub_category: str = Form(...),
    branch_id: str = Form(""),
    year: int = Form(0),
    coverage_months: str = Form(""),  # comma-separated: "1,2,3"
    coverage_quarter: str = Form(""),
    valid_from: str = Form(""),
    valid_until: str = Form(""),
    tags: str = Form(""),  # comma-separated
    employee_name: str = Form(""),
    user=Depends(get_current_user),
):
    """Upload a document with metadata."""
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    cat_def = CATEGORIES[category]
    if sub_category not in cat_def["sub_categories"]:
        raise HTTPException(status_code=400, detail=f"Invalid sub_category: {sub_category}")

    sub_def = cat_def["sub_categories"][sub_category]
    org_id = _get_org_id()

    # Parse coverage months
    months = []
    if coverage_months:
        months = [int(m.strip()) for m in coverage_months.split(",") if m.strip().isdigit()]

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Auto-generate name if not provided
    if not name:
        name = sub_def["label"]
        if year:
            name += f" {year}"
        if months:
            month_strs = [MONTH_NAMES[m - 1] for m in months if 1 <= m <= 12]
            if len(month_strs) <= 3:
                name += f" ({', '.join(month_strs)})"
            else:
                name += f" ({month_strs[0]}-{month_strs[-1]})"

    doc_id = new_id()

    # Upload files to R2
    saved_files = []
    for file in files:
        file_id = new_id()
        ext = Path(file.filename).suffix.lower() if file.filename else ".pdf"
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".pdf"
        filename = f"{file_id}{ext}"
        content_type = file.content_type or "application/octet-stream"
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds 25MB limit")

        r2_result = await upload_file(org_id, "business_documents", doc_id, filename, content, content_type)
        saved_files.append({
            "id": file_id,
            "filename": file.filename or filename,
            "r2_key": r2_result["key"],
            "content_type": content_type,
            "size": len(content),
            "uploaded_at": now_iso(),
        })

    document = {
        "id": doc_id,
        "name": name,
        "description": description,
        "category": category,
        "category_label": cat_def["label"],
        "sub_category": sub_category,
        "sub_category_label": sub_def["label"],
        "period_type": sub_def.get("period_type", "one_time"),
        "audit_sensitive": sub_def.get("audit_sensitive", False) or cat_def.get("audit_sensitive", False),
        "branch_id": branch_id,
        "year": year or datetime.now(timezone.utc).year,
        "coverage_months": months,
        "coverage_quarter": coverage_quarter,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "tags": tag_list,
        "employee_name": employee_name,
        "files": saved_files,
        "file_count": len(saved_files),
        "uploaded_by_id": user["id"],
        "uploaded_by_name": user.get("full_name", user.get("username", "")),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    await db.business_documents.insert_one(document)
    del document["_id"]
    return document


# ─────────────────────────────────────────────────────────────────────────────
#  List / Browse documents
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_documents(
    user=Depends(get_current_user),
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
    branch_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    """List documents with filtering."""
    query = {}
    if category:
        query["category"] = category
    if sub_category:
        query["sub_category"] = sub_category
    if branch_id:
        query["branch_id"] = branch_id
    if year:
        query["year"] = year
    if month:
        query["coverage_months"] = month
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
            {"sub_category_label": {"$regex": search, "$options": "i"}},
            {"employee_name": {"$regex": search, "$options": "i"}},
        ]

    total = await db.business_documents.count_documents(query)
    docs = await db.business_documents.find(query, {"_id": 0}).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(limit)

    return {"documents": docs, "total": total}


# ─────────────────────────────────────────────────────────────────────────────
#  Compliance summary — what's filed, what's missing, what's expiring
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/compliance/summary")
async def compliance_summary(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    year: Optional[int] = None,
):
    """Get compliance overview: filed/missing months, expiring permits."""
    target_year = year or datetime.now(timezone.utc).year
    query = {"year": target_year}
    if branch_id:
        query["branch_id"] = branch_id

    docs = await db.business_documents.find(query, {"_id": 0, "category": 1, "sub_category": 1, "coverage_months": 1, "valid_until": 1, "period_type": 1}).to_list(5000)

    monthly_coverage = {}
    expiring = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for doc in docs:
        sub = doc.get("sub_category", "")
        period = doc.get("period_type", "")

        if period == "monthly":
            if sub not in monthly_coverage:
                monthly_coverage[sub] = set()
            for m in doc.get("coverage_months", []):
                monthly_coverage[sub].add(m)

        valid_until = doc.get("valid_until", "")
        if valid_until and valid_until >= today:
            days_left = (datetime.fromisoformat(valid_until) - datetime.fromisoformat(today)).days
            if days_left <= 60:
                expiring.append({
                    "sub_category": sub,
                    "sub_category_label": doc.get("sub_category_label", sub),
                    "valid_until": valid_until,
                    "days_left": days_left,
                })

    expired_query = {"valid_until": {"$lt": today, "$ne": ""}, "period_type": {"$in": ["validity", "annual"]}}
    if branch_id:
        expired_query["branch_id"] = branch_id
    expired_docs = await db.business_documents.find(expired_query, {"_id": 0, "sub_category": 1, "sub_category_label": 1, "valid_until": 1}).to_list(100)
    expired = [{"sub_category": d["sub_category"], "sub_category_label": d.get("sub_category_label", ""), "valid_until": d["valid_until"]} for d in expired_docs]

    return {
        "year": target_year,
        "monthly_coverage": {k: sorted(list(v)) for k, v in monthly_coverage.items()},
        "expiring_soon": expiring,
        "expired": expired,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  QR Upload Token — for phone uploads
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/qr-upload-token")
async def generate_qr_upload_token(data: dict, user=Depends(get_current_user)):
    """Generate a temporary token for phone-based document upload."""
    category = data.get("category", "")
    sub_category = data.get("sub_category", "")
    branch_id = data.get("branch_id", "")
    year = data.get("year", datetime.now(timezone.utc).year)
    coverage_months = data.get("coverage_months", [])

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    cat_label = CATEGORIES.get(category, {}).get("label", category)
    sub_label = CATEGORIES.get(category, {}).get("sub_categories", {}).get(sub_category, {}).get("label", sub_category)

    doc = {
        "id": new_id(),
        "token": token,
        "token_type": "doc_upload",
        "token_expires_at": expires_at,
        "category": category,
        "sub_category": sub_category,
        "category_label": cat_label,
        "sub_category_label": sub_label,
        "branch_id": branch_id,
        "year": year,
        "coverage_months": coverage_months,
        "org_id": _get_org_id(),
        "created_by_id": user["id"],
        "created_by_name": user.get("full_name", user.get("username", "")),
        "created_at": now_iso(),
    }
    await db.doc_upload_tokens.insert_one(doc)
    return {"token": token, "expires_at": expires_at, "category_label": cat_label, "sub_category_label": sub_label}


# ─────────────────────────────────────────────────────────────────────────────
#  Public: preview QR upload (no auth)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/qr-upload/{token}")
async def qr_upload_preview(token: str):
    """Public — get upload context from token."""
    session = await db.doc_upload_tokens.find_one({"token": token, "token_type": "doc_upload"}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Upload link not found")

    expires_at = session.get("token_expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="Upload link has expired (15 min). Generate a new QR code.")
        except ValueError:
            pass

    return {
        "category_label": session.get("category_label", ""),
        "sub_category_label": session.get("sub_category_label", ""),
        "branch_id": session.get("branch_id", ""),
        "year": session.get("year", ""),
        "coverage_months": session.get("coverage_months", []),
        "expired": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Public: upload via QR token (no auth)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/qr-upload/{token}")
async def qr_upload_files(
    token: str,
    files: List[UploadFile] = File(...),
):
    """Public — upload files using QR token."""
    session = await db.doc_upload_tokens.find_one({"token": token, "token_type": "doc_upload"}, {"_id": 0})
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

    org_id = session.get("org_id", "default")
    category = session.get("category", "other")
    sub_category = session.get("sub_category", "miscellaneous")
    branch_id = session.get("branch_id", "")
    year = session.get("year", datetime.now(timezone.utc).year)
    coverage_months = session.get("coverage_months", [])

    cat_def = CATEGORIES.get(category, CATEGORIES["other"])
    sub_def = cat_def["sub_categories"].get(sub_category, {"label": sub_category, "period_type": "one_time"})

    doc_id = new_id()
    saved_files = []
    for file in files:
        file_id = new_id()
        ext = Path(file.filename).suffix.lower() if file.filename else ".pdf"
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".pdf"
        filename = f"{file_id}{ext}"
        content_type = file.content_type or "application/octet-stream"
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            continue

        r2_result = await upload_file(org_id, "business_documents", doc_id, filename, content, content_type)
        saved_files.append({
            "id": file_id,
            "filename": file.filename or filename,
            "r2_key": r2_result["key"],
            "content_type": content_type,
            "size": len(content),
            "uploaded_at": now_iso(),
        })

    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid files uploaded")

    name = sub_def["label"]
    if year:
        name += f" {year}"
    if coverage_months:
        month_strs = [MONTH_NAMES[m - 1] for m in coverage_months if 1 <= m <= 12]
        if len(month_strs) <= 3:
            name += f" ({', '.join(month_strs)})"
        else:
            name += f" ({month_strs[0]}-{month_strs[-1]})"

    document = {
        "id": doc_id,
        "name": name,
        "description": "Uploaded via phone (QR)",
        "category": category,
        "category_label": cat_def["label"],
        "sub_category": sub_category,
        "sub_category_label": sub_def["label"],
        "period_type": sub_def.get("period_type", "one_time"),
        "audit_sensitive": sub_def.get("audit_sensitive", False) or cat_def.get("audit_sensitive", False),
        "branch_id": branch_id,
        "year": year,
        "coverage_months": coverage_months,
        "coverage_quarter": "",
        "valid_from": "",
        "valid_until": "",
        "tags": ["qr-upload"],
        "employee_name": "",
        "files": saved_files,
        "file_count": len(saved_files),
        "uploaded_by_id": session.get("created_by_id", ""),
        "uploaded_by_name": session.get("created_by_name", "Phone Upload"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    await db.business_documents.insert_one(document)
    await db.doc_upload_tokens.update_one({"token": token}, {"$set": {"token_expires_at": now_iso()}})

    return {"uploaded": len(saved_files), "document_id": doc_id, "document_name": name}


# ─────────────────────────────────────────────────────────────────────────────
#  Get single document with pre-signed URLs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{doc_id}")
async def get_document(doc_id: str, user=Depends(get_current_user)):
    """Get a document with pre-signed file URLs."""
    doc = await db.business_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    for f in doc.get("files", []):
        r2_key = f.get("r2_key", "")
        if r2_key:
            f["url"] = await get_presigned_url(r2_key, expires_in=3600)

    return doc


# ─────────────────────────────────────────────────────────────────────────────
#  Update document metadata
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{doc_id}")
async def update_document(doc_id: str, data: dict, user=Depends(get_current_user)):
    """Update document metadata (name, tags, coverage months, validity, etc.)."""
    doc = await db.business_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    allowed_fields = {
        "name", "description", "coverage_months", "coverage_quarter",
        "year", "valid_from", "valid_until", "tags", "employee_name",
        "category", "sub_category", "branch_id",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    updates["updated_at"] = now_iso()

    # If category/sub_category changed, update labels
    if "category" in updates and "sub_category" in updates:
        cat = updates["category"]
        sub = updates["sub_category"]
        if cat in CATEGORIES and sub in CATEGORIES[cat]["sub_categories"]:
            updates["category_label"] = CATEGORIES[cat]["label"]
            updates["sub_category_label"] = CATEGORIES[cat]["sub_categories"][sub]["label"]
            updates["period_type"] = CATEGORIES[cat]["sub_categories"][sub].get("period_type", "one_time")

    await db.business_documents.update_one({"id": doc_id}, {"$set": updates})
    return {"message": "Document updated"}


# ─────────────────────────────────────────────────────────────────────────────
#  Delete document
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user=Depends(get_current_user)):
    """Delete a document and its files from R2."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    doc = await db.business_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete files from R2
    for f in doc.get("files", []):
        r2_key = f.get("r2_key", "")
        if r2_key:
            try:
                await delete_file(r2_key)
            except Exception:
                pass

    await db.business_documents.delete_one({"id": doc_id})
    return {"message": "Document deleted"}


# ─────────────────────────────────────────────────────────────────────────────
#  Add files to existing document
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{doc_id}/files")
async def add_files_to_document(
    doc_id: str,
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    """Add more files to an existing document."""
    doc = await db.business_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    org_id = _get_org_id()
    saved_files = []
    for file in files:
        file_id = new_id()
        ext = Path(file.filename).suffix.lower() if file.filename else ".pdf"
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".pdf"
        filename = f"{file_id}{ext}"
        content_type = file.content_type or "application/octet-stream"
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds 25MB limit")

        r2_result = await upload_file(org_id, "business_documents", doc_id, filename, content, content_type)
        saved_files.append({
            "id": file_id,
            "filename": file.filename or filename,
            "r2_key": r2_result["key"],
            "content_type": content_type,
            "size": len(content),
            "uploaded_at": now_iso(),
        })

    await db.business_documents.update_one(
        {"id": doc_id},
        {"$push": {"files": {"$each": saved_files}}, "$inc": {"file_count": len(saved_files)}, "$set": {"updated_at": now_iso()}}
    )
    return {"uploaded": len(saved_files)}


# ─────────────────────────────────────────────────────────────────────────────
#  Remove file from document
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{doc_id}/files/{file_id}")
async def remove_file_from_document(doc_id: str, file_id: str, user=Depends(get_current_user)):
    """Remove a single file from a document."""
    doc = await db.business_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_meta = next((f for f in doc.get("files", []) if f["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    r2_key = file_meta.get("r2_key", "")
    if r2_key:
        try:
            await delete_file(r2_key)
        except Exception:
            pass

    await db.business_documents.update_one(
        {"id": doc_id},
        {"$pull": {"files": {"id": file_id}}, "$inc": {"file_count": -1}, "$set": {"updated_at": now_iso()}}
    )
    return {"message": "File removed"}
