"""
Sync routes: Offline POS data sync.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from config import db
from utils import get_current_user, now_iso, new_id, log_movement, log_sale_items, update_cashier_wallet, get_active_date

router = APIRouter(tags=["Sync"])


@router.get("/sync/estimate")
async def get_sync_estimate(user=Depends(get_current_user), branch_id: str = None):
    """
    Quick pre-download count estimate — no heavy data fetching.
    Used by the frontend to show: "~2.4 MB · 3,241 products · 152 customers"
    before the user clicks Download.
    """
    product_count = await db.products.count_documents({"active": True})

    customer_q = {"active": True}
    if branch_id:
        customer_q["branch_id"] = branch_id
    customer_count = await db.customers.count_documents(customer_q)

    inventory_count = 0
    if branch_id:
        inventory_count = await db.inventory.count_documents({"branch_id": branch_id})

    # Rough KB estimate: products ~1.5KB, customers ~0.5KB, inventory ~0.1KB
    estimated_kb = round(product_count * 1.5 + customer_count * 0.5 + inventory_count * 0.1)

    return {
        "products": product_count,
        "customers": customer_count,
        "inventory": inventory_count,
        "estimated_kb": estimated_kb,
    }


@router.get("/sync/pos-data")
async def get_pos_sync_data(user=Depends(get_current_user), branch_id: str = None, last_sync: str = None):
    """Get data for offline POS sync — includes branch-specific prices.
    If last_sync is provided, only returns records updated since that timestamp (delta sync).
    """
    query = {"active": True}

    # Delta sync: only fetch records updated since last_sync
    if last_sync:
        try:
            query["$or"] = [
                {"updated_at": {"$gte": last_sync}},
                {"created_at": {"$gte": last_sync}},
            ]
        except Exception:
            pass  # Invalid date — fall back to full sync
    
    # Products catalog (global)
    products = await db.products.find(query, {"_id": 0}).to_list(10000)
    
    # Customers (branch-scoped)
    customers = await db.customers.find({"active": True}, {"_id": 0}).to_list(5000)
    
    # Price schemes (global)
    schemes = await db.price_schemes.find({"active": True}, {"_id": 0}).to_list(50)
    
    # Inventory quantities for branch (or aggregated across all branches)
    inventory = []
    if branch_id:
        inventory = await db.inventory.find({"branch_id": branch_id}, {"_id": 0}).to_list(10000)
    else:
        # No branch specified — aggregate total stock across all branches
        agg = await db.inventory.aggregate([
            {"$group": {"_id": "$product_id", "quantity": {"$sum": "$quantity"}}}
        ]).to_list(10000)
        inventory = [{"product_id": r["_id"], "quantity": r["quantity"]} for r in agg]
    
    # Branch price overrides — so cashiers sell at correct branch price offline
    branch_prices = []
    if branch_id:
        branch_prices = await db.branch_prices.find({"branch_id": branch_id}, {"_id": 0}).to_list(10000)

    # Merge inventory into products — inject `available` field per product
    inv_map = {inv["product_id"]: float(inv.get("quantity", 0)) for inv in inventory}
    bp_map  = {bp["product_id"]: bp for bp in branch_prices}

    enriched_products = []
    for p in products:
        p = dict(p)
        if p.get("is_repack") and p.get("parent_id"):
            # Repack: derive from parent stock
            parent_qty = inv_map.get(p["parent_id"], 0)
            units = p.get("units_per_parent", 1) or 1
            p["available"] = round(parent_qty * units, 4)
        else:
            p["available"] = inv_map.get(p["id"], 0)
        # Apply branch price overrides
        if p["id"] in bp_map:
            bp = bp_map[p["id"]]
            if bp.get("prices"):
                p["prices"] = {**(p.get("prices") or {}), **bp["prices"]}
            if bp.get("cost_price") is not None:
                p["cost_price"] = bp["cost_price"]
        enriched_products.append(p)
    
    return {
        "products": enriched_products,
        "customers": customers,
        "price_schemes": schemes,
        "inventory": inventory,
        "branch_prices": branch_prices,
        "sync_time": now_iso(),
        "is_delta": bool(last_sync),
    }


@router.post("/sales/sync")
async def sync_offline_sales(data: dict, user=Depends(get_current_user)):
    """
    Sync offline sales to server.
    Fixes applied vs original:
      - Calls log_movement after each inventory deduction (populates movement history)
      - Calls log_sale_items after invoice creation (populates daily sales log)
      - Warns (does not crash) when stock would go negative, but still processes sale
        so offline work isn't lost; adds a flag to the synced record for review.
    """
    sales = data.get("sales", [])
    synced = []
    errors = []

    for sale in sales:
        try:
            sale_id = sale.get("id", new_id())
            branch_id = sale.get("branch_id", "")

            # Idempotency — skip if already synced by id OR envelope_id
            envelope_id = sale.get("envelope_id", sale_id)
            existing = await db.invoices.find_one(
                {"$or": [{"id": sale_id}, {"envelope_id": envelope_id}]},
                {"_id": 0, "id": 1}
            )
            if existing:
                synced.append({"id": sale_id, "envelope_id": envelope_id, "status": "duplicate"})
                continue

            items = sale.get("items", [])
            subtotal = 0
            sale_date = sale.get("date", now_iso()[:10])
            inv_number = sale.get("invoice_number", f"SYNC-{sale_id[:8]}")
            stock_warnings = []

            for item in items:
                qty = float(item.get("quantity", 0))
                rate = float(item.get("rate", item.get("price", 0)))
                line_total = round(qty * rate, 2)
                item["total"] = line_total
                subtotal += line_total

                product = await db.products.find_one({"id": item.get("product_id")}, {"_id": 0})
                if not product:
                    continue

                if product.get("is_repack") and product.get("parent_id"):
                    units_per_parent = product.get("units_per_parent", 1)
                    parent_deduction = qty / units_per_parent

                    # Check stock — warn if would go negative but don't block (offline work must not be lost)
                    parent_inv = await db.inventory.find_one(
                        {"product_id": product["parent_id"], "branch_id": branch_id}, {"_id": 0}
                    )
                    current_stock = float(parent_inv["quantity"]) if parent_inv else 0.0
                    if current_stock < parent_deduction:
                        stock_warnings.append(
                            f"{product['name']}: need {parent_deduction:.4f} boxes, "
                            f"have {current_stock:.4f} — inventory will go negative"
                        )

                    await db.inventory.update_one(
                        {"product_id": product["parent_id"], "branch_id": branch_id},
                        {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                        upsert=True
                    )
                    # ── FIX: log movement (was missing) ──────────────────────────
                    await log_movement(
                        product["parent_id"], branch_id, "sale", -parent_deduction,
                        sale_id, inv_number, rate * units_per_parent,
                        user["id"], user.get("full_name", user["username"]),
                        f"Offline sale (synced): {product['name']} x {qty}"
                    )
                else:
                    # Regular product
                    inv = await db.inventory.find_one(
                        {"product_id": item.get("product_id"), "branch_id": branch_id}, {"_id": 0}
                    )
                    current_stock = float(inv["quantity"]) if inv else 0.0
                    if current_stock < qty:
                        stock_warnings.append(
                            f"{product['name']}: need {qty}, have {current_stock:.2f} — inventory will go negative"
                        )

                    await db.inventory.update_one(
                        {"product_id": item.get("product_id"), "branch_id": branch_id},
                        {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}},
                        upsert=True
                    )
                    # ── FIX: log movement (was missing) ──────────────────────────
                    await log_movement(
                        item.get("product_id"), branch_id, "sale", -qty,
                        sale_id, inv_number, rate,
                        user["id"], user.get("full_name", user["username"]),
                        "Offline sale (synced)"
                    )

            # Create invoice
            invoice = {
                "id": sale_id,
                "envelope_id": envelope_id,  # for idempotent re-sync detection
                "invoice_number": inv_number,
                "prefix": sale.get("prefix", "SYNC"),
                "customer_id": sale.get("customer_id"),
                "customer_name": sale.get("customer_name", "Walk-in"),
                "branch_id": branch_id,
                "order_date": sale_date,
                "invoice_date": sale_date,
                "due_date": sale_date,
                "items": items,
                "subtotal": subtotal,
                "freight": float(sale.get("freight", 0)),
                "overall_discount": float(sale.get("overall_discount", 0)),
                "grand_total": round(subtotal + float(sale.get("freight", 0)) - float(sale.get("overall_discount", 0)), 2),
                "amount_paid": float(sale.get("amount_paid", subtotal)),
                "balance": float(sale.get("balance", 0)),
                "status": sale.get("status", "paid"),
                "payment_type": sale.get("payment_type", "cash"),
                "payments": sale.get("payments", []),
                "cashier_id": user["id"],
                "cashier_name": user.get("full_name", user["username"]),
                "synced_from_offline": True,
                "offline_timestamp": sale.get("timestamp", ""),
                "stock_warnings": stock_warnings,   # attached for audit review
                "created_at": now_iso(),
            }

            await db.invoices.insert_one(invoice)
            del invoice["_id"]

            if invoice["amount_paid"] > 0:
                await update_cashier_wallet(branch_id, invoice["amount_paid"], f"Synced sale {inv_number}")

            if invoice.get("customer_id") and invoice["balance"] > 0:
                await db.customers.update_one(
                    {"id": invoice["customer_id"]},
                    {"$inc": {"balance": invoice["balance"]}}
                )

            # ── FIX: log to daily sales log (was missing) ────────────────────
            active_date = await get_active_date(branch_id)
            enriched = []
            for item in items:
                prod = await db.products.find_one({"id": item.get("product_id")}, {"_id": 0, "category": 1})
                enriched.append({**item, "category": prod.get("category", "General") if prod else "General"})

            payment_method = sale.get("payment_method", "cash" if invoice["payment_type"] == "cash" else "credit")
            await log_sale_items(
                branch_id, active_date, enriched, inv_number,
                invoice["customer_name"], payment_method,
                user.get("full_name", user["username"])
            )

            result = {"id": sale_id, "status": "synced", "invoice_number": inv_number}
            if stock_warnings:
                result["stock_warnings"] = stock_warnings
            synced.append(result)

        except Exception as e:
            errors.append({"id": sale.get("id"), "error": str(e)})

    return {
        "synced": synced,
        "errors": errors,
        "total_synced": len([s for s in synced if s.get("status") == "synced"]),
        "total_errors": len(errors),
        "results": synced,
    }
