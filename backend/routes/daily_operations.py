"""
Daily operations routes: Sales log, daily reports, close accounts.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import get_current_user, check_perm, now_iso, new_id, get_branch_filter, apply_branch_filter

router = APIRouter(tags=["Daily Operations"])


@router.get("/daily-close-preview")
async def get_daily_close_preview(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Full Z-Report preview data for day close.
    Returns all sections needed for the cash reconciliation form.
    """
    check_perm(user, "reports", "view")
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not branch_id:
        branch_id = user.get("branch_id")

    month_prefix = date[:7]  # "YYYY-MM"

    # ── Starting float: yesterday's cash_to_drawer ───────────────────────────
    yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_close = await db.daily_closings.find_one(
        {"date": yesterday, "branch_id": branch_id}, {"_id": 0}
    )
    if prev_close:
        starting_float = float(prev_close.get("cash_to_drawer", 0))
    else:
        wallet = await db.fund_wallets.find_one(
            {"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0}
        )
        starting_float = float(wallet["balance"]) if wallet else 0.0

    # ── Safe balance (informational) ─────────────────────────────────────────
    safe = await db.fund_wallets.find_one(
        {"branch_id": branch_id, "type": "safe", "active": True}, {"_id": 0}
    )
    safe_balance = 0.0
    if safe:
        lots = await db.safe_lots.find(
            {"wallet_id": safe["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}
        ).to_list(500)
        safe_balance = sum(l["remaining_amount"] for l in lots)

    # ── Cash sales today (payment_type=cash, by category) ────────────────────
    cash_sales_pipeline = [
        {"$match": {"branch_id": branch_id, "date": date, "payment_method": "cash"}},
        {"$group": {"_id": "$category", "total": {"$sum": "$line_total"}, "qty": {"$sum": "$quantity"}}},
        {"$sort": {"total": -1}},
    ]
    cat_results = await db.sales_log.aggregate(cash_sales_pipeline).to_list(100)
    cash_sales_by_category = [
        {"category": r["_id"] or "General", "total": round(r["total"], 2), "qty": r["qty"]}
        for r in cat_results
    ]
    total_cash_sales = round(sum(c["total"] for c in cash_sales_by_category), 2)

    # Also include partial-sale cash received today (amount_paid from partial invoices)
    partial_invoices = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date,
         "payment_type": "partial", "status": {"$ne": "voided"}},
        {"_id": 0, "customer_name": 1, "invoice_number": 1, "amount_paid": 1, "grand_total": 1}
    ).to_list(500)
    total_partial_cash = round(sum(float(inv.get("amount_paid", 0)) for inv in partial_invoices), 2)

    # ── New credit sales today (info only — not cash) ─────────────────────────
    credit_invoices = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date,
         "payment_type": "credit", "status": {"$ne": "voided"}},
        {"_id": 0, "customer_name": 1, "invoice_number": 1, "grand_total": 1, "balance": 1}
    ).to_list(500)
    credit_sales_today = [
        {"customer_name": inv["customer_name"], "invoice_number": inv["invoice_number"],
         "grand_total": inv.get("grand_total", 0), "balance": inv.get("balance", 0)}
        for inv in credit_invoices
    ]
    total_credit_today = round(sum(c["grand_total"] for c in credit_sales_today), 2)

    # ── AR payments received today (on OLDER invoices) ───────────────────────
    ar_pipeline = [
        {"$match": {"branch_id": branch_id, "status": {"$ne": "voided"},
                    "order_date": {"$ne": date}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": date}},
        {"$project": {
            "_id": 0,
            "customer_name": 1, "invoice_number": 1,
            "balance": 1,  # current balance after all payments
            "payment": "$payments"
        }}
    ]
    ar_payments_raw = await db.invoices.aggregate(ar_pipeline).to_list(500)
    ar_payments = []
    for p in ar_payments_raw:
        pmt = p.get("payment", {})
        amount = float(pmt.get("amount", 0))
        interest_paid = float(pmt.get("applied_to_interest", 0))
        penalty_paid = float(pmt.get("applied_to_penalty", 0))
        principal_paid = float(pmt.get("applied_to_principal", amount - interest_paid - penalty_paid))
        current_bal = float(p.get("balance", 0))
        ar_payments.append({
            "customer_name": p.get("customer_name", ""),
            "invoice_number": p.get("invoice_number", ""),
            "balance_before": round(current_bal + amount, 2),  # approx before this payment
            "interest_paid": round(interest_paid, 2),
            "penalty_paid": round(penalty_paid, 2),
            "principal_paid": round(principal_paid, 2),
            "amount_paid": round(amount, 2),
            "remaining_balance": round(current_bal, 2),
        })
    total_ar_received = round(sum(p["amount_paid"] for p in ar_payments), 2)

    # ── Expenses today (all = cash outflows) ─────────────────────────────────
    expenses_raw = await db.expenses.find(
        {"branch_id": branch_id, "date": date}, {"_id": 0}
    ).to_list(500)

    # For Employee Advance expenses: add monthly running total
    expenses = []
    for e in expenses_raw:
        exp = dict(e)
        if e.get("category") == "Employee Advance" and e.get("employee_id"):
            month_total_pipeline = [
                {"$match": {
                    "branch_id": branch_id,
                    "category": "Employee Advance",
                    "employee_id": e["employee_id"],
                    "date": {"$gte": f"{month_prefix}-01", "$lte": f"{month_prefix}-31"}
                }},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            month_res = await db.expenses.aggregate(month_total_pipeline).to_list(1)
            exp["monthly_ca_total"] = round(month_res[0]["total"] if month_res else 0, 2)
        expenses.append(exp)

    total_expenses = round(sum(float(e.get("amount", 0)) for e in expenses), 2)

    # ── Expected counter ──────────────────────────────────────────────────────
    # starting_float + all_cash_received_today - cash_expenses
    total_cash_in = total_cash_sales + total_partial_cash + total_ar_received
    expected_counter = round(starting_float + total_cash_in - total_expenses, 2)

    return {
        "date": date,
        "branch_id": branch_id,
        # Opening
        "starting_float": starting_float,
        "safe_balance": round(safe_balance, 2),
        # Cash inflows
        "cash_sales_by_category": cash_sales_by_category,
        "total_cash_sales": total_cash_sales,
        "partial_invoices": [
            {"customer_name": inv["customer_name"],
             "invoice_number": inv["invoice_number"],
             "amount_paid": round(float(inv.get("amount_paid", 0)), 2),
             "grand_total": round(float(inv.get("grand_total", 0)), 2)}
            for inv in partial_invoices
        ],
        "total_partial_cash": total_partial_cash,
        # AR collections
        "ar_payments": ar_payments,
        "total_ar_received": total_ar_received,
        # Credit today (info)
        "credit_sales_today": credit_sales_today,
        "total_credit_today": total_credit_today,
        # Expenses
        "expenses": expenses,
        "total_expenses": total_expenses,
        # Summary
        "total_cash_in": round(total_cash_in, 2),
        "expected_counter": expected_counter,
    }

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
    """Close accounts for a day. Requires admin PIN verification."""
    check_perm(user, "reports", "close_day")

    date = data["date"]
    branch_id = data["branch_id"]

    # Admin PIN required for day close
    admin_pin = data.get("admin_pin", "")
    if user.get("role") != "admin":
        if not admin_pin:
            raise HTTPException(status_code=403, detail="Admin PIN required to close the day")
        admin = await db.users.find_one({"role": "admin", "active": True}, {"_id": 0})
        if not admin:
            raise HTTPException(status_code=403, detail="No admin user found")
        admin_stored_pin = admin.get("manager_pin", "") or admin.get("password_hash", "")[-4:]
        if admin_pin != admin_stored_pin:
            raise HTTPException(status_code=403, detail="Invalid admin PIN")

    existing = await db.daily_closings.find_one(
        {"date": date, "branch_id": branch_id, "status": "closed"}, {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Day already closed")

    # Pull all data (reuse preview logic)
    from datetime import timedelta
    month_prefix = date[:7]
    yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_close = await db.daily_closings.find_one({"date": yesterday, "branch_id": branch_id}, {"_id": 0})
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
    starting_float = float(prev_close.get("cash_to_drawer", 0)) if prev_close else float(wallet["balance"] if wallet else 0)

    safe = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "safe", "active": True}, {"_id": 0})
    safe_balance = 0.0
    if safe:
        lots = await db.safe_lots.find({"wallet_id": safe["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}).to_list(500)
        safe_balance = sum(l["remaining_amount"] for l in lots)

    cash_sales_agg = await db.sales_log.aggregate([
        {"$match": {"branch_id": branch_id, "date": date, "payment_method": "cash"}},
        {"$group": {"_id": "$category", "total": {"$sum": "$line_total"}}}
    ]).to_list(100)
    sales_by_category = {r["_id"] or "General": round(r["total"], 2) for r in cash_sales_agg}
    total_cash_sales = round(sum(sales_by_category.values()), 2)

    partial_total = 0.0
    partial_invoices = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date, "payment_type": "partial", "status": {"$ne": "voided"}},
        {"_id": 0, "amount_paid": 1}
    ).to_list(500)
    partial_total = round(sum(float(inv.get("amount_paid", 0)) for inv in partial_invoices), 2)

    ar_pipeline = [
        {"$match": {"branch_id": branch_id, "status": {"$ne": "voided"}, "order_date": {"$ne": date}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": date}},
        {"$project": {"_id": 0, "customer_name": 1, "invoice_number": 1, "balance": 1, "payment": "$payments"}}
    ]
    ar_raw = await db.invoices.aggregate(ar_pipeline).to_list(500)
    credit_collections = []
    for p in ar_raw:
        pmt = p.get("payment", {})
        amount = float(pmt.get("amount", 0))
        interest_paid = float(pmt.get("applied_to_interest", 0))
        penalty_paid = float(pmt.get("applied_to_penalty", 0))
        principal_paid = float(pmt.get("applied_to_principal", amount - interest_paid - penalty_paid))
        credit_collections.append({
            "customer": p.get("customer_name", ""),
            "invoice": p.get("invoice_number", ""),
            "balance_before": round(float(p.get("balance", 0)) + amount, 2),
            "interest_paid": round(interest_paid, 2),
            "penalty_paid": round(penalty_paid, 2),
            "principal_paid": round(principal_paid, 2),
            "total_paid": round(amount, 2),
            "balance": round(float(p.get("balance", 0)), 2),
        })
    total_ar_received = round(sum(c["total_paid"] for c in credit_collections), 2)

    expenses_raw = await db.expenses.find({"branch_id": branch_id, "date": date}, {"_id": 0}).to_list(500)
    expenses = []
    for e in expenses_raw:
        exp = dict(e)
        if e.get("category") == "Employee Advance" and e.get("employee_id"):
            month_res = await db.expenses.aggregate([
                {"$match": {"branch_id": branch_id, "category": "Employee Advance",
                            "employee_id": e["employee_id"],
                            "date": {"$gte": f"{month_prefix}-01", "$lte": f"{month_prefix}-31"}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]).to_list(1)
            exp["monthly_ca_total"] = round(month_res[0]["total"] if month_res else 0, 2)
        expenses.append(exp)
    total_expenses = round(sum(float(e.get("amount", 0)) for e in expenses), 2)

    total_cash_in = total_cash_sales + partial_total + total_ar_received
    expected_counter = round(starting_float + total_cash_in - total_expenses, 2)

    actual_cash = float(data.get("actual_cash", 0))
    cash_to_safe = float(data.get("cash_to_safe", 0))
    cash_to_drawer = float(data.get("cash_to_drawer", 0))
    over_short = round(actual_cash - expected_counter, 2)

    close_record = {
        "id": new_id(), "branch_id": branch_id, "date": date, "status": "closed",
        "starting_float": starting_float,
        "safe_balance": round(safe_balance, 2),
        "sales_by_category": sales_by_category,
        "total_cash_sales": total_cash_sales,
        "total_partial_cash": partial_total,
        "credit_collections": credit_collections,
        "total_ar_received": total_ar_received,
        "total_expenses": total_expenses,
        "expenses": expenses,
        "total_cash_in": round(total_cash_in, 2),
        "expected_counter": expected_counter,
        "actual_cash": actual_cash,
        "over_short": over_short,
        "cash_to_safe": cash_to_safe,
        "cash_to_drawer": cash_to_drawer,
        "closed_by": user["id"],
        "closed_by_name": user.get("full_name", user["username"]),
        "closed_at": now_iso(),
    }

    await db.daily_closings.insert_one(close_record)
    del close_record["_id"]

    # Update cashier wallet to new float
    if wallet:
        await db.fund_wallets.update_one({"id": wallet["id"]}, {"$set": {"balance": cash_to_drawer}})

    # Add cash_to_safe to safe
    if cash_to_safe > 0 and safe:
        await db.safe_lots.insert_one({
            "id": new_id(), "branch_id": branch_id, "wallet_id": safe["id"],
            "date_received": date, "original_amount": cash_to_safe,
            "remaining_amount": cash_to_safe,
            "source_reference": f"Day close {date}",
            "created_by": user["id"], "created_at": now_iso()
        })

    return close_record
    
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
