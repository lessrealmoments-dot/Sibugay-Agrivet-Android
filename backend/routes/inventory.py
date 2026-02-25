"""
Inventory management routes: stock levels, adjustments, transfers.
Supports multi-branch data isolation.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id, log_movement,
    get_branch_filter, apply_branch_filter, ensure_branch_access, get_default_branch
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("")
async def list_inventory(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    search: Optional[str] = None,
    low_stock: Optional[bool] = None,
    include_repacks: Optional[bool] = True,
    sort_by: Optional[str] = "name",   # "name" | "type" | "grouped"
    skip: int = 0,
    limit: int = 50
):
    """List inventory with stock levels, including derived repack quantities."""
    # Base query - only get non-repack products for direct inventory
    base_match = {"active": True}
    if not include_repacks:
        base_match["is_repack"] = {"$ne": True}
    
    pipeline = [
        {"$match": base_match},
        {"$lookup": {
            "from": "inventory",
            "localField": "id",
            "foreignField": "product_id",
            "as": "stock_records"
        }},
    ]
    
    if branch_id:
        pipeline.append({"$addFields": {
            "stock_records": {
                "$filter": {
                    "input": "$stock_records",
                    "as": "s",
                    "cond": {"$eq": ["$$s.branch_id", branch_id]}
                }
            }
        }})
    
    pipeline.append({"$addFields": {
        "total_stock": {"$sum": "$stock_records.quantity"},
        "branch_stock": {
            "$arrayToObject": {
                "$map": {
                    "input": "$stock_records",
                    "as": "s",
                    "in": {"k": "$$s.branch_id", "v": "$$s.quantity"}
                }
            }
        }
    }})
    
    if search:
        pipeline.insert(1, {"$match": {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}}
        ]}})
    
    if low_stock:
        pipeline.append({"$match": {"total_stock": {"$lte": 10}}})
    
    pipeline.append({"$project": {"_id": 0, "stock_records": 0}})
    
    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db.products.aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0
    
    pipeline.extend([{"$skip": skip}, {"$limit": limit}])
    items = await db.products.aggregate(pipeline).to_list(limit)
    
    # For repacks, calculate derived stock from parent
    enriched_items = []
    for item in items:
        if item.get("is_repack") and item.get("parent_id"):
            # Get parent stock
            parent_inv = await db.inventory.find_one(
                {"product_id": item["parent_id"], "branch_id": branch_id} if branch_id 
                else {"product_id": item["parent_id"]},
                {"_id": 0}
            )
            parent_stock = parent_inv["quantity"] if parent_inv else 0
            units_per_parent = item.get("units_per_parent", 1)
            
            # Calculate derived stock
            item["total_stock"] = parent_stock * units_per_parent
            item["derived_from_parent"] = True
            item["parent_stock"] = parent_stock
            
            # Get parent name
            parent = await db.products.find_one(
                {"id": item["parent_id"]},
                {"_id": 0, "name": 1, "unit": 1}
            )
            item["parent_name"] = parent["name"] if parent else ""
            item["parent_unit"] = parent["unit"] if parent else ""
        enriched_items.append(item)
    
    return {"items": enriched_items, "total": total}


@router.post("/adjust")
async def adjust_inventory(data: dict, user=Depends(get_current_user)):
    """Adjust inventory quantity (add or subtract)."""
    check_perm(user, "inventory", "adjust")
    
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    quantity = float(data["quantity"])
    reason = data.get("reason", "Manual adjustment")
    
    # Check if this is a repack - cannot adjust repack inventory directly
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if product and product.get("is_repack"):
        raise HTTPException(
            status_code=400,
            detail="Cannot adjust repack inventory directly. Adjust the parent product instead. Repack stock is derived from parent."
        )
    
    existing = await db.inventory.find_one(
        {"product_id": product_id, "branch_id": branch_id},
        {"_id": 0}
    )
    
    if existing:
        new_qty = existing["quantity"] + quantity
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": {"quantity": new_qty, "updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(),
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity": quantity,
            "updated_at": now_iso()
        })
    
    log = {
        "id": new_id(),
        "product_id": product_id,
        "branch_id": branch_id,
        "quantity_change": quantity,
        "reason": reason,
        "user_id": user["id"],
        "created_at": now_iso()
    }
    await db.inventory_logs.insert_one(log)
    
    await log_movement(
        product_id, branch_id, "adjustment", quantity,
        log["id"], "ADJ", 0, user["id"],
        user.get("full_name", user["username"]), reason
    )
    
    return {
        "message": "Inventory adjusted",
        "new_quantity": (existing["quantity"] + quantity) if existing else quantity
    }


@router.post("/transfer")
async def transfer_inventory(data: dict, user=Depends(get_current_user)):
    """Transfer inventory between branches."""
    check_perm(user, "inventory", "transfer")
    
    product_id = data["product_id"]
    from_branch = data["from_branch_id"]
    to_branch = data["to_branch_id"]
    quantity = float(data["quantity"])
    
    source = await db.inventory.find_one(
        {"product_id": product_id, "branch_id": from_branch},
        {"_id": 0}
    )
    
    if not source or source["quantity"] < quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock in source branch")
    
    # Deduct from source
    await db.inventory.update_one(
        {"product_id": product_id, "branch_id": from_branch},
        {"$inc": {"quantity": -quantity}, "$set": {"updated_at": now_iso()}}
    )
    
    # Add to destination
    dest = await db.inventory.find_one(
        {"product_id": product_id, "branch_id": to_branch},
        {"_id": 0}
    )
    
    if dest:
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": to_branch},
            {"$inc": {"quantity": quantity}, "$set": {"updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(),
            "product_id": product_id,
            "branch_id": to_branch,
            "quantity": quantity,
            "updated_at": now_iso()
        })
    
    # Log the transfer
    log = {
        "id": new_id(),
        "type": "transfer",
        "product_id": product_id,
        "from_branch_id": from_branch,
        "to_branch_id": to_branch,
        "quantity": quantity,
        "user_id": user["id"],
        "created_at": now_iso()
    }
    await db.inventory_logs.insert_one(log)
    
    return {"message": "Transfer complete"}


@router.post("/set")
async def set_inventory(data: dict, user=Depends(get_current_user)):
    """Set inventory to a specific quantity."""
    check_perm(user, "inventory", "adjust")
    
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    quantity = float(data["quantity"])

    # Repack guard — repack stock is derived from parent; cannot be set directly
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if product and product.get("is_repack"):
        raise HTTPException(
            status_code=400,
            detail="Cannot set repack inventory directly. Adjust the parent product instead."
        )
    
    existing = await db.inventory.find_one(
        {"product_id": product_id, "branch_id": branch_id}
    )
    
    if existing:
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": {"quantity": quantity, "updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(),
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity": quantity,
            "updated_at": now_iso()
        })
    
    return {"message": "Inventory set", "quantity": quantity}


@router.post("/admin-adjust")
async def admin_adjust_inventory(data: dict, user=Depends(get_current_user)):
    """
    Admin inventory correction — sets stock to exact new_quantity to fix counting errors.
    Requires prior TOTP/password verification. Creates a full audit log.
    """
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    new_quantity = float(data["new_quantity"])
    reason = data.get("reason", "Admin correction")
    verified_by = data.get("verified_by", "")    # name of admin who verified
    auth_mode = data.get("auth_mode", "totp")    # "totp", "password", or "direct_admin"

    # Repack guard
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if product and product.get("is_repack"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Cannot adjust repack inventory directly. Adjust the parent product."
        )

    existing = await db.inventory.find_one(
        {"product_id": product_id, "branch_id": branch_id}, {"_id": 0}
    )
    old_quantity = existing["quantity"] if existing else 0

    if existing:
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": {"quantity": new_quantity, "updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(),
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity": new_quantity,
            "updated_at": now_iso()
        })

    diff = new_quantity - old_quantity

    # Full audit record
    correction_id = new_id()
    correction = {
        "id": correction_id,
        "product_id": product_id,
        "branch_id": branch_id,
        "old_quantity": old_quantity,
        "new_quantity": new_quantity,
        "difference": diff,
        "reason": reason,
        "performed_by_id": user["id"],
        "performed_by_name": user.get("full_name", user["username"]),
        "authorized_by": verified_by,
        "auth_mode": auth_mode,
        "created_at": now_iso(),
    }
    await db.inventory_corrections.insert_one(correction)
    del correction["_id"]

    # Movement history entry
    await log_movement(
        product_id, branch_id, "correction", diff,
        correction_id, "CORR", 0, user["id"],
        user.get("full_name", user["username"]), reason
    )

    return {
        "message": "Inventory corrected",
        "old_quantity": old_quantity,
        "new_quantity": new_quantity,
        "difference": diff,
        "correction": correction,
    }


@router.get("/corrections/{product_id}")
async def get_inventory_corrections(product_id: str, user=Depends(get_current_user)):
    """Get correction history for a specific product."""
    corrections = await db.inventory_corrections.find(
        {"product_id": product_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return corrections
