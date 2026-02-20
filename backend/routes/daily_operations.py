"""
Daily operations routes: Sales log, daily reports, close accounts.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import get_current_user, check_perm, now_iso, new_id, get_branch_filter, apply_branch_filter

router = APIRouter(tags=["Daily Operations"])


@router.get("/daily-log")
async def get_daily_log(user=Depends(get_current_user), branch_id: Optional[str] = None, date: Optional[str] = None):
    """Get sequential sales log for a date."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    query = {"date": date}
    if branch_id:
        query["branch_id"] = branch_id
    
    entries = await db.sales_log.find(query, {"_id": 0}).sort("sequence", 1).to_list(10000)
    return {"entries": entries, "date": date, "count": len(entries)}


@router.get("/daily-report")
async def get_daily_report(user=Depends(get_current_user), branch_id: Optional[str] = None, date: Optional[str] = None):
    """Get daily profit report."""
    check_perm(user, "reports", "view")
    
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    log_query = {"date": date}
    if branch_id:
        log_query["branch_id"] = branch_id
    
    # Sales by category
    cat_pipeline = [
        {"$match": log_query},
        {"$group": {"_id": "$category", "total": {"$sum": "$line_total"}, "count": {"$sum": "$quantity"}}}
    ]
    cat_results = await db.sales_log.aggregate(cat_pipeline).to_list(100)
    sales_by_category = {r["_id"] or "Uncategorized": {"total": r["total"], "count": r["count"]} for r in cat_results}
    total_revenue = sum(r["total"] for r in cat_results)
    
    # COGS - get cost prices for all sold products
    log_entries = await db.sales_log.find(log_query, {"_id": 0}).to_list(10000)
    total_cogs = 0
    for entry in log_entries:
        if entry.get("product_id"):
            prod = await db.products.find_one({"id": entry["product_id"]}, {"_id": 0, "cost_price": 1})
            if prod:
                total_cogs += (prod.get("cost_price", 0) * entry.get("quantity", 0))
    total_cogs = round(total_cogs, 2)
    
    # Expenses
    exp_query = {"date": date}
    if branch_id:
        exp_query["branch_id"] = branch_id
    expenses = await db.expenses.find(exp_query, {"_id": 0}).to_list(500)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    # Credit collections: only payments on OLD invoices (not today's new sales)
    pay_pipeline = [
        {"$match": {"status": {"$ne": "voided"}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": date}},
    ]
    if branch_id:
        pay_pipeline[0]["$match"]["branch_id"] = branch_id
    pay_pipeline.append({"$project": {"_id": 0, "invoice_number": 1, "customer_name": 1, "order_date": 1, "payment": "$payments"}})
    all_payments_today = await db.invoices.aggregate(pay_pipeline).to_list(500)
    
    # Only count payments on older invoices as credit collections (NOT same-day sales)
    credit_collections = [p for p in all_payments_today if p.get("order_date") != date]
    total_credit_collections = sum(p["payment"]["amount"] for p in credit_collections)
    
    # Total cash from all invoice payments (for cash flow)
    total_cash_from_invoices = sum(p["payment"]["amount"] for p in all_payments_today)
    
    gross_profit = round(total_revenue - total_cogs, 2)
    net_profit = round(gross_profit - total_expenses, 2)
    
    # Get real-time cashier wallet balance
    wallet_query = {"type": "cashier", "active": True}
    if branch_id:
        wallet_query["branch_id"] = branch_id
    cashier_wallet = await db.fund_wallets.find_one(wallet_query, {"_id": 0})
    cashier_balance = cashier_wallet["balance"] if cashier_wallet else 0
    
    return {
        "date": date,
        "new_sales_today": total_revenue,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "sales_by_category": sales_by_category,
        "expenses": expenses,
        "credit_collections": credit_collections,
        "total_credit_collections": total_credit_collections,
        "total_cash_from_invoices": total_cash_from_invoices,
        "cashier_wallet_balance": round(cashier_balance, 2),
        "transaction_count": len(log_entries),
    }


@router.get("/daily-close/{date}")
async def get_daily_close(date: str, user=Depends(get_current_user), branch_id: Optional[str] = None):
    """Get status of daily close for a date."""
    query = {"date": date}
    if branch_id:
        query["branch_id"] = branch_id
    closing = await db.daily_closings.find_one(query, {"_id": 0})
    return closing or {"status": "open", "date": date}


@router.post("/daily-close")
async def close_day(data: dict, user=Depends(get_current_user)):
    """Close accounts for a day."""
    check_perm(user, "reports", "close_day")
    
    date = data["date"]
    branch_id = data["branch_id"]
    
    # Check if already closed
    existing = await db.daily_closings.find_one({"date": date, "branch_id": branch_id, "status": "closed"}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Day already closed")
    
    # Get report data
    report_query = {"date": date, "branch_id": branch_id}
    log_entries = await db.sales_log.find(report_query, {"_id": 0}).to_list(10000)
    new_sales_today = sum(e.get("line_total", 0) for e in log_entries)
    
    # Sales by category
    cat_map = {}
    for e in log_entries:
        cat = e.get("category", "Uncategorized")
        cat_map[cat] = cat_map.get(cat, 0) + e.get("line_total", 0)
    
    # Expenses
    expenses = await db.expenses.find(report_query, {"_id": 0}).to_list(500)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    # Credit collections (payments on existing receivables)
    all_payments_pipeline = [
        {"$match": {"branch_id": branch_id, "status": {"$ne": "voided"}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": date}},
        {"$project": {
            "_id": 0, "invoice_number": 1, "customer_name": 1, "balance": 1,
            "interest_accrued": 1, "order_date": 1, "payment": "$payments"
        }}
    ]
    all_payments_today = await db.invoices.aggregate(all_payments_pipeline).to_list(500)
    
    # Credit collections = payments on invoices NOT created today
    credit_collections = []
    for p in all_payments_today:
        if p.get("order_date") != date:
            credit_collections.append({
                "customer": p.get("customer_name", ""),
                "invoice": p.get("invoice_number", ""),
                "principal_paid": p["payment"].get("applied_to_principal", p["payment"]["amount"]),
                "interest_paid": p["payment"].get("applied_to_interest", 0),
                "total_paid": p["payment"]["amount"],
                "balance": p.get("balance", 0)
            })
    total_credit_collections = sum(c["total_paid"] for c in credit_collections)
    
    # Cashier wallet
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
    previous_balance = wallet["balance"] if wallet else 0
    
    # Safe balance
    safe = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "safe", "active": True}, {"_id": 0})
    safe_balance = 0
    if safe:
        lots = await db.safe_lots.find({"wallet_id": safe["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}).to_list(500)
        safe_balance = sum(l["remaining_amount"] for l in lots)
    
    # Expected cash
    expected_cash = previous_balance
    
    # User input
    actual_cash = float(data.get("actual_cash", 0))
    bank_checks = float(data.get("bank_checks", 0))
    other_payment_forms = float(data.get("other_payment_forms", 0))
    cash_to_drawer = float(data.get("cash_to_drawer", 0))
    cash_to_safe = float(data.get("cash_to_safe", 0))
    
    extra_cash = round(actual_cash - (expected_cash - bank_checks - other_payment_forms), 2)
    
    # Create closing record
    close_record = {
        "id": new_id(),
        "branch_id": branch_id,
        "date": date,
        "status": "closed",
        "new_sales_today": new_sales_today,
        "sales_by_category": cat_map,
        "total_expenses": total_expenses,
        "credit_collections": credit_collections,
        "total_credit_collections": total_credit_collections,
        "previous_cashier_balance": previous_balance,
        "expected_cash": expected_cash,
        "actual_cash": actual_cash,
        "bank_checks": bank_checks,
        "other_payment_forms": other_payment_forms,
        "extra_cash": extra_cash,
        "cash_to_drawer": cash_to_drawer,
        "cash_to_safe": cash_to_safe,
        "cash_deposited_to_safe": cash_to_safe,
        "safe_balance": safe_balance,
        "closed_by": user["id"],
        "closed_by_name": user.get("full_name", user["username"]),
        "closed_at": now_iso(),
    }
    
    await db.daily_closings.insert_one(close_record)
    del close_record["_id"]
    
    # Update cashier wallet balance to cash_to_drawer
    if wallet:
        await db.fund_wallets.update_one({"id": wallet["id"]}, {"$set": {"balance": cash_to_drawer}})
    
    # Add to safe if cash_to_safe > 0
    if cash_to_safe > 0 and safe:
        await db.safe_lots.insert_one({
            "id": new_id(),
            "branch_id": branch_id,
            "wallet_id": safe["id"],
            "date_received": date,
            "original_amount": cash_to_safe,
            "remaining_amount": cash_to_safe,
            "source_reference": f"Day close {date}",
            "created_by": user["id"],
            "created_at": now_iso()
        })
    
    return close_record
