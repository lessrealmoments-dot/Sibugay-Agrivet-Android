"""
Branch Transfer Orders — inter-branch stock movement with automatic price propagation.
Manages the 3-price model: Branch Capital → Transfer Capital → Branch Retail
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id,
    log_movement, get_branch_cost
)

router = APIRouter(prefix="/branch-transfers", tags=["Branch Transfers"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_po_refs(product_id: str):
    """Get moving average and last purchase cost from PO history."""
    last_po = await db.purchase_orders.find_one(
        {"items.product_id": product_id, "status": {"$in": ["received", "partial"]}},
        {"items": 1}, sort=[("created_at", -1)]
    )
    last_purchase = 0.0
    if last_po:
        for item in last_po.get("items", []):
            if item.get("product_id") == product_id:
                raw = item.get("unit_price") or item.get("cost") or item.get("unit_cost")
                if raw:
                    last_purchase = float(raw)
                break

    avg_r = await db.purchase_orders.aggregate([
        {"$match": {"items.product_id": product_id, "status": {"$in": ["received", "partial"]}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None,
            "total": {"$sum": {"$multiply": ["$items.quantity",
                {"$ifNull": ["$items.unit_price", {"$ifNull": ["$items.cost", 0]}]}]}},
            "qty": {"$sum": "$items.quantity"}
        }}
    ]).to_list(1)
    moving_average = (
        round(avg_r[0]["total"] / avg_r[0]["qty"], 4)
        if avg_r and avg_r[0]["qty"] > 0
        else 0.0
    )
    return round(last_purchase, 2), round(moving_average, 2)


async def _get_price_memory(product_id: str, to_branch_id: str):
    """Get last retail price and transfer capital for this product at the destination branch."""
    mem = await db.branch_transfer_price_memory.find_one(
        {"product_id": product_id, "branch_id": to_branch_id}, {"_id": 0}
    )
    return mem or {}


async def _apply_markup(cost: float, markup: dict) -> float:
    """Apply a single markup rule to a cost price."""
    if not markup:
        return cost
    mk_type = markup.get("type", "fixed")
    mk_val = float(markup.get("value", 0))
    if mk_type == "percent":
        return round(cost * (1 + mk_val / 100), 2)
    return round(cost + mk_val, 2)


# ── Markup template per destination branch ────────────────────────────────────

@router.get("/markup-template/{to_branch_id}")
async def get_markup_template(to_branch_id: str, user=Depends(get_current_user)):
    """Get saved category markup template for a destination branch."""
    template = await db.branch_transfer_templates.find_one(
        {"to_branch_id": to_branch_id}, {"_id": 0}
    )
    if not template:
        # Return defaults: empty markups, min_margin = 20
        return {
            "to_branch_id": to_branch_id,
            "min_margin": 20.0,
            "category_markups": [],
        }
    return template


@router.put("/markup-template/{to_branch_id}")
async def save_markup_template(to_branch_id: str, data: dict, user=Depends(get_current_user)):
    """Save category markup template for a destination branch."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")
    payload = {
        "to_branch_id": to_branch_id,
        "min_margin": float(data.get("min_margin", 20)),
        "category_markups": data.get("category_markups", []),
        "updated_by": user["id"],
        "updated_at": now_iso(),
    }
    await db.branch_transfer_templates.update_one(
        {"to_branch_id": to_branch_id}, {"$set": payload}, upsert=True
    )
    return payload


# ── Product lookup for the transfer form ──────────────────────────────────────

