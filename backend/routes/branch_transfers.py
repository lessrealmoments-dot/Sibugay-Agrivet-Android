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
    branch_id: Optional[str] = None,   # convenience: filter for either side
    skip: int = 0,
    limit: int = 40,
):
    """List branch transfer orders.
    Non-admins automatically see only orders relevant to their branch (from OR to).
    Admins can pass branch_id to filter, or omit it to see all.
    """
    q = {}
    if status:
        q["status"] = status
    if from_branch_id:
        q["from_branch_id"] = from_branch_id
    if to_branch_id:
        q["to_branch_id"] = to_branch_id

    # Branch isolation: non-admins only see their own branch's orders
    user_branch = user.get("branch_id")
    is_admin = user.get("role") == "admin"

    if branch_id:
        # Explicit branch filter (admin scoping to a specific branch)
        q["$or"] = [{"from_branch_id": branch_id}, {"to_branch_id": branch_id}]
    elif not is_admin and user_branch:
        # Non-admin: restrict to orders involving their branch
        q["$or"] = [{"from_branch_id": user_branch}, {"to_branch_id": user_branch}]

    total = await db.branch_transfer_orders.count_documents(q)
    orders = await db.branch_transfer_orders.find(
        q, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"orders": orders, "total": total}


@router.put("/{transfer_id}")
async def update_transfer(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """Edit a draft transfer order. Only source branch (or admin) can edit. Order must be draft."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be edited")

    # Non-admin: must be the source branch
    user_branch = user.get("branch_id")
    if user.get("role") != "admin" and user_branch and user_branch != order["from_branch_id"]:
        raise HTTPException(status_code=403, detail="Only the source branch can edit this transfer")

    items = data.get("items", order["items"])

    total_at_branch_capital = round(sum(
        float(i.get("branch_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_transfer_capital = round(sum(
        float(i.get("transfer_capital", 0)) * float(i.get("qty", 0)) for i in items), 2)
    total_at_branch_retail = round(sum(
        float(i.get("branch_retail", 0)) * float(i.get("qty", 0)) for i in items), 2)

    update = {
        "items": items,
        "min_margin": float(data.get("min_margin", order.get("min_margin", 20))),
        "category_markups": data.get("category_markups", order.get("category_markups", [])),
        "notes": data.get("notes", order.get("notes", "")),
        "total_at_branch_capital": total_at_branch_capital,
        "total_at_transfer_capital": total_at_transfer_capital,
        "total_at_branch_retail": total_at_branch_retail,
        "updated_at": now_iso(),
        "updated_by": user.get("full_name", user["username"]),
    }
    await db.branch_transfer_orders.update_one({"id": transfer_id}, {"$set": update})
    updated = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    return updated


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
    """Mark transfer as sent (goods are on the way). Creates incoming notification for destination."""
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft orders can be sent")

    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {"status": "sent", "sent_at": now_iso(), "sent_by": user["id"]}}
    )

    # Notify destination branch users + admins
    from_branch = await db.branches.find_one({"id": order["from_branch_id"]}, {"_id": 0, "name": 1})
    to_branch = await db.branches.find_one({"id": order["to_branch_id"]}, {"_id": 0, "name": 1})
    from_name = from_branch.get("name", order["from_branch_id"]) if from_branch else order["from_branch_id"]
    to_name = to_branch.get("name", order["to_branch_id"]) if to_branch else order["to_branch_id"]

    dest_users = await db.users.find(
        {"branch_id": order["to_branch_id"], "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    admins = await db.users.find(
        {"role": "admin", "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    target_ids = list({u["id"] for u in dest_users + admins})

    await db.notifications.insert_one({
        "id": new_id(),
        "type": "transfer_incoming",
        "title": "Incoming Stock Transfer",
        "message": f"Transfer {order['order_number']} from {from_name} is on the way — {len(order.get('items', []))} product(s)",
        "branch_id": order["to_branch_id"],
        "branch_name": to_name,
        "metadata": {
            "transfer_id": transfer_id,
            "order_number": order["order_number"],
            "from_branch": from_name,
            "to_branch": to_name,
        },
        "target_user_ids": target_ids,
        "read_by": [],
        "created_at": now_iso(),
    })

    return {"message": "Transfer sent", "status": "sent"}


@router.post("/{transfer_id}/receive")
async def receive_transfer(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """
    Submit received quantities for a branch transfer.
    - If ALL quantities match ordered: update inventory immediately → status 'received'
    - If ANY variance (shortage/excess): save pending receipt WITHOUT updating inventory
      → status 'received_pending', notify source to confirm or dispute
    """
    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] not in ["sent", "draft"]:
        raise HTTPException(status_code=400, detail="Transfer is not in a receivable state")

    from_branch_id = order["from_branch_id"]
    to_branch_id = order["to_branch_id"]

    from_branch = await db.branches.find_one({"id": from_branch_id}, {"_id": 0, "name": 1})
    to_branch = await db.branches.find_one({"id": to_branch_id}, {"_id": 0, "name": 1})
    from_name = from_branch.get("name", from_branch_id) if from_branch else from_branch_id
    to_name = to_branch.get("name", to_branch_id) if to_branch else to_branch_id

    qty_overrides = {item["product_id"]: float(item.get("qty_received", item["qty"]))
                     for item in data.get("items", [])}

    pending_items = []
    shortages = []
    excesses = []

    for item in order["items"]:
        product_id = item["product_id"]
        qty_ordered = float(item["qty"])
        qty_received = qty_overrides.get(product_id, qty_ordered)
        transfer_capital = float(item["transfer_capital"])
        branch_retail = float(item["branch_retail"])

        pending_items.append({
            **item,
            "qty_ordered": qty_ordered,
            "qty_received": qty_received,
        })

        variance = qty_ordered - qty_received   # positive = short, negative = excess
        if variance != 0:
            var_entry = {
                "product_id": product_id,
                "product_name": item["product_name"],
                "sku": item.get("sku", ""),
                "unit": item.get("unit", ""),
                "qty_ordered": qty_ordered,
                "qty_received": qty_received,
                "variance": variance,
                "transfer_capital": transfer_capital,
                "branch_retail": branch_retail,
                "capital_variance": round(abs(variance) * transfer_capital, 2),
                "retail_variance": round(abs(variance) * branch_retail, 2),
            }
            if variance > 0:
                shortages.append(var_entry)
            else:
                excesses.append(var_entry)

    has_variance = len(shortages) > 0 or len(excesses) > 0

    if has_variance:
        # ── PENDING PATH: store claim, do NOT touch inventory yet ────────────
        await db.branch_transfer_orders.update_one(
            {"id": transfer_id},
            {"$set": {
                "status": "received_pending",
                "pending_receipt_at": now_iso(),
                "pending_receipt_by": user["id"],
                "pending_receipt_by_name": user.get("full_name", user["username"]),
                "receive_notes": data.get("notes", ""),
                "pending_items": pending_items,
                "shortages": shortages,
                "excesses": excesses,
                "has_shortage": len(shortages) > 0,
                "has_excess": len(excesses) > 0,
            }}
        )

        # Notify source branch + admins to review
        src_users = await db.users.find(
            {"branch_id": from_branch_id, "active": True}, {"_id": 0, "id": 1}
        ).to_list(50)
        admins = await db.users.find(
            {"role": "admin", "active": True}, {"_id": 0, "id": 1}
        ).to_list(50)
        notify_ids = list({u["id"] for u in src_users + admins})

        variance_parts = []
        if shortages:
            variance_parts.append(f"{len(shortages)} short")
        if excesses:
            variance_parts.append(f"{len(excesses)} excess")

        await db.notifications.insert_one({
            "id": new_id(),
            "type": "transfer_variance_review",
            "title": "Transfer Receipt — Variance Needs Review",
            "message": (
                f"{to_name} received {order['order_number']} with discrepancy ({', '.join(variance_parts)}). "
                f"Please verify and Accept or Dispute."
            ),
            "branch_id": from_branch_id,
            "branch_name": from_name,
            "metadata": {
                "transfer_id": transfer_id,
                "order_number": order["order_number"],
                "shortages": shortages,
                "excesses": excesses,
            },
            "target_user_ids": notify_ids,
            "read_by": [],
            "created_at": now_iso(),
        })

        return {
            "message": "Receipt submitted — waiting for source branch to confirm the variance.",
            "status": "received_pending",
            "has_variance": True,
            "shortages": shortages,
            "excesses": excesses,
        }

    # ── EXACT MATCH PATH: update inventory immediately ───────────────────────
    return await _apply_receipt(
        order, pending_items, shortages, excesses, from_branch_id, to_branch_id,
        from_name, to_name, transfer_id, user, data.get("notes", "")
    )


async def _apply_receipt(order, items, shortages, excesses, from_branch_id, to_branch_id,
                          from_name, to_name, transfer_id, user, notes=""):
    """Apply the inventory movement for a confirmed receipt."""
    for item in items:
        product_id = item["product_id"]
        qty_received = float(item.get("qty_received", item["qty"]))
        transfer_capital = float(item["transfer_capital"])
        branch_retail = float(item["branch_retail"])

        if qty_received <= 0:
            continue

        # Check source has enough
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
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$inc": {"quantity": qty_received}, "$set": {"updated_at": now_iso()}},
            upsert=True
        )

        # Set branch_prices at destination
        await db.branch_prices.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$set": {
                "product_id": product_id, "branch_id": to_branch_id,
                "cost_price": transfer_capital,
                "prices": {"retail": branch_retail},
                "updated_at": now_iso(),
                "source": "branch_transfer",
                "transfer_order": order["order_number"],
            }},
            upsert=True
        )

        await db.branch_transfer_price_memory.update_one(
            {"product_id": product_id, "branch_id": to_branch_id},
            {"$set": {
                "product_id": product_id, "branch_id": to_branch_id,
                "last_retail_price": branch_retail, "last_transfer_capital": transfer_capital,
                "last_order_number": order["order_number"], "updated_at": now_iso(),
            }},
            upsert=True
        )

        await log_movement(
            product_id, from_branch_id, "transfer_out", -qty_received,
            transfer_id, order["order_number"], transfer_capital,
            user["id"], user.get("full_name", user["username"]),
            f"Branch transfer to {to_name}"
        )
        await log_movement(
            product_id, to_branch_id, "transfer_in", qty_received,
            transfer_id, order["order_number"], transfer_capital,
            user["id"], user.get("full_name", user["username"]),
            f"Branch transfer from {from_name}"
        )

    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "received",
            "received_at": now_iso(),
            "received_by": user["id"],
            "received_by_name": user.get("full_name", user["username"]),
            "receive_notes": notes,
            "items": items,
            "shortages": shortages,
            "excesses": excesses,
            "has_shortage": len(shortages) > 0,
            "has_excess": len(excesses) > 0,
        }}
    )

    return {
        "message": f"Transfer received. {len(items)} product(s) updated.",
        "order_number": order["order_number"],
        "status": "received",
        "shortages": shortages,
        "excesses": excesses,
        "has_shortage": len(shortages) > 0,
        "has_excess": len(excesses) > 0,
    }


@router.post("/{transfer_id}/accept-receipt")
async def accept_receipt(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """
    Source branch accepts the destination's claimed quantities.
    Triggers the actual inventory movement and finalises the transfer.
    Only the source branch (or admin) can accept.
    """
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "received_pending":
        raise HTTPException(status_code=400, detail="Transfer is not pending receipt confirmation")

    user_branch = user.get("branch_id")
    if user.get("role") != "admin" and user_branch and user_branch != order["from_branch_id"]:
        raise HTTPException(status_code=403, detail="Only the source branch can accept this receipt")

    from_branch_id = order["from_branch_id"]
    to_branch_id = order["to_branch_id"]
    from_branch = await db.branches.find_one({"id": from_branch_id}, {"_id": 0, "name": 1})
    to_branch = await db.branches.find_one({"id": to_branch_id}, {"_id": 0, "name": 1})
    from_name = from_branch.get("name", from_branch_id) if from_branch else from_branch_id
    to_name = to_branch.get("name", to_branch_id) if to_branch else to_branch_id

    items = order.get("pending_items", order["items"])
    shortages = order.get("shortages", [])
    excesses = order.get("excesses", [])

    result = await _apply_receipt(
        order, items, shortages, excesses, from_branch_id, to_branch_id,
        from_name, to_name, transfer_id, user,
        notes=order.get("receive_notes", "")
    )

    # Record who accepted and when
    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {
            "accepted_by": user["id"],
            "accepted_by_name": user.get("full_name", user["username"]),
            "accepted_at": now_iso(),
            "accept_note": data.get("note", ""),
        }}
    )

    # Notify destination that the receipt was accepted
    dest_users = await db.users.find(
        {"branch_id": to_branch_id, "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    admins = await db.users.find({"role": "admin", "active": True}, {"_id": 0, "id": 1}).to_list(50)
    notify_ids = list({u["id"] for u in dest_users + admins})
    await db.notifications.insert_one({
        "id": new_id(),
        "type": "transfer_accepted",
        "title": "Transfer Receipt Accepted",
        "message": f"{from_name} accepted the receipt for {order['order_number']}. Inventory has been updated.",
        "branch_id": to_branch_id,
        "branch_name": to_name,
        "metadata": {"transfer_id": transfer_id, "order_number": order["order_number"]},
        "target_user_ids": notify_ids,
        "read_by": [],
        "created_at": now_iso(),
    })

    return result


@router.post("/{transfer_id}/dispute-receipt")
async def dispute_receipt(transfer_id: str, data: dict, user=Depends(get_current_user)):
    """
    Source branch disputes the destination's claimed quantities.
    Inventory is NOT updated. Destination is notified to re-count.
    """
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    order = await db.branch_transfer_orders.find_one({"id": transfer_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if order["status"] != "received_pending":
        raise HTTPException(status_code=400, detail="Transfer is not pending receipt confirmation")

    user_branch = user.get("branch_id")
    if user.get("role") != "admin" and user_branch and user_branch != order["from_branch_id"]:
        raise HTTPException(status_code=403, detail="Only the source branch can dispute this receipt")

    dispute_note = data.get("note", "").strip()
    if not dispute_note:
        raise HTTPException(status_code=400, detail="Dispute reason is required")

    from_branch_id = order["from_branch_id"]
    to_branch_id = order["to_branch_id"]
    from_branch = await db.branches.find_one({"id": from_branch_id}, {"_id": 0, "name": 1})
    to_branch = await db.branches.find_one({"id": to_branch_id}, {"_id": 0, "name": 1})
    from_name = from_branch.get("name", from_branch_id) if from_branch else from_branch_id
    to_name = to_branch.get("name", to_branch_id) if to_branch else to_branch_id

    await db.branch_transfer_orders.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": now_iso(),
            "disputed_by": user["id"],
            "disputed_by_name": user.get("full_name", user["username"]),
            "dispute_note": dispute_note,
        }}
    )

    # Notify destination to re-count
    dest_users = await db.users.find(
        {"branch_id": to_branch_id, "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    admins = await db.users.find({"role": "admin", "active": True}, {"_id": 0, "id": 1}).to_list(50)
    notify_ids = list({u["id"] for u in dest_users + admins})
    await db.notifications.insert_one({
        "id": new_id(),
        "type": "transfer_disputed",
        "title": "Transfer Receipt Disputed",
        "message": (
            f"{from_name} disputes the quantities for {order['order_number']}. "
            f"Reason: {dispute_note}. Please re-count and re-submit."
        ),
        "branch_id": to_branch_id,
        "branch_name": to_name,
        "metadata": {
            "transfer_id": transfer_id,
            "order_number": order["order_number"],
            "dispute_note": dispute_note,
        },
        "target_user_ids": notify_ids,
        "read_by": [],
        "created_at": now_iso(),
    })

    return {
        "message": f"Receipt disputed. {to_name} has been notified to re-count.",
        "status": "disputed",
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
