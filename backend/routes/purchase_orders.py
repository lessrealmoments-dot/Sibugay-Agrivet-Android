"""
Purchase Order routes: CRUD, receiving, payments.
Supports multi-branch data isolation.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
import uuid
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id, 
    log_movement, update_cashier_wallet,
    get_branch_filter, apply_branch_filter, ensure_branch_access
)

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.get("")
async def list_purchase_orders(
    user=Depends(get_current_user),
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List all purchase orders with optional status filter. Respects branch isolation."""
    query = {}
    
    # Apply branch filter for data isolation
    branch_filter = await get_branch_filter(user, branch_id)
    query = apply_branch_filter(query, branch_filter)
    
    if status:
        query["status"] = status
    
    total = await db.purchase_orders.count_documents(query)
    items = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"purchase_orders": items, "total": total}


@router.post("")
async def create_purchase_order(data: dict, user=Depends(get_current_user)):
    """Create a new purchase order."""
    check_perm(user, "inventory", "adjust")
    
    items = data.get("items", [])
    subtotal = sum(float(i.get("quantity", 0)) * float(i.get("unit_price", 0)) for i in items)
    payment_method = data.get("payment_method", "cash")
    branch_id = data.get("branch_id", "")
    
    po = {
        "id": new_id(),
        "po_number": data.get("po_number", "").strip() or f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}",
        "vendor": data["vendor"],
        "branch_id": branch_id,
        "items": [{
            "product_id": i["product_id"],
            "product_name": i.get("product_name", ""),
            "quantity": float(i["quantity"]),
            "unit_price": float(i.get("unit_price", 0)),
            "total": float(i["quantity"]) * float(i.get("unit_price", 0))
        } for i in items],
        "subtotal": subtotal,
        "status": data.get("status", "ordered"),
        "purchase_date": data.get("purchase_date", now_iso()[:10]),
        "payment_method": payment_method,
        "payment_status": "paid" if payment_method == "cash" else "unpaid",
        "amount_paid": subtotal if payment_method == "cash" else 0,
        "balance": 0 if payment_method == "cash" else subtotal,
        "received_date": None,
        "notes": data.get("notes", ""),
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await db.purchase_orders.insert_one(po)
    del po["_id"]
    
    # Cash payment: deduct from cashier drawer
    if payment_method == "cash" and subtotal > 0:
        await update_cashier_wallet(branch_id, -subtotal, f"PO Payment {po['po_number']} - {data['vendor']}")
    
    # Credit: create payable
    if payment_method == "credit" and subtotal > 0:
        await db.payables.insert_one({
            "id": new_id(),
            "supplier": data["vendor"],
            "branch_id": branch_id,
            "description": f"Purchase Order {po['po_number']}",
            "po_id": po["id"],
            "amount": subtotal,
            "paid": 0,
            "balance": subtotal,
            "due_date": data.get("due_date", ""),
            "status": "pending",
            "created_at": now_iso(),
        })
    
    return po


@router.put("/{po_id}")
async def update_purchase_order(po_id: str, data: dict, user=Depends(get_current_user)):
    """Update a purchase order."""
    check_perm(user, "inventory", "adjust")
    
    allowed = ["vendor", "items", "purchase_date", "notes", "status", "branch_id"]
    update = {k: v for k, v in data.items() if k in allowed}
    
    if "items" in update:
        update["subtotal"] = sum(float(i.get("quantity", 0)) * float(i.get("unit_price", 0)) for i in update["items"])
    
    update["updated_at"] = now_iso()
    await db.purchase_orders.update_one({"id": po_id}, {"$set": update})
    
    return await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})


