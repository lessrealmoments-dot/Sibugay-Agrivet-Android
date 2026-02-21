"""
Common helper functions used across the application.
"""
import uuid
from datetime import datetime, timezone, timedelta
from config import db


def now_iso():
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def new_id():
    """Generate a new UUID string."""
    return str(uuid.uuid4())


async def log_movement(product_id, branch_id, m_type, qty_change, ref_id, ref_number, price, user_id, user_name, notes=""):
    """Log a product movement (sale, purchase, adjustment, etc.)."""
    await db.movements.insert_one({
        "id": new_id(),
        "product_id": product_id,
        "branch_id": branch_id,
        "type": m_type,
        "quantity_change": qty_change,
        "reference_id": ref_id,
        "reference_number": ref_number,
        "price_at_time": float(price) if price else 0,
        "notes": notes,
        "user_id": user_id,
        "user_name": user_name,
        "created_at": now_iso()
    })


async def log_sale_items(branch_id, date, items, invoice_number, customer_name, payment_method, cashier_name):
    """Record each sold item to sequential sales log."""
    last = await db.sales_log.find_one(
        {"branch_id": branch_id, "date": date},
        {"_id": 0},
        sort=[("sequence", -1)]
    )
    seq = last["sequence"] if last else 0
    running = last["running_total"] if last else 0
    
    for item in items:
        seq += 1
        lt = float(item.get("total", item.get("quantity", 0) * item.get("rate", item.get("price", 0))))
        running = round(running + lt, 2)
        entry = {
            "id": new_id(),
            "branch_id": branch_id,
            "date": date,
            "sequence": seq,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "timestamp": now_iso(),
            "product_name": item.get("product_name", ""),
            "product_id": item.get("product_id", ""),
            "quantity": float(item.get("quantity", 0)),
            "unit_price": float(item.get("rate", item.get("price", 0))),
            "discount": float(item.get("discount_amount", 0)),
            "line_total": lt,
            "running_total": running,
            "category": item.get("category", ""),
            "invoice_number": invoice_number,
            "customer_name": customer_name,
            "payment_method": (payment_method or "cash").lower(),
            "cashier_name": cashier_name,
        }
        await db.sales_log.insert_one(entry)


async def get_active_date(branch_id):
    """Return today's date unless closed, then return next day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closed = await db.daily_closings.find_one(
        {"branch_id": branch_id, "date": today, "status": "closed"},
        {"_id": 0}
    )
    if closed:
        next_day = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        return next_day
    return today


async def update_cashier_wallet(branch_id, amount, reference=""):
    """Update cashier drawer wallet balance. Positive = cash in, negative = cash out."""
    wallet = await db.fund_wallets.find_one(
        {"branch_id": branch_id, "type": "cashier", "active": True},
        {"_id": 0}
    )
    if not wallet:
        wallet = {
            "id": new_id(),
            "branch_id": branch_id,
            "type": "cashier",
            "name": "Cashier Drawer",
            "balance": 0,
            "active": True,
            "created_at": now_iso()
        }
        await db.fund_wallets.insert_one(wallet)
        del wallet["_id"]
    
    await db.fund_wallets.update_one(
        {"id": wallet["id"]},
        {"$inc": {"balance": round(amount, 2)}}
    )
    await db.wallet_movements.insert_one({
        "id": new_id(),
        "wallet_id": wallet["id"],
        "branch_id": branch_id,
        "type": "cash_in" if amount >= 0 else "cash_out",
        "amount": round(amount, 2),
        "reference": reference,
        "created_at": now_iso()
    })


async def get_product_price(product: dict, branch_id: str, scheme: str) -> float:
    """
    Get the effective price for a product at a specific branch.
    Fallback chain: branch_prices override → product.prices (global default)
    """
    if branch_id:
        override = await db.branch_prices.find_one(
            {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
        )
        if override and scheme in (override.get("prices") or {}):
            return float(override["prices"][scheme])
    return float((product.get("prices") or {}).get(scheme, product.get("cost_price", 0)))


async def get_branch_cost(product: dict, branch_id: str) -> float:
    """
    Get the effective cost/capital price for a product at a specific branch.
    Fallback chain: branch_prices.cost_price → product.cost_price (global)
    """
    if branch_id:
        override = await db.branch_prices.find_one(
            {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
        )
        if override and override.get("cost_price") is not None:
            return float(override["cost_price"])
    return float(product.get("cost_price", 0))