@router.get("/product-lookup")
async def lookup_product_for_transfer(
    q: str = "",
    from_branch_id: str = "",
    to_branch_id: str = "",
    user=Depends(get_current_user),
):
    """
    Search products and return all pricing data needed for a transfer row:
      branch_capital, moving_avg, last_purchase, last_branch_retail (memory).
    """
    if not q or len(q) < 1:
        return []
    query = {
        "active": True,
        "is_repack": {"$ne": True},
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
        ]
    }
    products = await db.products.find(query, {"_id": 0}).limit(10).to_list(10)
    results = []
    for p in products:
        global_cost = float(p.get("cost_price", 0))
        branch_capital = float(await get_branch_cost(p, from_branch_id)) if from_branch_id else global_cost
        last_purchase, moving_avg = await _get_po_refs(p["id"])
        memory = await _get_price_memory(p["id"], to_branch_id) if to_branch_id else {}
        results.append({
            "id": p["id"],
            "sku": p["sku"],
            "name": p["name"],
            "category": p.get("category", "General"),
            "unit": p.get("unit", ""),
            "branch_capital": branch_capital,
            "global_cost_price": global_cost,
            "is_branch_specific_cost": (branch_capital != global_cost),
            "last_purchase_ref": last_purchase,
            "moving_average_ref": moving_avg,
            "last_branch_retail": memory.get("last_retail_price"),
            "last_transfer_capital": memory.get("last_transfer_capital"),
        })
    return results


# ── Transfer order CRUD ───────────────────────────────────────────────────────

@router.get("")
async def list_transfers(
    user=Depends(get_current_user),
    status: Optional[str] = None,
    from_branch_id: Optional[str] = None,
    to_branch_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 40,
):
    """List branch transfer orders."""
    q = {}
    if status:
        q["status"] = status
    if from_branch_id:
        q["from_branch_id"] = from_branch_id
    if to_branch_id:
        q["to_branch_id"] = to_branch_id

    total = await db.branch_transfer_orders.count_documents(q)
    orders = await db.branch_transfer_orders.find(
        q, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"orders": orders, "total": total}