@router.post("/{po_id}/receive")
async def receive_purchase_order(po_id: str, user=Depends(get_current_user)):
    """Receive a purchase order and update inventory."""
    check_perm(user, "inventory", "adjust")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    if po["status"] == "received":
        raise HTTPException(status_code=400, detail="PO already received")
    
    branch_id = po.get("branch_id", "")
    
    for item in po.get("items", []):
        pid = item["product_id"]
        qty = float(item["quantity"])
        price = float(item.get("unit_price", 0))
        
        # Update inventory
        existing = await db.inventory.find_one({"product_id": pid, "branch_id": branch_id})
        if existing:
            await db.inventory.update_one(
                {"product_id": pid, "branch_id": branch_id},
                {"$inc": {"quantity": qty}, "$set": {"updated_at": now_iso()}}
            )
        else:
            await db.inventory.insert_one({
                "id": new_id(),
                "product_id": pid,
                "branch_id": branch_id,
                "quantity": qty,
                "updated_at": now_iso()
            })
        
        # Log movement
        await log_movement(
            pid, branch_id, "purchase", qty, po["id"], po["po_number"],
            price, user["id"], user.get("full_name", user["username"]),
            f"PO received from {po['vendor']}"
        )
        
        # Update product cost: Last Purchase + Moving Average
        product_update = {"last_vendor": po["vendor"], "cost_price": price}
        
        # Recalculate moving average from all purchase movements
        all_purchases = await db.movements.find(
            {"product_id": pid, "type": "purchase", "quantity_change": {"$gt": 0}}, {"_id": 0}
        ).to_list(10000)
        
        total_pqty = sum(m["quantity_change"] for m in all_purchases)
        total_pcost = sum(m["quantity_change"] * m.get("price_at_time", 0) for m in all_purchases)
        
        if total_pqty > 0:
            product_update["moving_average_cost"] = round(total_pcost / total_pqty, 2)
        
        await db.products.update_one({"id": pid}, {"$set": product_update})
        
        # Update vendor last_price
        await db.product_vendors.update_many(
            {"product_id": pid, "vendor_name": po["vendor"]},
            {"$set": {"last_price": price, "last_order_date": now_iso()[:10]}}
        )
    
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {"status": "received", "received_date": now_iso()}}
    )
    
    return {"message": "PO received, inventory updated"}


@router.delete("/{po_id}")
async def cancel_purchase_order(po_id: str, user=Depends(get_current_user)):
    """Cancel a purchase order."""
    check_perm(user, "inventory", "adjust")
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "cancelled"}})
    return {"message": "PO cancelled"}


@router.post("/{po_id}/pay")
async def pay_purchase_order(po_id: str, data: dict, user=Depends(get_current_user)):
    """Record a payment on a purchase order."""
    check_perm(user, "accounting", "create")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    if po.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="PO already paid")
    
    amount = float(data.get("amount", po.get("balance", po["subtotal"])))
    branch_id = po.get("branch_id", "")
    
    ref_parts = [f"PO Payment {po['po_number']} - {po['vendor']}"]
    if data.get("check_number"):
        ref_parts.append(f"Check #{data['check_number']}")
    
    await update_cashier_wallet(branch_id, -amount, " ".join(ref_parts))
    
    new_paid = po.get("amount_paid", 0) + amount
    new_balance = max(0, round(po["subtotal"] - new_paid, 2))
    new_status = "paid" if new_balance <= 0 else "partial"
    
    payment_record = {
        "id": new_id(),
        "amount": amount,
        "date": data.get("payment_date", now_iso()[:10]),
        "check_number": data.get("check_number", ""),
        "check_date": data.get("check_date", ""),
        "method": data.get("method", "Cash"),
        "recorded_by": user.get("full_name", user["username"]),
        "recorded_at": now_iso(),
    }
    
    await db.purchase_orders.update_one({"id": po_id}, {
        "$set": {
            "amount_paid": new_paid,
            "balance": new_balance,
            "payment_status": new_status
        },
        "$push": {"payment_history": payment_record}
    })
    
    # Update payable if exists
    payable = await db.payables.find_one({"po_id": po_id}, {"_id": 0})
    if payable:
        pay_new_paid = payable["paid"] + amount
        pay_new_balance = max(0, round(payable["amount"] - pay_new_paid, 2))
        pay_status = "paid" if pay_new_balance <= 0 else "partial"
        await db.payables.update_one(
            {"po_id": po_id},
            {"$set": {"paid": pay_new_paid, "balance": pay_new_balance, "status": pay_status}}
        )
    
    return {
        "message": "Payment recorded",
        "new_balance": new_balance,
        "payment_status": new_status
    }


@router.get("/vendors")
async def list_po_vendors(user=Depends(get_current_user)):
    """Get unique vendor names from purchase orders."""
    vendors = await db.purchase_orders.distinct("vendor", {"status": {"$ne": "cancelled"}})
    return sorted(vendors)


@router.get("/by-vendor")
async def get_vendor_pos(vendor: str, user=Depends(get_current_user)):
    """Get all POs for a vendor, unpaid ones first."""
    pos = await db.purchase_orders.find(
        {"vendor": vendor, "status": {"$ne": "cancelled"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return pos
