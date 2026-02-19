"""
Settings routes: Invoice prefixes, terms options, and system settings.
"""
from fastapi import APIRouter, Depends
from config import db
from utils import get_current_user, check_perm, now_iso

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/invoice-prefixes")
async def get_invoice_prefixes(user=Depends(get_current_user)):
    """Get invoice prefix settings."""
    s = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    return s.get("value", {}) if s else {
        "sales_invoice": "SI",
        "purchase_order": "PO",
        "service_invoice": "SVC",
        "cash_advance": "CA",
        "interest_charge": "INT",
        "penalty_charge": "PEN",
    }


@router.put("/invoice-prefixes")
async def update_invoice_prefixes(data: dict, user=Depends(get_current_user)):
    """Update invoice prefix settings."""
    check_perm(user, "settings", "edit")
    await db.settings.update_one(
        {"key": "invoice_prefixes"},
        {"$set": {"key": "invoice_prefixes", "value": data, "updated_at": now_iso()}},
        upsert=True
    )
    return data


@router.get("/terms-options")
async def get_terms_options(user=Depends(get_current_user)):
    """Get available payment terms options."""
    return [
        {"key": "COD", "label": "Cash on Delivery", "days": 0},
        {"key": "NET7", "label": "Net 7 Days", "days": 7},
        {"key": "NET15", "label": "Net 15 Days", "days": 15},
        {"key": "NET30", "label": "Net 30 Days", "days": 30},
        {"key": "NET45", "label": "Net 45 Days", "days": 45},
        {"key": "NET60", "label": "Net 60 Days", "days": 60},
        {"key": "NET90", "label": "Net 90 Days", "days": 90},
    ]
