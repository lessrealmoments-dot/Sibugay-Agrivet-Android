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
    """Get data for offline POS sync — includes branch-specific prices."""
    query = {"active": True}
    
    # Products catalog (global)
    products = await db.products.find(query, {"_id": 0}).to_list(10000)
    
    # Customers (branch-scoped)
    customers = await db.customers.find({"active": True}, {"_id": 0}).to_list(5000)
    
    # Price schemes (global)
    schemes = await db.price_schemes.find({"active": True}, {"_id": 0}).to_list(50)
    
    # Inventory quantities for branch
    inventory = []
    if branch_id:
        inventory = await db.inventory.find({"branch_id": branch_id}, {"_id": 0}).to_list(10000)
    
    # Branch price overrides — so cashiers sell at correct branch price offline
    branch_prices = []
    if branch_id:
        branch_prices = await db.branch_prices.find({"branch_id": branch_id}, {"_id": 0}).to_list(10000)
    
    return {
        "products": products,
        "customers": customers,
        "price_schemes": schemes,
        "inventory": inventory,
        "branch_prices": branch_prices,
        "sync_time": now_iso(),
    }


@router.post("/sales/sync")
async def sync_offline_sales(data: dict, user=Depends(get_current_user)):
    """Sync offline sales to server."""
    sales = data.get("sales", [])
    synced = []
    errors = []
    
    for sale in sales:
        try:
            sale_id = sale.get("id", new_id())
            branch_id = sale.get("branch_id", "")
            
            # Check if already synced
            existing = await db.invoices.find_one({"id": sale_id}, {"_id": 0})
            if existing:
                synced.append({"id": sale_id, "status": "already_synced"})
                continue
            
            # Process items
            items = sale.get("items", [])
            subtotal = 0
            
            for item in items:
                qty = float(item.get("quantity", 0))
                rate = float(item.get("rate", item.get("price", 0)))
                line_total = round(qty * rate, 2)
                item["total"] = line_total
                subtotal += line_total
                
                # Deduct inventory
                product = await db.products.find_one({"id": item.get("product_id")}, {"_id": 0})
                if product:
                    if product.get("is_repack") and product.get("parent_id"):
                        units_per_parent = product.get("units_per_parent", 1)
                        parent_deduction = qty / units_per_parent
                        await db.inventory.update_one(
                            {"product_id": product["parent_id"], "branch_id": branch_id},
                            {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                            upsert=True
                        )
                    else:
                        await db.inventory.update_one(
                            {"product_id": item.get("product_id"), "branch_id": branch_id},
                            {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}},
                            upsert=True
                        )
            
            # Create invoice
            invoice = {
                "id": sale_id,
                "invoice_number": sale.get("invoice_number", f"SYNC-{sale_id[:8]}"),
                "prefix": sale.get("prefix", "SYNC"),
                "customer_id": sale.get("customer_id"),
                "customer_name": sale.get("customer_name", "Walk-in"),
                "branch_id": branch_id,
                "order_date": sale.get("date", now_iso()[:10]),
                "invoice_date": sale.get("date", now_iso()[:10]),
                "due_date": sale.get("date", now_iso()[:10]),
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
                "created_at": now_iso(),
            }
            
            await db.invoices.insert_one(invoice)
            del invoice["_id"]
            
            # Update cashier wallet
            if invoice["amount_paid"] > 0:
                await update_cashier_wallet(branch_id, invoice["amount_paid"], f"Synced sale {invoice['invoice_number']}")
            
            # Update customer balance
            if invoice.get("customer_id") and invoice["balance"] > 0:
                await db.customers.update_one(
                    {"id": invoice["customer_id"]},
                    {"$inc": {"balance": invoice["balance"]}}
                )
            
            synced.append({"id": sale_id, "status": "synced", "invoice_number": invoice["invoice_number"]})
        except Exception as e:
            errors.append({"id": sale.get("id"), "error": str(e)})
    
    return {
        "synced": synced,
        "errors": errors,
        "total_synced": len(synced),
        "total_errors": len(errors),
    }
