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
        {"$match": {"branch_id": branch_id, "date": date,
                    "payment_method": {"$regex": "^cash$", "$options": "i"}}},
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
            "id": 1, "customer_name": 1, "invoice_number": 1,
            "customer_id": 1,
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
            "invoice_id": p.get("id", ""),
            "customer_id": p.get("customer_id", ""),
            "customer_name": p.get("customer_name", ""),
            "invoice_number": p.get("invoice_number", ""),
            "balance_before": round(current_bal + amount, 2),
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

    # ── Digital payments today (GCash, Maya, etc.) ───────────────────────────
    digital_invoices = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date,
         "fund_source": "digital", "status": {"$ne": "voided"}},
        {"_id": 0, "customer_name": 1, "invoice_number": 1, "grand_total": 1,
         "amount_paid": 1, "digital_platform": 1, "digital_ref_number": 1, "digital_sender": 1}
    ).to_list(500)
    digital_by_platform = {}
    for inv in digital_invoices:
        platform = inv.get("digital_platform", "Digital") or "Digital"
        digital_by_platform[platform] = digital_by_platform.get(platform, 0) + float(inv.get("amount_paid", 0))
    total_digital_today = round(sum(float(inv.get("amount_paid", 0)) for inv in digital_invoices), 2)

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
        # Digital payments today
        "digital_sales_today": [
            {"invoice_number": inv.get("invoice_number"), "customer_name": inv.get("customer_name"),
             "amount": round(float(inv.get("amount_paid", 0)), 2),
             "platform": inv.get("digital_platform", "Digital"),
             "ref_number": inv.get("digital_ref_number", "")}
            for inv in digital_invoices
        ],
        "digital_by_platform": {k: round(v, 2) for k, v in digital_by_platform.items()},
        "total_digital_today": total_digital_today,
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


