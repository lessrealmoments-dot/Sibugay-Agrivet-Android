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



@router.post("/import-from-branch")
async def import_supplier_from_branch(data: dict, user=Depends(get_current_user)):
    """
    Import a supplier from another branch along with their product pricing data.
    The supplier is copied to the target branch, and all product_vendors records
    (last prices per product) are imported as reference for future POs.
    """
    check_perm(user, "suppliers", "create")

    source_branch_id = data.get("source_branch_id")
    target_branch_id = data.get("target_branch_id")
    supplier_id = data.get("supplier_id")

    if not source_branch_id or not target_branch_id or not supplier_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="source_branch_id, target_branch_id, and supplier_id are required")

    supplier = await db.suppliers.find_one({"id": supplier_id, "active": True}, {"_id": 0})
    if not supplier:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Check if supplier name already exists at target branch
    existing = await db.suppliers.find_one({
        "name": supplier["name"], "branch_id": target_branch_id, "active": True
    }, {"_id": 0})
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Supplier '{supplier['name']}' already exists at this branch")

    # Create new supplier record for target branch
    new_supplier = {
        "id": new_id(),
        "name": supplier["name"],
        "branch_id": target_branch_id,
        "contact_person": supplier.get("contact_person", ""),
        "phone": supplier.get("phone", ""),
        "email": supplier.get("email", ""),
        "address": supplier.get("address", ""),
        "notes": supplier.get("notes", ""),
        "payment_terms": supplier.get("payment_terms", "COD"),
        "tax_id": supplier.get("tax_id", ""),
        "imported_from_branch_id": source_branch_id,
        "imported_from_supplier_id": supplier_id,
        "active": True,
        "created_at": now_iso(),
    }
    await db.suppliers.insert_one(new_supplier)
    del new_supplier["_id"]

    # Copy product_vendors data from source branch for this supplier
    source_vendors = await db.product_vendors.find({
        "branch_id": source_branch_id,
        "$or": [
            {"vendor_name": supplier["name"]},
            {"supplier_id": supplier_id},
        ]
    }, {"_id": 0}).to_list(5000)

    imported_count = 0
    for pv in source_vendors:
        await db.product_vendors.update_one(
            {"product_id": pv["product_id"], "vendor_name": supplier["name"], "branch_id": target_branch_id},
            {"$setOnInsert": {
                "id": new_id(),
                "product_id": pv["product_id"],
                "branch_id": target_branch_id,
                "supplier_id": new_supplier["id"],
                "vendor_name": supplier["name"],
                "vendor_contact": pv.get("vendor_contact", ""),
                "last_price": pv.get("last_price", 0),
                "last_order_date": pv.get("last_order_date", ""),
                "is_preferred": False,
                "imported_from_branch_id": source_branch_id,
                "created_at": now_iso(),
            }},
            upsert=True,
        )
        imported_count += 1

    return {
        "supplier": new_supplier,
        "vendor_prices_imported": imported_count,
        "message": f"Imported '{supplier['name']}' with {imported_count} product price(s) from source branch",
    }


@router.get("/available-for-import")
async def get_suppliers_available_for_import(
    target_branch_id: str = "",
    user=Depends(get_current_user),
):
    """
    Get suppliers from OTHER branches that can be imported to the target branch.
    Excludes suppliers whose name already exists at the target branch.
    """
    if not target_branch_id:
        return []

    # Get names of suppliers already at target branch
    existing_names = await db.suppliers.distinct(
        "name", {"branch_id": target_branch_id, "active": True}
    )

    # Get suppliers from other branches, excluding already-existing names
    query = {
        "active": True,
        "branch_id": {"$ne": target_branch_id, "$nin": ["", None]},
    }
    if existing_names:
        query["name"] = {"$nin": existing_names}

    candidates = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(500)

    # Enrich with branch name and product count
    result = []
    branch_cache = {}
    for s in candidates:
        bid = s.get("branch_id", "")
        if bid and bid not in branch_cache:
            branch_doc = await db.branches.find_one({"id": bid}, {"_id": 0, "name": 1})
            branch_cache[bid] = branch_doc.get("name", bid) if branch_doc else bid
        product_count = await db.product_vendors.count_documents({
            "branch_id": bid,
            "$or": [{"vendor_name": s["name"]}, {"supplier_id": s["id"]}],
        })
        result.append({
            **s,
            "source_branch_name": branch_cache.get(bid, bid),
            "product_count": product_count,
        })

    return result
