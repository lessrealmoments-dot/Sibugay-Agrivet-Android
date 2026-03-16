"""
Price scheme management routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/price-schemes", tags=["Price Schemes"])


@router.get("")
async def list_price_schemes(user=Depends(get_current_user)):
    """List all active price schemes."""
    schemes = await db.price_schemes.find({"active": True}, {"_id": 0}).to_list(50)
    return schemes


@router.post("")
async def create_price_scheme(data: dict, user=Depends(get_current_user)):
    """Create a new price scheme."""
    check_perm(user, "price_schemes", "create")

    key = data.get("key", data["name"].lower().replace(" ", "_"))
    # Prevent duplicate keys
    existing = await db.price_schemes.find_one({"key": key, "active": True}, {"_id": 0, "name": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"A price scheme with key \"{key}\" already exists.")

    scheme = {
        "id": new_id(),
        "name": data["name"],
        "key": key,
        "description": data.get("description", ""),
        "calculation_method": data.get("calculation_method", "fixed"),
        "calculation_value": float(data.get("calculation_value", 0)),
        "base_scheme": data.get("base_scheme", "cost_price"),
        "active": True,
        "created_at": now_iso(),
    }
    await db.price_schemes.insert_one(scheme)
    del scheme["_id"]
    return scheme


@router.put("/{scheme_id}")
async def update_price_scheme(scheme_id: str, data: dict, user=Depends(get_current_user)):
    """Update a price scheme."""
    check_perm(user, "price_schemes", "edit")
    
    allowed = ["name", "description", "calculation_method", "calculation_value", "base_scheme"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    
    await db.price_schemes.update_one({"id": scheme_id}, {"$set": update})
    scheme = await db.price_schemes.find_one({"id": scheme_id}, {"_id": 0})
    return scheme


@router.delete("/{scheme_id}")
async def delete_price_scheme(scheme_id: str, user=Depends(get_current_user)):
    """Soft delete a price scheme."""
    check_perm(user, "price_schemes", "delete")
    await db.price_schemes.update_one({"id": scheme_id}, {"$set": {"active": False}})
    return {"message": "Price scheme deleted"}