@router.get("/daily-log")
async def get_daily_log(user=Depends(get_current_user), branch_id: Optional[str] = None, date: Optional[str] = None):
    """
    Get daily sales log split into:
      - cash_entries: sequential cash sales with cash-only running total
      - credit_invoices: today's credit/partial invoices with full item details (for AR section)
      - summary: totals by section and category
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    query = {"date": date}
    if branch_id:
        query["branch_id"] = branch_id

    all_entries = await db.sales_log.find(query, {"_id": 0}).sort("sequence", 1).to_list(10000)

    # Separate cash vs credit entries
    cash_entries = [e for e in all_entries if (e.get("payment_method") or "cash").lower() == "cash"]

    # Compute cash-only running total
    cash_running = 0.0
    for e in cash_entries:
        cash_running += float(e.get("line_total", 0))
        e["cash_running_total"] = round(cash_running, 2)

    # Cash by category
    cash_by_category = {}
    for e in cash_entries:
        cat = e.get("category") or "General"
        cash_by_category[cat] = round(cash_by_category.get(cat, 0.0) + float(e.get("line_total", 0)), 2)
    cash_by_category = dict(sorted(cash_by_category.items(), key=lambda x: -x[1]))

    # Credit/partial invoices with full item details
    inv_query = {"order_date": date, "payment_type": {"$in": ["credit", "partial"]}, "status": {"$ne": "voided"}}
    if branch_id:
        inv_query["branch_id"] = branch_id
    credit_invoices = await db.invoices.find(inv_query, {"_id": 0}).sort("created_at", 1).to_list(500)

    total_cash = round(sum(float(e.get("line_total", 0)) for e in cash_entries), 2)
    total_credit = round(sum(float(inv.get("grand_total", 0)) for inv in credit_invoices), 2)

    return {
        "entries": all_entries,
        "cash_entries": cash_entries,
        "credit_invoices": credit_invoices,
        "date": date,
        "count": len(all_entries),
        "summary": {
            "total_cash": total_cash,
            "total_credit": total_credit,
            "grand_total": round(total_cash + total_credit, 2),
            "cash_count": len(cash_entries),
            "credit_invoice_count": len(credit_invoices),
            "cash_by_category": cash_by_category,
        },
    }


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
    
    # Expenses — split into real P&L expenses vs credit-generating items
    # Credit-generating categories create AR invoices (receivables, not real losses):
    #   "Farm Expense" → farm service billed to customer (invoice created)
    #   "Customer Cash-out" / "Customer Cash Out" → cash given to customer (invoice created)
    #   "Employee Advance" → advance to employee (to be deducted from salary)
    CREDIT_CATEGORIES = {"farm expense", "customer cash-out", "customer cash out", "employee advance"}

    exp_query = {"date": date}
    if branch_id:
        exp_query["branch_id"] = branch_id
    expenses = await db.expenses.find(exp_query, {"_id": 0}).to_list(500)

    real_expenses = []       # Actual P&L expenses (utilities, rent, PO payments, etc.)
    credit_expenses = []     # Credits extended to customers (AR — money comes back)
    advance_expenses = []    # Employee advances (asset — comes back via salary deduction)

    for e in expenses:
        cat = (e.get("category") or "").lower().strip()
        if "employee advance" in cat:
            advance_expenses.append(e)
        elif "farm expense" in cat or "customer cash" in cat:
            credit_expenses.append(e)
        else:
            real_expenses.append(e)

    total_real_expenses = round(sum(float(e.get("amount", 0)) for e in real_expenses), 2)
    total_credit_expenses = round(sum(float(e.get("amount", 0)) for e in credit_expenses), 2)
    total_advance_expenses = round(sum(float(e.get("amount", 0)) for e in advance_expenses), 2)
    # Legacy field: sum of ALL for backward compat
    total_expenses = round(total_real_expenses + total_credit_expenses + total_advance_expenses, 2)
    
    # Also fetch today's AR invoices created from cash outs / farm expenses (for display)
    ar_today_query = {
        "order_date": date,
        "sale_type": {"$in": ["cash_advance", "farm_expense"]},
        "status": {"$ne": "voided"}
    }
    if branch_id:
        ar_today_query["branch_id"] = branch_id
    ar_credits_today = await db.invoices.find(ar_today_query, {"_id": 0,
        "invoice_number": 1, "customer_name": 1, "sale_type": 1, "grand_total": 1}).to_list(200)
    total_ar_credits_today = round(sum(float(inv.get("grand_total", 0)) for inv in ar_credits_today), 2)
    
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
    # Net profit uses ONLY real expenses — credits (AR) and advances are not P&L losses
    net_profit = round(gross_profit - total_real_expenses, 2)
    
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
        # Correct net profit — only real expenses subtracted
        "total_expenses": total_real_expenses,
        "net_profit": net_profit,
        "sales_by_category": sales_by_category,
        # Split expense lists
        "expenses": real_expenses,
        "credit_expenses": credit_expenses,           # Farm + Cash-out (AR — NOT a loss)
        "advance_expenses": advance_expenses,          # Employee advances (asset)
        "total_credit_expenses": total_credit_expenses,
        "total_advance_expenses": total_advance_expenses,
        # AR credits created today from cash outs / farm service (invoice-backed)
        "ar_credits_today": ar_credits_today,
        "total_ar_credits_today": total_ar_credits_today,
        # Legacy sum (all expenses) for any existing UI that needs it
        "total_all_expenses": total_expenses,
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
        {"$match": {"branch_id": branch_id, "date": date,
                    "payment_method": {"$regex": "^cash$", "$options": "i"}}},
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
    variance_notes = data.get("variance_notes", "").strip()

    # ── Credit sales today (new AR created) ───────────────────────────────────
    credit_invoices_today = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date,
         "payment_type": {"$in": ["credit", "partial"]}, "status": {"$ne": "voided"}},
        {"_id": 0, "customer_name": 1, "invoice_number": 1, "grand_total": 1,
         "balance": 1, "payment_type": 1, "sale_type": 1}
    ).to_list(500)
    total_new_credit = round(sum(float(inv.get("grand_total", 0)) for inv in credit_invoices_today), 2)

    # Also get cashouts/farm AR credits
    ar_credits_today = await db.invoices.find(
        {"branch_id": branch_id, "order_date": date,
         "sale_type": {"$in": ["cash_advance", "farm_expense"]}, "status": {"$ne": "voided"}},
        {"_id": 0, "customer_name": 1, "invoice_number": 1, "grand_total": 1, "sale_type": 1}
    ).to_list(200)

    # ── Total outstanding AR at time of close ─────────────────────────────────
    ar_total_result = await db.invoices.aggregate([
        {"$match": {"branch_id": branch_id, "status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(1)
    total_ar_at_close = round(ar_total_result[0]["total"] if ar_total_result else 0, 2)

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
        "variance_notes": variance_notes,
        "cash_to_safe": cash_to_safe,
        "cash_to_drawer": cash_to_drawer,
        # New credit extended today
        "credit_sales_today": [
            {"customer_name": inv["customer_name"], "invoice_number": inv["invoice_number"],
             "grand_total": inv.get("grand_total", 0), "balance": inv.get("balance", 0),
             "type": inv.get("sale_type", "credit")}
            for inv in credit_invoices_today
        ],
        "ar_credits_today": [
            {"customer_name": inv["customer_name"], "invoice_number": inv["invoice_number"],
             "grand_total": inv.get("grand_total", 0), "type": inv.get("sale_type", "")}
            for inv in ar_credits_today
        ],
        "total_new_credit": total_new_credit,
        "total_ar_at_close": total_ar_at_close,
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


@router.get("/daily-variance-history")
async def get_variance_history(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    limit: int = 60,
    skip: int = 0
):
    """
    Historical record of daily over/short (cash variances) for audit purposes.
    Positive over_short = extra cash (possible unrecorded sales).
    Negative over_short = cash short (possible theft, unrecorded expense, or error).
    """
    check_perm(user, "reports", "view")

    query = {"status": "closed"}
    if branch_id:
        query["branch_id"] = branch_id

    total = await db.daily_closings.count_documents(query)
    records = await db.daily_closings.find(
        query,
        {"_id": 0, "id": 1, "date": 1, "branch_id": 1,
         "expected_counter": 1, "actual_cash": 1, "over_short": 1,
         "variance_notes": 1, "closed_by_name": 1, "closed_at": 1,
         "total_cash_sales": 1, "total_ar_received": 1, "total_expenses": 1,
         "starting_float": 1}
    ).sort("date", -1).skip(skip).limit(limit).to_list(limit)

    # Attach branch name
    branch_names = {}
    for r in records:
        bid = r.get("branch_id")
        if bid and bid not in branch_names:
            b = await db.branches.find_one({"id": bid}, {"_id": 0, "name": 1})
            branch_names[bid] = b["name"] if b else bid
        r["branch_name"] = branch_names.get(bid, "")

    return {"records": records, "total": total}



@router.get("/low-stock-alert")
async def get_low_stock_alert(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
):
    """
    Products that ever had inventory added for this branch and are now
    at 0 OR at/below their reorder_point.
    """
    check_perm(user, "inventory", "view")
    if not branch_id:
        branch_id = user.get("branch_id")
    if not branch_id:
        return []

    inv_records = await db.inventory.find(
        {"branch_id": branch_id}, {"_id": 0, "product_id": 1, "quantity": 1}
    ).to_list(10000)

    low_stock = []
    for inv in inv_records:
        qty = float(inv.get("quantity", 0))
        product = await db.products.find_one(
            {"id": inv["product_id"], "active": True, "is_repack": {"$ne": True}},
            {"_id": 0, "id": 1, "name": 1, "sku": 1, "unit": 1, "category": 1,
             "reorder_point": 1, "reorder_quantity": 1}
        )
        if not product:
            continue
        reorder_pt = float(product.get("reorder_point", 0))
        if qty <= 0 or (reorder_pt > 0 and qty <= reorder_pt):
            low_stock.append({
                "product_id": product["id"],
                "sku": product["sku"],
                "name": product["name"],
                "unit": product["unit"],
                "category": product.get("category", "General"),
                "current_qty": qty,
                "reorder_point": reorder_pt,
                "reorder_quantity": product.get("reorder_quantity", 0),
                "status": "out_of_stock" if qty <= 0 else "low_stock",
            })

    low_stock.sort(key=lambda x: (0 if x["status"] == "out_of_stock" else 1, x["name"]))
    return low_stock


@router.get("/supplier-payables")
async def get_supplier_payables(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
):
    """All outstanding unpaid/partially-paid purchase orders, sorted by urgency."""
    check_perm(user, "purchase_orders", "view")
    if not branch_id:
        branch_id = user.get("branch_id")

    query = {
        "payment_status": {"$ne": "paid"},
        "status": {"$in": ["received", "partial", "ordered"]},
    }
    if branch_id:
        query["branch_id"] = branch_id

    pos = await db.purchase_orders.find(query, {"_id": 0}).sort("due_date", 1).to_list(500)
    today = datetime.now(timezone.utc).date()
    result = []
    for po in pos:
        due_str = po.get("due_date", "")
        days_until_due = None
        is_overdue = False
        is_urgent = False
        if due_str:
            try:
                due_d = datetime.strptime(due_str, "%Y-%m-%d").date()
                days_until_due = (due_d - today).days
                is_overdue = days_until_due < 0
                is_urgent = days_until_due < 7
            except Exception:
                pass

        result.append({
            "id": po.get("id", ""),
            "po_number": po.get("po_number", po.get("id", "")[:8].upper()),
            "vendor": po.get("vendor", "Unknown"),
            "purchase_date": po.get("purchase_date", ""),
            "due_date": due_str,
            "subtotal": float(po.get("subtotal", 0)),
            "balance": float(po.get("balance", po.get("subtotal", 0))),
            "status": po.get("status", ""),
            "payment_status": po.get("payment_status", "unpaid"),
            "days_until_due": days_until_due,
            "is_overdue": is_overdue,
            "is_urgent": is_urgent,
        })

    # Sort: overdue first, then by urgency, then by days_until_due
    result.sort(key=lambda x: (
        0 if x["is_overdue"] else (1 if x["is_urgent"] else 2),
        x["days_until_due"] if x["days_until_due"] is not None else 9999
    ))
    return result
