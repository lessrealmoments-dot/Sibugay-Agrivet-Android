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
    return entries


@router.get("/daily-report")
async def get_daily_report(user=Depends(get_current_user), branch_id: Optional[str] = None, date: Optional[str] = None):
    """Get daily profit report."""
    check_perm(user, "reports", "view")
    
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    query = {"date": date}
    branch_filter = await get_branch_filter(user, branch_id)
    query = apply_branch_filter(query, branch_filter)
    
    # Get sales from sales log
    sales_log = await db.sales_log.find(query, {"_id": 0}).to_list(10000)
    total_sales = sum(e.get("line_total", 0) for e in sales_log)
    
    # Get expenses
    expense_query = {"date": date}
    expense_query = apply_branch_filter(expense_query, branch_filter)
    expenses = await db.expenses.find(expense_query, {"_id": 0}).to_list(1000)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    # Get invoices for the day
    invoice_query = {"created_at": {"$gte": date, "$lt": date + "T23:59:59"}}
    invoice_query = apply_branch_filter(invoice_query, branch_filter)
    invoices = await db.invoices.find(invoice_query, {"_id": 0}).to_list(10000)
    
    # Calculate payments received
    payments_received = sum(inv.get("amount_paid", 0) for inv in invoices)
    
    # Calculate cost of goods sold (COGS)
    total_cogs = 0
    for inv in invoices:
        for item in inv.get("items", []):
            qty = item.get("quantity", 0)
            cost = item.get("cost_price", 0)
            total_cogs += qty * cost
    
    gross_profit = total_sales - total_cogs
    net_profit = gross_profit - total_expenses
    
    # Category breakdown
    category_sales = {}
    for e in sales_log:
        cat = e.get("category", "General")
        category_sales[cat] = category_sales.get(cat, 0) + e.get("line_total", 0)
    
    category_expenses = {}
    for e in expenses:
        cat = e.get("category", "Miscellaneous")
        category_expenses[cat] = category_expenses.get(cat, 0) + e.get("amount", 0)
    
    return {
        "date": date,
        "total_sales": total_sales,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "payments_received": payments_received,
        "invoice_count": len(invoices),
        "sales_transactions": len(set(e.get("invoice_number", "") for e in sales_log)),
        "category_sales": category_sales,
        "category_expenses": category_expenses,
    }


@router.get("/daily-close/{date}")
async def get_daily_close(date: str, user=Depends(get_current_user), branch_id: Optional[str] = None):
    """Get status of daily close for a date."""
    query = {"date": date}
    if branch_id:
        query["branch_id"] = branch_id
    close = await db.daily_closings.find_one(query, {"_id": 0})
    return close


@router.post("/daily-close")
async def close_day(data: dict, user=Depends(get_current_user)):
    """Close accounts for a day."""
    check_perm(user, "reports", "close_day")
    
    date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    branch_id = data["branch_id"]
    
    # Check if already closed
    existing = await db.daily_closings.find_one({"date": date, "branch_id": branch_id}, {"_id": 0})
    if existing and existing.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Day already closed")
    
    # Calculate totals
    sales_log = await db.sales_log.find({"date": date, "branch_id": branch_id}, {"_id": 0}).to_list(10000)
    total_sales = sum(e.get("line_total", 0) for e in sales_log)
    
    expenses = await db.expenses.find({"date": date, "branch_id": branch_id}, {"_id": 0}).to_list(1000)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    # Get cashier wallet balance
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
    cashier_balance = wallet["balance"] if wallet else 0
    
    # Physical count from user
    physical_count = float(data.get("physical_count", cashier_balance))
    variance = physical_count - cashier_balance
    
    close_record = {
        "id": new_id(),
        "branch_id": branch_id,
        "date": date,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "net_sales": total_sales - total_expenses,
        "system_balance": cashier_balance,
        "physical_count": physical_count,
        "variance": variance,
        "variance_notes": data.get("variance_notes", ""),
        "status": "closed",
        "closed_by": user["id"],
        "closed_by_name": user.get("full_name", user["username"]),
        "closed_at": now_iso(),
    }
    
    if existing:
        await db.daily_closings.update_one({"id": existing["id"]}, {"$set": close_record})
    else:
        await db.daily_closings.insert_one(close_record)
        del close_record["_id"]
    
    return close_record
