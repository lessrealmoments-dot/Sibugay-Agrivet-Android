"""
Reports routes: AR Aging, Sales Report, Expense Report.
"""
from fastapi import APIRouter, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import get_current_user, check_perm, get_branch_filter, apply_branch_filter

router = APIRouter(tags=["Reports"])


# ==================== AR AGING REPORT ====================
@router.get("/reports/ar-aging")
async def ar_aging_report(
    branch_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    AR Aging Report: open invoice balances bucketed by age.
    Buckets: Current (0-30d), 31-60d, 61-90d, 90+d from today.
    """
    check_perm(user, "reports", "view")

    query = {
        "customer_id": {"$ne": None},
        "balance": {"$gt": 0},
        "status": {"$nin": ["voided", "paid"]},
    }
    branch_filter = await get_branch_filter(user, branch_id)
    query = apply_branch_filter(query, branch_filter)

    invoices = await db.invoices.find(query, {"_id": 0}).to_list(2000)

    today = datetime.now(timezone.utc).date()

    # Per-customer map: { customer_id: { name, buckets, invoices } }
    customers = {}

    totals = {"current": 0.0, "b31_60": 0.0, "b61_90": 0.0, "b90plus": 0.0, "total": 0.0}

    for inv in invoices:
        cid = inv.get("customer_id", "")
        cname = inv.get("customer_name", "Unknown")

        # Use invoice_date or order_date to compute age
        date_str = inv.get("invoice_date") or inv.get("order_date") or inv.get("created_at", "")[:10]
        try:
            inv_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            days_old = (today - inv_date).days
        except (ValueError, TypeError):
            days_old = 0

        balance = float(inv.get("balance", 0))

        # Bucket assignment
        if days_old <= 30:
            bucket = "current"
        elif days_old <= 60:
            bucket = "b31_60"
        elif days_old <= 90:
            bucket = "b61_90"
        else:
            bucket = "b90plus"

        if cid not in customers:
            customers[cid] = {
                "customer_id": cid,
                "customer_name": cname,
                "current": 0.0,
                "b31_60": 0.0,
                "b61_90": 0.0,
                "b90plus": 0.0,
                "total": 0.0,
                "invoices": [],
            }

        customers[cid][bucket] = round(customers[cid][bucket] + balance, 2)
        customers[cid]["total"] = round(customers[cid]["total"] + balance, 2)
        customers[cid]["invoices"].append({
            "invoice_number": inv.get("invoice_number", ""),
            "invoice_date": date_str[:10],
            "due_date": inv.get("due_date", ""),
            "grand_total": inv.get("grand_total", 0),
            "amount_paid": inv.get("amount_paid", 0),
            "balance": balance,
            "days_old": days_old,
            "bucket": bucket,
            "sale_type": inv.get("sale_type", "walk_in"),
        })

        totals[bucket] = round(totals[bucket] + balance, 2)
        totals["total"] = round(totals["total"] + balance, 2)

    rows = sorted(customers.values(), key=lambda x: x["total"], reverse=True)

    return {
        "as_of_date": today.isoformat(),
        "totals": totals,
        "rows": rows,
        "branch_filter": branch_id,
    }


# ==================== SALES REPORT ====================
@router.get("/reports/sales")
async def sales_report(
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Sales Report: totals by category, by payment type, and per-transaction.
    Uses sales_log for category breakdown. Uses invoices for transaction list.
    """
    check_perm(user, "reports", "view")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not date_from:
        # Default: first day of current month
        date_from = datetime.now(timezone.utc).strftime("%Y-%m-01")
    if not date_to:
        date_to = today

    # ── Category breakdown from sales_log ─────────────────────────────────
    log_query = {"date": {"$gte": date_from, "$lte": date_to}}
    if branch_id:
        log_query["branch_id"] = branch_id

    cat_pipeline = [
        {"$match": log_query},
        {"$group": {
            "_id": {"category": "$category", "payment_method": "$payment_method"},
            "total": {"$sum": "$line_total"},
            "qty": {"$sum": "$quantity"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"total": -1}},
    ]
    cat_results = await db.sales_log.aggregate(cat_pipeline).to_list(500)

    # Restructure: { category -> { total, qty, by_payment } }
    cat_map = {}
    payment_totals = {}
    for r in cat_results:
        cat = r["_id"]["category"] or "General"
        pay = (r["_id"]["payment_method"] or "cash").lower()
        total = round(r["total"], 2)
        qty = r["qty"]

        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "total": 0.0, "qty": 0, "by_payment": {}}
        cat_map[cat]["total"] = round(cat_map[cat]["total"] + total, 2)
        cat_map[cat]["qty"] += qty
        cat_map[cat]["by_payment"][pay] = round(cat_map[cat]["by_payment"].get(pay, 0) + total, 2)

        payment_totals[pay] = round(payment_totals.get(pay, 0) + total, 2)

    categories = sorted(cat_map.values(), key=lambda x: x["total"], reverse=True)
    grand_total = round(sum(c["total"] for c in categories), 2)

    # ── Daily breakdown ────────────────────────────────────────────────────
    day_pipeline = [
        {"$match": log_query},
        {"$group": {"_id": "$date", "total": {"$sum": "$line_total"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    day_results = await db.sales_log.aggregate(day_pipeline).to_list(365)
    daily = [{"date": r["_id"], "total": round(r["total"], 2), "count": r["count"]} for r in day_results]

    # ── Transaction list from invoices ─────────────────────────────────────
    inv_query = {
        "order_date": {"$gte": date_from, "$lte": date_to},
        "status": {"$ne": "voided"},
        "sale_type": {"$nin": ["interest_charge", "penalty_charge"]},
    }
    if branch_id:
        inv_query["branch_id"] = branch_id

    invoices = await db.invoices.find(inv_query, {"_id": 0}).sort("order_date", -1).to_list(1000)
    transactions = []
    for inv in invoices:
        transactions.append({
            "invoice_number": inv.get("invoice_number", ""),
            "date": inv.get("order_date", ""),
            "customer_name": inv.get("customer_name", "Walk-in"),
            "payment_type": inv.get("payment_type", "cash"),
            "grand_total": inv.get("grand_total", 0),
            "amount_paid": inv.get("amount_paid", 0),
            "balance": inv.get("balance", 0),
            "status": inv.get("status", ""),
            "items_count": len(inv.get("items", [])),
            "cashier_name": inv.get("cashier_name", ""),
            "sale_type": inv.get("sale_type", "walk_in"),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "grand_total": grand_total,
        "categories": categories,
        "payment_totals": payment_totals,
        "daily": daily,
        "transactions": transactions,
    }


# ==================== EXPENSE REPORT ====================
@router.get("/reports/expenses")
async def expense_report(
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Expense Report: totals by category and per-transaction detail.
    """
    check_perm(user, "reports", "view")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not date_from:
        date_from = datetime.now(timezone.utc).strftime("%Y-%m-01")
    if not date_to:
        date_to = today

    query = {"date": {"$gte": date_from, "$lte": date_to}, "voided": {"$ne": True}}
    if branch_id:
        query["branch_id"] = branch_id
    if category:
        query["category"] = category

    # ── Category totals ────────────────────────────────────────────────────
    cat_pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$category",
            "total": {"$sum": "$amount"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"total": -1}},
    ]
    cat_results = await db.expenses.aggregate(cat_pipeline).to_list(100)
    categories = [
        {"category": r["_id"] or "Miscellaneous", "total": round(r["total"], 2), "count": r["count"]}
        for r in cat_results
    ]
    grand_total = round(sum(c["total"] for c in categories), 2)

    # ── Daily breakdown ────────────────────────────────────────────────────
    day_pipeline = [
        {"$match": query},
        {"$group": {"_id": "$date", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    day_results = await db.expenses.aggregate(day_pipeline).to_list(365)
    daily = [{"date": r["_id"], "total": round(r["total"], 2), "count": r["count"]} for r in day_results]

    # ── Transaction detail ─────────────────────────────────────────────────
    expenses = await db.expenses.find(query, {"_id": 0}).sort("date", -1).to_list(2000)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "grand_total": grand_total,
        "categories": categories,
        "daily": daily,
        "expenses": expenses,
    }
