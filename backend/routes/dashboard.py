"""
Dashboard routes: statistics, summaries, multi-branch overview.
Supports multi-branch data isolation with owner cross-branch views.
"""
from fastapi import APIRouter, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import (
    get_current_user, get_branch_filter, apply_branch_filter,
    get_user_branches, get_default_branch
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


async def _compute_ar_aging(branch_filter):
    """Compute AR aging buckets across all outstanding invoices."""
    today = datetime.now(timezone.utc).date()
    match = {"status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}
    match = apply_branch_filter(match, branch_filter)
    invoices = await db.invoices.find(match, {"_id": 0, "balance": 1, "order_date": 1, "customer_name": 1}).to_list(5000)
    buckets = {"current": 0, "days_31_60": 0, "days_61_90": 0, "over_90": 0, "total": 0}
    for inv in invoices:
        bal = float(inv.get("balance", 0))
        buckets["total"] = round(buckets["total"] + bal, 2)
        try:
            age = (today - datetime.strptime(inv["order_date"], "%Y-%m-%d").date()).days
        except Exception:
            age = 0
        if age <= 30:
            buckets["current"] = round(buckets["current"] + bal, 2)
        elif age <= 60:
            buckets["days_31_60"] = round(buckets["days_31_60"] + bal, 2)
        elif age <= 90:
            buckets["days_61_90"] = round(buckets["days_61_90"] + bal, 2)
        else:
            buckets["over_90"] = round(buckets["over_90"] + bal, 2)
    return buckets


async def _get_top_debtors(branch_filter, limit=5):
    """Top customers by outstanding AR balance."""
    match = {"status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}
    match = apply_branch_filter(match, branch_filter)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$customer_name", "customer_id": {"$first": "$customer_id"},
                    "total_balance": {"$sum": "$balance"}, "invoice_count": {"$sum": 1}}},
        {"$sort": {"total_balance": -1}},
        {"$limit": limit},
    ]
    rows = await db.invoices.aggregate(pipeline).to_list(limit)
    return [{"customer": r["_id"], "balance": round(r["total_balance"], 2), "invoices": r["invoice_count"]} for r in rows]