@router.post("")
async def create_transfer(data: dict, user=Depends(get_current_user)):
    """Create a new branch transfer order (saved as draft)."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    from_branch_id = data["from_branch_id"]
    to_branch_id = data["to_branch_id"]
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="No items in transfer")

    count = await db.branch_transfer_orders.count_documents({})
    order_number = f"BTO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"

    # Compute totals
    total_at_branch_capital = round(sum(
        float(i.get("branch_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_transfer_capital = round(sum(
        float(i.get("transfer_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_branch_retail = round(sum(
        float(i.get("branch_retail", 0)) * float(i.get("qty", 0)) for i in items), 2)

    transfer = {
        "id": new_id(),
        "order_number": order_number,
        "from_branch_id": from_branch_id,
        "to_branch_id": to_branch_id,
        "status": "draft",
        "min_margin": float(data.get("min_margin", 20)),
        "category_markups": data.get("category_markups", []),
        "items": items,
        "notes": data.get("notes", ""),
        "total_at_branch_capital": total_at_branch_capital,
        "total_at_transfer_capital": total_at_transfer_capital,
        "total_at_branch_retail": total_at_branch_retail,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
        "sent_at": None,
        "received_at": None,
        "received_by": None,
    }

    await db.branch_transfer_orders.insert_one(transfer)
    del transfer["_id"]
    return transfer


@router.get("/{transfer_id}")
async def get_transfer(transfer_id: str, user=Depends(get_current_user)):
    """Get a single branch transfer order."""
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return order


@router.put("/{transfer_id}")
async def update_transfer(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """Update a draft transfer order."""
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be edited")

    items = data.get("items", order["items"])
    total_at_branch_capital = round(sum(
        float(i.get("branch_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_transfer_capital = round(sum(
        float(i.get("transfer_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_branch_retail = round(sum(
        float(i.get("branch_retail", 0)) * float(i.get("qty", 0)) for i in items), 2)

    update = {
        "items": items,
        "min_margin": float(data.get("min_margin", order["min_margin"])),
        "category_markups": data.get("category_markups", order["category_markups"]),
        "notes": data.get("notes", order.get("notes", "")),
        "total_at_branch_capital": total_at_branch_capital,
        "total_at_transfer_capital": total_at_transfer_capital,
        "total_at_branch_retail": total_at_branch_retail,
        "updated_at": now_iso(),
    }
    await db.branch_transfer_orders.update_one({"id": transfer_id}, {"$set": update})
    return {**order, **update}


@router.post("/{transfer_id}/send")
async def send_transfer(transfer_id: str, user=Depends(get_current_user)):
    """Mark transfer as sent (goods are on the way)."""
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be sent")

    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {"status": "sent", "sent_at": now_iso(), "sent_by": user["id"]}}
    )
    return {"message": "Transfer sent", "status": "sent"}


@router.post("/{transfer_id}/receive")
async def receive_transfer(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """
    Confirm receipt of a branch transfer.
    - Deducts inventory from source branch
    - Adds inventory to destination branch
    - Sets branch_prices (transfer_capital as cost, branch_retail as retail price)
    - Updates price memory for future transfers
    Supports partial quantities via qty_received per item.
    """
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] not in ["sent", "draft"]:
        raise HTTPException(status_code=400, detail="Transfer is not in a receivable state")

    from_branch_id = order["from_branch_id"]
    to_branch_id = order["to_branch_id"]

    # Optional qty overrides from receiving party
    qty_overrides = {item["product_id"]: float(item.get("qty_received", item["qty"]))
                     for item in data.get("items", [])}

    received_items = []
    for item in order["items"]:
        product_id = item["product_id"]
        qty_ordered = float(item["qty"])
        qty_received = qty_overrides.get(product_id, qty_ordered)
        transfer_capital = float(item["transfer_capital"])
        branch_retail = float(item["branch_retail"])

        if qty_received <= 0:
            continue

        # Deduct from source branch
        source_inv = await db.inventory.find_one(
            {"product_id": product_id, "branch_id": from_branch_id}, {"_id": 0}
        )
        source_stock = float(source_inv["quantity"]) if source_inv else 0
        if source_stock < qty_received:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{item['product_name']}' in source branch: "
                       f"have {source_stock:.0f}, need {qty_received:.0f}"
            )

        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": from_branch_id},
            {"$inc": {"quantity": -qty_received}, "$set": {"updated_at": now_iso()}}
        )

        # Add to destination branch
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$inc": {"quantity": qty_received}, "$set": {"updated_at": now_iso()}},
            upsert=True
        )

        # Set branch_prices at destination (transfer_capital = their cost, branch_retail = their retail)
        await db.branch_prices.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$set": {
                "product_id": product_id,
                "branch_id": to_branch_id,
                "cost_price": transfer_capital,
                "prices": {"retail": branch_retail},
                "updated_at": now_iso(),
                "source": "branch_transfer",
                "transfer_order": order["order_number"],
            }},
            upsert=True
        )

        # Update price memory for future transfers
        await db.branch_transfer_price_memory.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$set": {
                "product_id": product_id,
                "branch_id": to_branch_id,
                "last_retail_price": branch_retail,
                "last_transfer_capital": transfer_capital,
                "last_order_number": order["order_number"],
                "updated_at": now_iso(),
            }},
            upsert=True
        )

        # Log movements
        await log_movement(
            product_id, from_branch_id, "transfer_out", -qty_received,
            transfer_id, order["order_number"], transfer_capital,
            user["id"], user.get("full_name", user["username"]),
            f"Branch transfer to {to_branch_id}"
        )
        await log_movement(
            product_id, to_branch_id, "transfer_in", qty_received,
            transfer_id, order["order_number"], transfer_capital,
            user["id"], user.get("full_name", user["username"]),
            f"Branch transfer from {from_branch_id}"
        )

        received_items.append({**item, "qty_received": qty_received})

    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "received",
            "received_at": now_iso(),
            "received_by": user["id"],
            "received_by_name": user.get("full_name", user["username"]),
            "items": received_items,
        }}
    )

    return {
        "message": f"Transfer received. {len(received_items)} product(s) updated.",
        "order_number": order["order_number"],
        "items_received": len(received_items),
    }


@router.delete("/{transfer_id}")
async def cancel_transfer(transfer_id: str, user=Depends(get_current_user)):
    """Cancel a draft or sent transfer."""
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] == "received":
        raise HTTPException(status_code=400, detail="Cannot cancel a received transfer")
    await db.branch_transfer_orders.update_one(
        {"id": transfer_id}, {"$set": {"status": "cancelled", "cancelled_at": now_iso()}}
    )
    return {"message": "Transfer cancelled"}
