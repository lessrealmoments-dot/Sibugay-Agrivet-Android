"""
Supplier management routes — branch-specific.
Each branch maintains its own supplier directory.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("")
async def list_suppliers(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
):
    """List active suppliers, filtered by branch when provided."""
    query = {"active": True}
    if branch_id:
        # Show suppliers for this branch + global suppliers (no branch_id)
        query["$or"] = [
            {"branch_id": branch_id},
            {"branch_id": ""},
            {"branch_id": {"$exists": False}},
        ]
    suppliers = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(500)
    return suppliers


@router.post("")
async def create_supplier(data: dict, user=Depends(get_current_user)):
    """Create a new supplier, optionally scoped to a branch."""
    check_perm(user, "suppliers", "create")
    supplier = {
        "id": new_id(),
        "name": data["name"],
        "branch_id": data.get("branch_id", ""),
        "contact_person": data.get("contact_person", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "notes": data.get("notes", ""),
        "payment_terms": data.get("payment_terms", "COD"),
        "tax_id": data.get("tax_id", ""),
        "active": True,
        "created_at": now_iso(),
    }
    await db.suppliers.insert_one(supplier)
    del supplier["_id"]
    return supplier


@router.get("/search")
async def search_suppliers(
    q: str = "",
    branch_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Search suppliers by name, filtered by branch."""
    if not q:
        return []
    query = {
        "active": True,
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"contact_person": {"$regex": q, "$options": "i"}},
        ]
    }
    if branch_id:
        query = {"$and": [
            query,
            {"$or": [
                {"branch_id": branch_id},
                {"branch_id": ""},
                {"branch_id": {"$exists": False}},
            ]}
        ]}
    suppliers = await db.suppliers.find(query, {"_id": 0}).limit(20).to_list(20)
    return suppliers


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, user=Depends(get_current_user)):
    """Get supplier details."""
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.put("/{supplier_id}")
async def update_supplier(supplier_id: str, data: dict, user=Depends(get_current_user)):
    """Update supplier details."""
    check_perm(user, "suppliers", "edit")
    allowed = ["name", "contact_person", "phone", "email", "address", "notes",
               "payment_terms", "tax_id", "branch_id"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    await db.suppliers.update_one({"id": supplier_id}, {"$set": update})
    return await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str, user=Depends(get_current_user)):
    """Soft delete a supplier."""
    check_perm(user, "suppliers", "delete")
    await db.suppliers.update_one({"id": supplier_id}, {"$set": {"active": False}})
    return {"message": "Supplier deleted"}
