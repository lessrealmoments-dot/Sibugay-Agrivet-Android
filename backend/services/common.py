"""
Shared service functions for AgriPOS
"""
from database import db, now_iso, new_id
import logging

logger = logging.getLogger(__name__)

async def log_movement(product_id, branch_id, m_type, qty_change, ref_id, ref_number, price, user_id, user_name, notes=""):
    """Log inventory movement"""
    movement = {
        "id": new_id(), "product_id": product_id, "branch_id": branch_id, "type": m_type,
        "quantity_change": qty_change, "reference_id": ref_id, "reference_number": ref_number,
        "unit_price": price, "user_id": user_id, "user_name": user_name, "notes": notes, "created_at": now_iso(),
    }
    await db.inventory_movements.insert_one(movement)

async def log_sale_items(branch_id, date, items, invoice_number, customer_name, payment_method, cashier_name):
    """Log items to sales_log for daily reporting"""
    last = await db.sales_log.find_one({"branch_id": branch_id, "date": date}, sort=[("sequence", -1)])
    seq = (last["sequence"] if last else 0) + 1
    for item in items:
        log_entry = {
            "id": new_id(),
            "branch_id": branch_id,
            "date": date,
            "sequence": seq,
            "time": now_iso(),
            "product_name": item.get("product_name", ""),
            "customer_name": customer_name,
            "invoice_number": invoice_number,
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("price", 0),
            "discount": item.get("discount", 0),
            "line_total": item.get("total", item.get("quantity", 1) * item.get("price", 0) - item.get("discount", 0)),
            "payment_method": payment_method,
            "cashier": cashier_name,
        }
        await db.sales_log.insert_one(log_entry)
        seq += 1

async def get_active_date(branch_id):
    """Get active date for a branch (next open day after last close)"""
    from datetime import datetime, timezone, timedelta
    last_close = await db.daily_closes.find_one(
        {"branch_id": branch_id}, sort=[("date", -1)], projection={"_id": 0, "date": 1}
    )
    if last_close:
        last_date = datetime.fromisoformat(last_close["date"].replace("Z", "+00:00"))
        return (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

async def update_cashier_wallet(branch_id, amount, reference=""):
    """Update cashier wallet balance and log movement"""
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier"}, {"_id": 0})
    if not wallet:
        wallet = {"id": new_id(), "branch_id": branch_id, "type": "cashier", "name": "Cashier Drawer", "balance": 0, "created_at": now_iso()}
        await db.fund_wallets.insert_one(wallet)
    new_balance = (wallet.get("balance", 0) or 0) + amount
    await db.fund_wallets.update_one({"id": wallet["id"]}, {"$set": {"balance": new_balance}})
    
    movement = {
        "id": new_id(), "wallet_id": wallet["id"], "wallet_name": "Cashier Drawer",
        "branch_id": branch_id, "type": "credit" if amount > 0 else "debit",
        "amount": abs(amount), "balance_after": new_balance, "reference": reference, "created_at": now_iso(),
    }
    await db.wallet_movements.insert_one(movement)
    return new_balance
