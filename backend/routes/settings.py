"""
Settings routes: Invoice prefixes, terms options, system settings, PIN policies.
"""
from fastapi import APIRouter, Depends, HTTPException
from config import db
from utils import get_current_user, check_perm, now_iso

router = APIRouter(prefix="/settings", tags=["Settings"])


# ── PIN Policies ─────────────────────────────────────────────────────────────

@router.get("/pin-policies")
async def get_pin_policies(user=Depends(get_current_user)):
    """Get PIN policy configuration. Admin only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    from routes.verify import PIN_POLICY_ACTIONS, PIN_METHODS, _get_pin_policy
    custom = await _get_pin_policy()
    # Merge defaults with custom overrides
    policies = {}
    for action in PIN_POLICY_ACTIONS:
        policies[action["key"]] = custom.get(action["key"], action["defaults"])
    return {"actions": PIN_POLICY_ACTIONS, "methods": PIN_METHODS, "policies": policies}


@router.put("/pin-policies")
async def update_pin_policies(data: dict, user=Depends(get_current_user)):
    """Update PIN policies. Admin only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    from routes.verify import PIN_METHODS
    policies = data.get("policies", {})
    # Validate: each value must be a list of valid methods
    valid_methods = set(PIN_METHODS)
    for key, methods in policies.items():
        if not isinstance(methods, list):
            raise HTTPException(status_code=400, detail=f"Invalid policy for {key}")
        if not all(m in valid_methods for m in methods):
            raise HTTPException(status_code=400, detail=f"Invalid method in policy for {key}")
        if len(methods) == 0:
            raise HTTPException(status_code=400, detail=f"At least one PIN method required for {key}")
    await db.system_settings.update_one(
        {"key": "pin_policies"},
        {"$set": {"key": "pin_policies", "policies": policies, "updated_at": now_iso(), "updated_by": user["id"]}},
        upsert=True
    )
    return {"message": "PIN policies updated", "policies": policies}


# ── Legacy TOTP Controls (kept for backward compatibility) ───────────────────

# All sensitive actions that can be protected by TOTP
TOTP_PROTECTED_ACTIONS = [
    {"key": "inventory_adjust",    "label": "Direct Inventory Correction",   "module": "Inventory"},
    {"key": "close_day",           "label": "Close Day (Z-Report)",           "module": "Daily Operations"},
    {"key": "invoice_edit",        "label": "Edit Posted Invoice",            "module": "Sales"},
    {"key": "invoice_void",        "label": "Void Invoice",                   "module": "Sales"},
    {"key": "product_delete",      "label": "Delete Product",                 "module": "Products"},
    {"key": "price_override",      "label": "Override Branch Price",          "module": "Products"},
    {"key": "reopen_po",           "label": "Reopen Purchase Order",          "module": "Purchase Orders"},
    {"key": "manage_users",        "label": "Create / Edit / Delete Users",   "module": "Settings"},
    {"key": "manage_permissions",  "label": "Manage User Permissions",        "module": "Settings"},
]

DEFAULT_TOTP_ACTIONS = ["inventory_adjust", "close_day"]


@router.get("/totp-controls")
async def get_totp_controls(user=Depends(get_current_user)):
    """Get which sensitive actions are protected by TOTP."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    doc = await db.system_settings.find_one({"key": "totp_controls"}, {"_id": 0})
    enabled = doc.get("enabled_actions", DEFAULT_TOTP_ACTIONS) if doc else DEFAULT_TOTP_ACTIONS
    return {"actions": TOTP_PROTECTED_ACTIONS, "enabled_actions": enabled}


@router.put("/totp-controls")
async def update_totp_controls(data: dict, user=Depends(get_current_user)):
    """Update which actions require TOTP verification."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    enabled = data.get("enabled_actions", [])
    await db.system_settings.update_one(
        {"key": "totp_controls"},
        {"$set": {"key": "totp_controls", "enabled_actions": enabled, "updated_at": now_iso()}},
        upsert=True
    )
    return {"message": "TOTP controls updated", "enabled_actions": enabled}
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


# ── TOTP Controls ────────────────────────────────────────────────────────────

@router.get("/totp-controls")
async def get_totp_controls(user=Depends(get_current_user)):
    """Get which sensitive actions are protected by TOTP."""
    from fastapi import HTTPException
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    doc = await db.system_settings.find_one({"key": "totp_controls"}, {"_id": 0})
    enabled = doc.get("enabled_actions", DEFAULT_TOTP_ACTIONS) if doc else DEFAULT_TOTP_ACTIONS
    return {"actions": TOTP_PROTECTED_ACTIONS, "enabled_actions": enabled}


@router.put("/totp-controls")
async def update_totp_controls(data: dict, user=Depends(get_current_user)):
    """Update which actions require TOTP verification."""
    from fastapi import HTTPException
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    enabled = data.get("enabled_actions", [])
    await db.system_settings.update_one(
        {"key": "totp_controls"},
        {"$set": {"key": "totp_controls", "enabled_actions": enabled, "updated_at": now_iso()}},
        upsert=True
    )
    return {"message": "TOTP controls updated", "enabled_actions": enabled}