@router.get("/stats")
async def dashboard_stats(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None
):
    """
    Get comprehensive dashboard statistics. Respects branch isolation.
    Returns KPIs, cash position, AR aging, today's credits, last close date.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_dt = datetime.now(timezone.utc)

    branch_filter = await get_branch_filter(user, branch_id)
    effective_branch_id = branch_id or (user.get("branch_id") if user.get("role") != "admin" else None)

    # ── Today's invoices ─────────────────────────────────────────────────────
    invoice_query = {"status": {"$ne": "voided"}, "order_date": today}
    invoice_query = apply_branch_filter(invoice_query, branch_filter)
    today_invoices = await db.invoices.find(invoice_query, {"_id": 0}).to_list(10000)
    today_revenue = round(sum(inv.get("grand_total", 0) for inv in today_invoices), 2)
    today_count = len(today_invoices)
    today_cash_sales = round(sum(
        inv.get("grand_total", 0) for inv in today_invoices
        if inv.get("payment_type") == "cash"
    ), 2)
    today_credit_sales = round(sum(
        inv.get("grand_total", 0) for inv in today_invoices
        if inv.get("payment_type") in ("credit", "partial")
    ), 2)

    # Customers who got credit today
    credit_customers_today = [
        {"customer_name": inv.get("customer_name", "Walk-in"),
         "invoice_number": inv.get("invoice_number", ""),
         "amount": round(float(inv.get("grand_total", 0)), 2),
         "balance": round(float(inv.get("balance", inv.get("grand_total", 0))), 2),
         "type": inv.get("sale_type", "credit"),
         "created_at": inv.get("created_at", "")[:16]}
        for inv in today_invoices if inv.get("payment_type") in ("credit", "partial")
    ]

    # ── AR collected today (payments on older invoices) ───────────────────────
    ar_pay_pipeline = [
        {"$match": apply_branch_filter({"status": {"$ne": "voided"}, "order_date": {"$ne": today}}, branch_filter)},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": today}},
        {"$group": {"_id": None, "total": {"$sum": "$payments.amount"},
                    "payments": {"$push": {
                        "customer_name": "$customer_name",
                        "invoice_number": "$invoice_number",
                        "amount": "$payments.amount",
                        "date": "$payments.date"
                    }}}}
    ]
    ar_pay_result = await db.invoices.aggregate(ar_pay_pipeline).to_list(1)
    today_ar_collected = round(ar_pay_result[0]["total"] if ar_pay_result else 0, 2)
    recent_ar_payments = (ar_pay_result[0].get("payments", []) if ar_pay_result else [])[:5]

    # ── Today's expenses ──────────────────────────────────────────────────────
    expense_query = {"date": today}
    expense_query = apply_branch_filter(expense_query, branch_filter)
    today_expenses_list = await db.expenses.find(expense_query, {"_id": 0}).to_list(1000)
    today_expense_total = round(sum(e.get("amount", 0) for e in today_expenses_list), 2)

    # ── Cash position ─────────────────────────────────────────────────────────
    cashier_balance = 0.0
    safe_balance = 0.0
    if effective_branch_id:
        wallet = await db.fund_wallets.find_one(
            {"branch_id": effective_branch_id, "type": "cashier", "active": True}, {"_id": 0}
        )
        cashier_balance = float(wallet["balance"]) if wallet else 0.0
        safe_w = await db.fund_wallets.find_one(
            {"branch_id": effective_branch_id, "type": "safe", "active": True}, {"_id": 0}
        )
        if safe_w:
            lots = await db.safe_lots.find(
                {"wallet_id": safe_w["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}
            ).to_list(500)
            safe_balance = sum(lot.get("remaining_amount", 0) for lot in lots)
        wallets = await db.fund_wallets.find({"type": "cashier", "active": True}, {"_id": 0}).to_list(100)
        cashier_balance = sum(float(w.get("balance", 0)) for w in wallets)

    # ── AR aging ──────────────────────────────────────────────────────────────
    ar_aging = await _compute_ar_aging(branch_filter)
    top_debtors = await _get_top_debtors(branch_filter)

    # ── Last close date ───────────────────────────────────────────────────────
    close_query = {"status": "closed"}
    if effective_branch_id:
        close_query["branch_id"] = effective_branch_id
    last_close = await db.daily_closings.find_one(close_query, {"_id": 0, "date": 1}, sort=[("date", -1)])
    last_close_date = last_close["date"] if last_close else None
    days_since_close = None
    if last_close_date:
        try:
            days_since_close = (datetime.now(timezone.utc).date() -
                                datetime.strptime(last_close_date, "%Y-%m-%d").date()).days
        except Exception:
            pass

    # ── Total products / low stock ────────────────────────────────────────────
    total_products = await db.products.count_documents({"active": True})
    low_stock_pipeline = [
        {"$match": {"active": True}},
        {"$lookup": {
            "from": "inventory",
            "let": {"pid": "$id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$product_id", "$$pid"]}}},
                *([{"$match": branch_filter}] if branch_filter else [])
            ],
            "as": "inv"
        }},
        {"$addFields": {"total_stock": {"$sum": "$inv.quantity"}}},
        {"$match": {"total_stock": {"$lte": 10}}},
        {"$count": "total"}
    ]
    low_stock_result = await db.products.aggregate(low_stock_pipeline).to_list(1)
    low_stock_count = low_stock_result[0]["total"] if low_stock_result else 0

    # ── Total customers ───────────────────────────────────────────────────────
    customer_query = {"active": True}
    if branch_filter and user.get("role") != "admin":
        customer_query = apply_branch_filter(customer_query, branch_filter)
    total_customers = await db.customers.count_documents(customer_query)

    # ── Recent sales (invoices) ───────────────────────────────────────────────
    recent_invoice_query = {"status": {"$ne": "voided"}}
    recent_invoice_query = apply_branch_filter(recent_invoice_query, branch_filter)
    recent_invoices = await db.invoices.find(
        recent_invoice_query, {"_id": 0}
    ).sort("created_at", -1).limit(8).to_list(8)
    for inv in recent_invoices:
        inv["sale_number"] = inv.get("invoice_number", "")
        inv["total"] = inv.get("grand_total", 0)

    # ── Top products ──────────────────────────────────────────────────────────
    top_inv_pipeline = [
        {"$match": apply_branch_filter({"status": {"$ne": "voided"}}, branch_filter)},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name",
                    "total_qty": {"$sum": "$items.quantity"},
                    "total_revenue": {"$sum": "$items.total"}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products_data = await db.invoices.aggregate(top_inv_pipeline).to_list(5)
    top_products = [
        {"name": p["_id"], "quantity": p["total_qty"], "revenue": round(p["total_revenue"], 2)}
        for p in top_products_data if p["_id"]
    ]

    # ── Net cash flow today ───────────────────────────────────────────────────
    today_net_cash = round(today_cash_sales + today_ar_collected - today_expense_total, 2)

    # ── Branches ─────────────────────────────────────────────────────────────
    user_branches = await get_user_branches(user)
    branches = await db.branches.find(
        {"active": True, "id": {"$in": user_branches}} if user_branches else {"active": True},
        {"_id": 0}
    ).to_list(100)

    return {
        # Meta
        "today": today,
        "day_of_week": now_dt.strftime("%A"),
        "last_close_date": last_close_date,
        "days_since_close": days_since_close,
        # Sales
        "today_revenue": today_revenue,
        "today_sales_count": today_count,
        "today_cash_sales": today_cash_sales,
        "today_credit_sales": today_credit_sales,
        "today_ar_collected": today_ar_collected,
        "today_net_cash": today_net_cash,
        "today_expenses": today_expense_total,
        # Cash position
        "cashier_balance": round(cashier_balance, 2),
        "safe_balance": round(safe_balance, 2),
        "total_cash_position": round(cashier_balance + safe_balance, 2),
        # AR
        "total_receivables": ar_aging["total"],
        "ar_aging": ar_aging,
        "top_debtors": top_debtors,
        "credit_customers_today": credit_customers_today,
        "recent_ar_payments": recent_ar_payments,
        # Inventory
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "total_customers": total_customers,
        # Lists
        "recent_sales": recent_invoices,
        "top_products": top_products,
        "branches": branches,
        "current_branch_filter": branch_id or "all",
        "is_multi_branch_view": user.get("role") == "admin" and not branch_id,
    }


@router.get("/branch-summary")
async def branch_summary(user=Depends(get_current_user)):
    """
    Get summary for all branches the user can access.
    Useful for owner/admin dashboard showing all branches at once.
    """
    user_branches = await get_user_branches(user)
    if not user_branches:
        return {"branches": [], "totals": {}}
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summaries = []
    
    for branch_id in user_branches:
        branch = await db.branches.find_one({"id": branch_id}, {"_id": 0})
        if not branch:
            continue
        
        # Today's revenue for this branch (by order_date)
        today_invoices = await db.invoices.find(
            {"branch_id": branch_id, "status": {"$ne": "voided"}, "order_date": today},
            {"_id": 0, "grand_total": 1, "payment_type": 1}
        ).to_list(10000)
        today_revenue = round(sum(inv.get("grand_total", 0) for inv in today_invoices), 2)
        today_sales_count = len(today_invoices)
        today_cash_sales = round(sum(inv.get("grand_total", 0) for inv in today_invoices if inv.get("payment_type") == "cash"), 2)
        today_new_credit = round(sum(inv.get("grand_total", 0) for inv in today_invoices if inv.get("payment_type") in ("credit", "partial")), 2)

        # AR collected today (payments on older invoices)
        ar_today = await db.invoices.aggregate([
            {"$match": {"branch_id": branch_id, "status": {"$ne": "voided"}, "order_date": {"$ne": today}}},
            {"$unwind": "$payments"},
            {"$match": {"payments.date": today}},
            {"$group": {"_id": None, "total": {"$sum": "$payments.amount"}}}
        ]).to_list(1)
        ar_collected_today = round(ar_today[0]["total"] if ar_today else 0, 2)
        
        # Outstanding receivables for this branch
        rec_result = await db.invoices.aggregate([
            {"$match": {"branch_id": branch_id, "status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
        ]).to_list(1)
        receivables = rec_result[0]["total"] if rec_result else 0
        
        # Today's expenses
        exp_result = await db.expenses.aggregate([
            {"$match": {"branch_id": branch_id, "date": today}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)
        expenses = exp_result[0]["total"] if exp_result else 0
        
        # Cashier wallet balance
        wallet = await db.fund_wallets.find_one(
            {"branch_id": branch_id, "type": "cashier", "active": True},
            {"_id": 0, "balance": 1}
        )
        cashier_balance = wallet.get("balance", 0) if wallet else 0
        
        # Safe balance
        safe = await db.fund_wallets.find_one(
            {"branch_id": branch_id, "type": "safe", "active": True},
            {"_id": 0, "id": 1}
        )
        safe_balance = 0
        if safe:
            lots = await db.safe_lots.find(
                {"wallet_id": safe["id"], "remaining_amount": {"$gt": 0}},
                {"_id": 0, "remaining_amount": 1}
            ).to_list(500)
            safe_balance = sum(lot.get("remaining_amount", 0) for lot in lots)

        # Low stock count for this branch
        low_stock_pipeline = [
            {"$match": {"active": True, "is_repack": {"$ne": True}}},
            {"$lookup": {
                "from": "inventory",
                "let": {"product_id": "$id"},
                "pipeline": [
                    {"$match": {
                        "$expr": {"$eq": ["$product_id", "$$product_id"]},
                        "branch_id": branch_id
                    }}
                ],
                "as": "inv"
            }},
            {"$addFields": {"stock": {"$ifNull": [{"$arrayElemAt": ["$inv.quantity", 0]}, 0]}}},
            {"$match": {"$and": [{"stock": {"$lte": 10}}, {"stock": {"$gte": 0}}]}},
            {"$count": "total"}
        ]
        low_stock_result = await db.products.aggregate(low_stock_pipeline).to_list(1)
        low_stock_count = low_stock_result[0]["total"] if low_stock_result else 0
        
        # Last close date for this branch
        last_close = await db.daily_closings.find_one(
            {"branch_id": branch_id, "status": "closed"}, {"_id": 0, "date": 1},
            sort=[("date", -1)]
        )
        last_close_date = last_close["date"] if last_close else None

        # Determine status
        status = "good"
        if low_stock_count > 10:
            status = "warning"
        if low_stock_count > 20:
            status = "critical"

        summaries.append({
            "id": branch_id,
            "name": branch.get("name", ""),
            "today_revenue": today_revenue,
            "today_sales_count": today_sales_count,
            "today_cash_sales": today_cash_sales,
            "today_new_credit": today_new_credit,
            "ar_collected_today": ar_collected_today,
            "receivables": round(receivables, 2),
            "today_expenses": round(expenses, 2),
            "net_today": round(today_revenue - expenses, 2),
            "cashier_balance": round(cashier_balance, 2),
            "safe_balance": round(safe_balance, 2),
            "total_cash": round(cashier_balance + safe_balance, 2),
            "low_stock_count": low_stock_count,
            "last_close_date": last_close_date,
            "status": status,
        })
    total_revenue = sum(s["today_revenue"] for s in summaries)
    total_receivables = sum(s["receivables"] for s in summaries)
    total_expenses = sum(s["today_expenses"] for s in summaries)
    total_cash = sum(s["total_cash"] for s in summaries)
    total_low_stock = sum(s["low_stock_count"] for s in summaries)
    
    return {
        "branches": summaries,
        "totals": {
            "today_revenue": total_revenue,
            "total_receivables": total_receivables,
            "today_expenses": total_expenses,
            "net_today": total_revenue - total_expenses,
            "total_cash": total_cash,
            "low_stock_count": total_low_stock,
            "branch_count": len(summaries),
        }
    }
