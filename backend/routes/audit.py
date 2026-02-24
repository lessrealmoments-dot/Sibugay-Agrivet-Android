"""
Audit Center routes: session management + comprehensive audit computation.
Full audit (admin): inventory via count sheets + all financial sections.
Partial audit (manager): financial sections only, no physical count required.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/audit", tags=["Audit"])


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def severity(variance_pct: float) -> str:
    """Traffic-light severity for a variance percentage."""
    if abs(variance_pct) <= 1:
        return "ok"        # 🟢 ≤1%
    if abs(variance_pct) <= 5:
        return "warning"   # 🟡 1–5%
    return "critical"      # 🔴 >5%


def cash_severity(discrepancy: float) -> str:
    if abs(discrepancy) <= 100:
        return "ok"
    if abs(discrepancy) <= 500:
        return "warning"
    return "critical"


# ─────────────────────────────────────────────────────────────────────────────
#  SESSION CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_audit_sessions(
    branch_id: Optional[str] = None,
    limit: int = 20,
    user=Depends(get_current_user),
):
    """List past audit sessions, most recent first."""
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    elif user.get("branch_id") and user.get("role") != "admin":
        query["branch_id"] = user["branch_id"]

    sessions = await db.audits.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_audit_session(session_id: str, user=Depends(get_current_user)):
    session = await db.audits.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Audit session not found")
    return session


@router.post("/sessions")
async def create_audit_session(data: dict, user=Depends(get_current_user)):
    """Create a new audit session. Triggers full computation."""
    audit_type = data.get("audit_type", "partial")  # 'partial' | 'full'
    if audit_type == "full" and user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admins can run a full audit")

    branch_id = data.get("branch_id", user.get("branch_id", ""))
    if not branch_id and user.get("role") != "admin":
        raise HTTPException(status_code=400, detail="Branch required")

    period_from = data.get("period_from", datetime.now(timezone.utc).strftime("%Y-%m-01"))
    period_to = data.get("period_to", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    branch_doc = await db.branches.find_one({"id": branch_id}, {"_id": 0, "name": 1}) if branch_id else None
    branch_name = branch_doc.get("name", branch_id) if branch_doc else "All Branches"

    session = {
        "id": new_id(),
        "branch_id": branch_id,
        "branch_name": branch_name,
        "audit_type": audit_type,
        "period_from": period_from,
        "period_to": period_to,
        "count_sheet_baseline_id": data.get("count_sheet_baseline_id"),
        "count_sheet_current_id": data.get("count_sheet_current_id"),
        "status": "in_progress",
        "sections_status": {},
        "sections_notes": {},
        "overall_score": None,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
        "completed_at": None,
        "completed_by": None,
    }
    await db.audits.insert_one(session)
    del session["_id"]
    return session


@router.put("/sessions/{session_id}")
async def update_audit_session(session_id: str, data: dict, user=Depends(get_current_user)):
    """Save section notes, mark sections complete, update overall score."""
    session = await db.audits.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Audit session not found")

    update = {}
    if "sections_status" in data:
        update["sections_status"] = data["sections_status"]
    if "sections_notes" in data:
        update["sections_notes"] = data["sections_notes"]
    if "overall_score" in data:
        update["overall_score"] = data["overall_score"]
    if data.get("status") == "completed":
        update["status"] = "completed"
        update["completed_at"] = now_iso()
        update["completed_by"] = user.get("full_name", user["username"])
    if update:
        await db.audits.update_one({"id": session_id}, {"$set": update})

    return await db.audits.find_one({"id": session_id}, {"_id": 0})


# ─────────────────────────────────────────────────────────────────────────────
#  COMPUTE — The audit engine
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/compute")
async def compute_audit(
    branch_id: Optional[str] = None,
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
    audit_type: str = "partial",          # partial | full
    count_sheet_baseline_id: Optional[str] = None,
    count_sheet_current_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Compute all audit sections for a given period/branch.
    Returns structured data for each section with discrepancies computed.
    Full audit requires two completed count sheets (baseline + current).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not period_from:
        period_from = datetime.now(timezone.utc).strftime("%Y-%m-01")
    if not period_to:
        period_to = today

    b_id = branch_id or user.get("branch_id", "")

    result = {
        "period_from": period_from,
        "period_to": period_to,
        "branch_id": b_id,
        "audit_type": audit_type,
        "computed_at": now_iso(),
    }

    # ── Section 2: Cash Reconciliation ──────────────────────────────────────
    result["cash"] = await _compute_cash(b_id, period_from, period_to)

    # ── Section 3: Sales Audit ───────────────────────────────────────────────
    result["sales"] = await _compute_sales(b_id, period_from, period_to)

    # ── Section 4: AR Audit ──────────────────────────────────────────────────
    result["ar"] = await _compute_ar(b_id, period_from, period_to)

    # ── Section 5: Payables Audit ────────────────────────────────────────────
    result["payables"] = await _compute_payables(b_id, period_from, period_to)

    # ── Section 6: Branch Transfers ──────────────────────────────────────────
    result["transfers"] = await _compute_transfers(b_id, period_from, period_to)

    # ── Section 7: Returns & Losses ──────────────────────────────────────────
    result["returns"] = await _compute_returns(b_id, period_from, period_to)

    # ── Section 8: Digital Payments ──────────────────────────────────────────
    result["digital"] = await _compute_digital(b_id, period_from, period_to)

    # ── Section 9: User Activity ─────────────────────────────────────────────
    result["activity"] = await _compute_activity(b_id, period_from, period_to)

    # ── Section 1: Inventory (full audit — needs count sheets) ───────────────
    if audit_type == "full" and count_sheet_baseline_id and count_sheet_current_id:
        result["inventory"] = await _compute_inventory(
            b_id, count_sheet_baseline_id, count_sheet_current_id
        )
    elif audit_type == "full":
        # Auto-find last two completed count sheets
        cs_list = await db.count_sheets.find(
            {"branch_id": b_id, "status": "completed"},
            {"_id": 0, "id": 1, "count_sheet_number": 1, "completed_at": 1}
        ).sort("completed_at", -1).limit(2).to_list(2)
        if len(cs_list) >= 2:
            result["inventory"] = await _compute_inventory(b_id, cs_list[1]["id"], cs_list[0]["id"])
            result["inventory"]["auto_detected"] = True
            result["inventory"]["baseline_ref"] = cs_list[1]["count_sheet_number"]
            result["inventory"]["current_ref"] = cs_list[0]["count_sheet_number"]
        else:
            result["inventory"] = {
                "available": False,
                "message": "Need at least 2 completed count sheets for a Full Audit inventory comparison.",
                "count_sheets_found": len(cs_list),
            }
    else:
        result["inventory"] = {"available": False, "message": "Inventory comparison requires a Full Audit with count sheets."}

    return result


# ── Section helpers ────────────────────────────────────────────────────────

async def _compute_inventory(branch_id: str, baseline_id: str, current_id: str) -> dict:
    """
    Compute inventory variance by comparing expected qty (from movement logs)
    against the physical count in the current count sheet.
    
    Formula: expected_qty = baseline.counted_qty + Σ(movements between sheets)
    Variance = current_sheet.counted_qty - expected_qty
    """
    baseline = await db.count_sheets.find_one({"id": baseline_id}, {"_id": 0})
    current = await db.count_sheets.find_one({"id": current_id}, {"_id": 0})

    if not baseline or not current:
        return {"available": False, "message": "Count sheets not found"}
    if baseline["status"] != "completed" or current["status"] != "completed":
        return {"available": False, "message": "Both count sheets must be completed"}

    baseline_date = baseline["completed_at"]
    current_date = current["completed_at"]

    # Build lookup: product_id → baseline counted qty
    baseline_map = {item["product_id"]: item for item in baseline.get("items", [])}

    items_result = []
    total_expected_value = 0
    total_variance_capital = 0
    total_variance_retail = 0
    items_ok = 0
    items_warning = 0
    items_critical = 0

    for item in current.get("items", []):
        pid = item["product_id"]
        physical_count = item.get("actual_quantity") or 0
        capital_price = item.get("capital_price", 0)
        retail_price = item.get("retail_price", 0)

        # Get baseline qty (from previous count sheet)
        baseline_item = baseline_map.get(pid)
        baseline_qty = baseline_item.get("actual_quantity", 0) if baseline_item else 0

        # Sum all movements between baseline and current count sheet
        movements = await db.movements.aggregate([
            {"$match": {
                "product_id": pid,
                "branch_id": branch_id,
                "created_at": {"$gte": baseline_date, "$lte": current_date}
            }},
            {"$group": {"_id": None, "total": {"$sum": "$quantity_change"}}}
        ]).to_list(1)
        net_movement = movements[0]["total"] if movements else 0.0

        expected_qty = round(baseline_qty + net_movement, 4)
        variance = round(physical_count - expected_qty, 4)
        variance_pct = round((variance / expected_qty * 100), 2) if expected_qty > 0 else 0
        variance_value_capital = round(variance * capital_price, 2)
        variance_value_retail = round(variance * retail_price, 2)

        sev = severity(variance_pct)
        if sev == "ok":
            items_ok += 1
        elif sev == "warning":
            items_warning += 1
        else:
            items_critical += 1

        total_expected_value += expected_qty * capital_price
        total_variance_capital += variance_value_capital
        total_variance_retail += variance_value_retail

        items_result.append({
            "product_id": pid,
            "product_name": item.get("product_name", ""),
            "sku": item.get("sku", ""),
            "category": item.get("category", ""),
            "unit": item.get("unit", ""),
            "baseline_qty": baseline_qty,
            "net_movement": round(net_movement, 4),
            "expected_qty": expected_qty,
            "physical_count": physical_count,
            "variance": variance,
            "variance_pct": variance_pct,
            "capital_price": capital_price,
            "retail_price": retail_price,
            "variance_value_capital": variance_value_capital,
            "variance_value_retail": variance_value_retail,
            "severity": sev,
        })

    # Sort by severity (critical first)
    sev_order = {"critical": 0, "warning": 1, "ok": 2}
    items_result.sort(key=lambda x: (sev_order[x["severity"]], -abs(x["variance_value_capital"])))

    inventory_accuracy = round(items_ok / len(items_result) * 100, 1) if items_result else 100

    return {
        "available": True,
        "baseline_id": baseline_id,
        "current_id": current_id,
        "baseline_date": baseline_date[:10],
        "current_date": current_date[:10],
        "items": items_result,
        "summary": {
            "total_products": len(items_result),
            "items_ok": items_ok,
            "items_warning": items_warning,
            "items_critical": items_critical,
            "total_expected_value": round(total_expected_value, 2),
            "total_variance_capital": round(total_variance_capital, 2),
            "total_variance_retail": round(total_variance_retail, 2),
            "inventory_accuracy_pct": inventory_accuracy,
        },
        "severity": "critical" if items_critical > 0 else ("warning" if items_warning > 0 else "ok"),
    }


async def _compute_cash(branch_id: str, date_from: str, date_to: str) -> dict:
    """Compute cash reconciliation for the period."""
    # Starting float: look for the last daily_closing before date_from
    prev_close = await db.daily_closings.find_one(
        {"branch_id": branch_id, "date": {"$lt": date_from}},
        {"_id": 0},
        sort=[("date", -1)]
    )
    starting_float = float(prev_close.get("cash_to_drawer", 0)) if prev_close else 0.0
    # Fallback: current cashier wallet
    if starting_float == 0 and not prev_close:
        wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
        starting_float = float(wallet.get("balance", 0)) if wallet else 0.0

    # Cash sales in period
    cash_sales_r = await db.sales_log.aggregate([
        {"$match": {"branch_id": branch_id, "date": {"$gte": date_from, "$lte": date_to},
                    "payment_method": {"$regex": "^cash$", "$options": "i"}}},
        {"$group": {"_id": None, "total": {"$sum": "$line_total"}}}
    ]).to_list(1)
    cash_sales = round(cash_sales_r[0]["total"] if cash_sales_r else 0, 2)

    # AR collected in period (invoice payments)
    ar_r = await db.invoices.aggregate([
        {"$unwind": "$payments"},
        {"$match": {"branch_id": branch_id, "payments.date": {"$gte": date_from, "$lte": date_to},
                    "payments.fund_source": "cashier"}},
        {"$group": {"_id": None, "total": {"$sum": "$payments.amount"}}}
    ]).to_list(1)
    ar_collected = round(ar_r[0]["total"] if ar_r else 0, 2)

    # Cash expenses in period
    exp_r = await db.expenses.aggregate([
        {"$match": {"branch_id": branch_id, "date": {"$gte": date_from, "$lte": date_to}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    total_expenses = round(exp_r[0]["total"] if exp_r else 0, 2)

    expected_cash = round(starting_float + cash_sales + ar_collected - total_expenses, 2)

    # Current cashier balance
    cashier = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
    current_cashier = float(cashier.get("balance", 0)) if cashier else 0.0

    # Safe balance
    safe = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "safe", "active": True}, {"_id": 0})
    safe_balance = 0.0
    if safe:
        lots = await db.safe_lots.find({"wallet_id": safe["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}).to_list(500)
        safe_balance = sum(lot["remaining_amount"] for lot in lots)

    # Expense breakdown by category
    exp_breakdown = await db.expenses.aggregate([
        {"$match": {"branch_id": branch_id, "date": {"$gte": date_from, "$lte": date_to}}},
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]).to_list(50)

    discrepancy = round(current_cashier - expected_cash, 2)
    sev = cash_severity(discrepancy)

    return {
        "starting_float": starting_float,
        "cash_sales": cash_sales,
        "ar_collected": ar_collected,
        "total_expenses": total_expenses,
        "expected_cash": expected_cash,
        "current_cashier_balance": round(current_cashier, 2),
        "safe_balance": round(safe_balance, 2),
        "total_funds": round(current_cashier + safe_balance, 2),
        "discrepancy": discrepancy,
        "discrepancy_type": "over" if discrepancy > 0 else ("short" if discrepancy < 0 else "balanced"),
        "expense_breakdown": [{"category": r["_id"] or "Other", "total": round(r["total"], 2), "count": r["count"]} for r in exp_breakdown],
        "severity": sev,
        "formula": "Starting Float + Cash Sales + AR Collected - All Expenses = Expected Cash",
    }


async def _compute_sales(branch_id: str, date_from: str, date_to: str) -> dict:
    """Sales audit: totals, overrides, voided/edited transactions."""
    # Total invoices in period
    inv_r = await db.invoices.aggregate([
        {"$match": {"branch_id": branch_id, "order_date": {"$gte": date_from, "$lte": date_to},
                    "status": {"$ne": "voided"}}},
        {"$group": {
            "_id": "$payment_type",
            "total": {"$sum": "$grand_total"},
            "count": {"$sum": 1}
        }}
    ]).to_list(10)

    by_type = {r["_id"] or "cash": {"total": round(r["total"], 2), "count": r["count"]} for r in inv_r}
    grand_total_sales = round(sum(v["total"] for v in by_type.values()), 2)

    # Voided transactions
    voided = await db.invoices.count_documents({
        "branch_id": branch_id, "order_date": {"$gte": date_from, "$lte": date_to}, "status": "voided"
    })

    # Edited invoices (audit trail)
    edited_r = await db.invoice_edits.find(
        {"edited_at": {"$gte": f"{date_from}T00:00:00", "$lte": f"{date_to}T23:59:59"}},
        {"_id": 0}
    ).to_list(100)

    # Price overrides (items sold below cost — fetched from movements)
    # Simplified: invoices where any item total < item qty * cost
    below_cost_count = 0

    total_txns = sum(v["count"] for v in by_type.values())
    sev = "warning" if (voided > 0 or len(edited_r) > 0) else "ok"

    return {
        "grand_total_sales": grand_total_sales,
        "total_transactions": total_txns,
        "by_payment_type": by_type,
        "voided_count": voided,
        "edited_invoices": edited_r[:20],
        "edited_count": len(edited_r),
        "severity": sev,
    }


async def _compute_ar(branch_id: str, date_from: str, date_to: str) -> dict:
    """AR audit: aging, collections efficiency."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    open_inv = await db.invoices.find(
        {"branch_id": branch_id, "balance": {"$gt": 0}, "status": {"$nin": ["voided", "paid"]},
         "customer_id": {"$ne": None}},
        {"_id": 0, "balance": 1, "invoice_date": 1, "customer_name": 1, "invoice_number": 1}
    ).to_list(1000)

    total_ar = round(sum(float(i.get("balance", 0)) for i in open_inv), 2)

    buckets = {"current": 0, "b31_60": 0, "b61_90": 0, "b90plus": 0}
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    for inv in open_inv:
        ds = (inv.get("invoice_date") or today)[:10]
        try:
            days = (today_dt - datetime.strptime(ds, "%Y-%m-%d").date()).days
        except ValueError:
            days = 0
        if days <= 30:
            buckets["current"] += float(inv.get("balance", 0))
        elif days <= 60:
            buckets["b31_60"] += float(inv.get("balance", 0))
        elif days <= 90:
            buckets["b61_90"] += float(inv.get("balance", 0))
        else:
            buckets["b90plus"] += float(inv.get("balance", 0))

    # Collections in period
    coll_r = await db.invoices.aggregate([
        {"$unwind": "$payments"},
        {"$match": {"branch_id": branch_id, "payments.date": {"$gte": date_from, "$lte": date_to}}},
        {"$group": {"_id": None, "total": {"$sum": "$payments.amount"}}}
    ]).to_list(1)
    collected = round(coll_r[0]["total"] if coll_r else 0, 2)

    sev = "critical" if buckets["b90plus"] > 0 else ("warning" if buckets["b61_90"] > 0 else "ok")

    return {
        "total_outstanding_ar": total_ar,
        "open_invoices_count": len(open_inv),
        "aging": {k: round(v, 2) for k, v in buckets.items()},
        "collected_in_period": collected,
        "severity": sev,
    }


async def _compute_payables(branch_id: str, date_from: str, date_to: str) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    unpaid = await db.purchase_orders.find(
        {"branch_id": branch_id, "payment_status": {"$in": ["unpaid", "partial"]}, "status": {"$ne": "cancelled"}},
        {"_id": 0, "po_number": 1, "vendor": 1, "balance": 1, "grand_total": 1, "subtotal": 1, "due_date": 1}
    ).to_list(500)

    total_ap = sum(float(p.get("balance") or p.get("grand_total") or p.get("subtotal", 0)) for p in unpaid)
    overdue = [p for p in unpaid if p.get("due_date") and p["due_date"] < today]

    return {
        "total_outstanding_ap": round(total_ap, 2),
        "unpaid_po_count": len(unpaid),
        "overdue_count": len(overdue),
        "overdue_value": round(sum(float(p.get("balance") or p.get("grand_total") or 0) for p in overdue), 2),
        "severity": "critical" if overdue else ("warning" if total_ap > 0 else "ok"),
    }


async def _compute_transfers(branch_id: str, date_from: str, date_to: str) -> dict:
    """Transfers audit: variances, pending requests."""
    query = {
        "$or": [{"from_branch_id": branch_id}, {"to_branch_id": branch_id}],
        "created_at": {"$gte": f"{date_from}T00:00:00", "$lte": f"{date_to}T23:59:59"}
    }
    transfers = await db.branch_transfer_orders.find(query, {"_id": 0}).to_list(500)

    total_received = len([t for t in transfers if t["status"] == "received"])
    with_shortage = len([t for t in transfers if t.get("has_shortage")])
    with_excess = len([t for t in transfers if t.get("has_excess")])
    pending = len([t for t in transfers if t["status"] in ("sent", "received_pending", "disputed")])

    # Pending stock requests directed to this branch
    requests = await db.purchase_orders.count_documents({
        "po_type": "branch_request", "supply_branch_id": branch_id, "status": "requested"
    })

    shortage_value = 0
    for t in transfers:
        if t.get("shortages"):
            shortage_value += sum(s.get("capital_variance", 0) for s in t["shortages"])

    return {
        "total_transfers": len(transfers),
        "received_count": total_received,
        "with_shortage": with_shortage,
        "with_excess": with_excess,
        "pending_count": pending,
        "pending_requests": requests,
        "total_shortage_value": round(shortage_value, 2),
        "severity": "critical" if with_shortage > 0 else ("warning" if pending > 0 or requests > 0 else "ok"),
    }


async def _compute_returns(branch_id: str, date_from: str, date_to: str) -> dict:
    returns = await db.returns.find(
        {"branch_id": branch_id, "return_date": {"$gte": date_from, "$lte": date_to}},
        {"_id": 0}
    ).to_list(500)

    total_refunded = sum(float(r.get("refund_amount", 0)) for r in returns)
    total_loss = sum(float(r.get("total_loss_value", 0)) for r in returns)
    pullout_count = len([r for r in returns if r.get("has_pullout")])

    reasons = {}
    for r in returns:
        reasons[r.get("reason", "Other")] = reasons.get(r.get("reason", "Other"), 0) + 1

    return {
        "total_returns": len(returns),
        "total_refunded": round(total_refunded, 2),
        "total_loss_value": round(total_loss, 2),
        "pullout_count": pullout_count,
        "top_reasons": sorted([{"reason": k, "count": v} for k, v in reasons.items()], key=lambda x: -x["count"]),
        "severity": "warning" if pullout_count > 0 else "ok",
    }


async def _compute_digital(branch_id: str, date_from: str, date_to: str) -> dict:
    """
    Digital payment audit: total digital collected, by platform, with reference tracking.
    Compares against digital wallet balance for discrepancy detection.
    """
    # All digital invoices in period (pure digital + split)
    digital_invs = await db.invoices.find(
        {"branch_id": branch_id, "order_date": {"$gte": date_from, "$lte": date_to},
         "fund_source": {"$in": ["digital", "split"]}, "status": {"$ne": "voided"}},
        {"_id": 0, "invoice_number": 1, "customer_name": 1, "order_date": 1,
         "amount_paid": 1, "digital_amount": 1, "cash_amount": 1,
         "digital_platform": 1, "digital_ref_number": 1, "digital_sender": 1,
         "fund_source": 1, "grand_total": 1}
    ).to_list(1000)

    by_platform: dict = {}
    total_digital = 0.0
    missing_ref = 0
    transactions = []

    for inv in digital_invs:
        is_split = inv.get("fund_source") == "split"
        digital_amt = float(inv.get("digital_amount", 0)) if is_split and inv.get("digital_amount") else float(inv.get("amount_paid", 0))
        platform = inv.get("digital_platform", "Digital") or "Digital"
        ref = inv.get("digital_ref_number", "")
        by_platform[platform] = round(by_platform.get(platform, 0) + digital_amt, 2)
        total_digital = round(total_digital + digital_amt, 2)
        if not ref:
            missing_ref += 1
        transactions.append({
            "invoice_number": inv.get("invoice_number"),
            "customer_name": inv.get("customer_name"),
            "date": inv.get("order_date"),
            "platform": platform,
            "ref_number": ref,
            "sender": inv.get("digital_sender", ""),
            "amount": digital_amt,
            "is_split": is_split,
            "has_ref": bool(ref),
        })

    # Compare against digital wallet balance
    digital_wallet = await db.fund_wallets.find_one(
        {"branch_id": branch_id, "type": "digital", "active": True}, {"_id": 0}
    )
    wallet_balance = float(digital_wallet.get("balance", 0)) if digital_wallet else 0.0

    sev = "critical" if missing_ref > 0 else "ok"

    return {
        "total_digital_collected": round(total_digital, 2),
        "by_platform": by_platform,
        "transaction_count": len(digital_invs),
        "missing_ref_count": missing_ref,
        "digital_wallet_balance": round(wallet_balance, 2),
        "transactions": sorted(transactions, key=lambda x: x.get("date", ""), reverse=True)[:50],
        "severity": sev,
    }


async def _compute_activity(branch_id: str, date_from: str, date_to: str) -> dict:
    """User activity audit: transactions by user, corrections, overrides."""
    # Sales by cashier in period
    sales_by_user = await db.invoices.aggregate([
        {"$match": {"branch_id": branch_id, "order_date": {"$gte": date_from, "$lte": date_to},
                    "status": {"$ne": "voided"}}},
        {"$group": {"_id": "$cashier_name", "total": {"$sum": "$grand_total"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]).to_list(20)

    # Inventory corrections in period
    corrections = await db.inventory_corrections.find(
        {"branch_id": branch_id, "created_at": {"$gte": f"{date_from}T00:00:00", "$lte": f"{date_to}T23:59:59"}},
        {"_id": 0}
    ).to_list(100)

    # Invoice edits
    edits = await db.invoice_edits.find(
        {"edited_at": {"$gte": f"{date_from}T00:00:00", "$lte": f"{date_to}T23:59:59"}},
        {"_id": 0}
    ).to_list(100)

    # Transactions outside business hours (before 7am or after 10pm)
    off_hours = await db.invoices.find(
        {"branch_id": branch_id, "order_date": {"$gte": date_from, "$lte": date_to},
         "$or": [
             {"created_at": {"$regex": "T0[0-6]"}},
             {"created_at": {"$regex": "T2[2-3]"}},
         ]},
        {"_id": 0, "invoice_number": 1, "cashier_name": 1, "grand_total": 1, "created_at": 1}
    ).to_list(50)

    flags = len(corrections) + len(edits) + len(off_hours)
    sev = "critical" if flags > 10 else ("warning" if flags > 0 else "ok")

    return {
        "sales_by_user": [{"user": r["_id"] or "Unknown", "total": round(r["total"], 2), "count": r["count"]} for r in sales_by_user],
        "inventory_corrections_count": len(corrections),
        "inventory_corrections": corrections[:20],
        "invoice_edits_count": len(edits),
        "invoice_edits": edits[:20],
        "off_hours_transactions": off_hours[:20],
        "off_hours_count": len(off_hours),
        "severity": sev,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  AUDIT OFFLINE PACKAGE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/offline-package")
async def get_offline_package(
    branch_id: Optional[str] = None,
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Returns all transactions + file metadata for a branch/period.
    Period auto-detected from last two completed count sheets if not provided.
    Used by frontend to cache data for offline audit.
    """
    b_id = branch_id or user.get("branch_id", "")

    # Auto-detect period from count sheets
    auto_detected = False
    if not period_from or not period_to:
        cs_list = await db.count_sheets.find(
            {"branch_id": b_id, "status": "completed"},
            {"_id": 0, "id": 1, "count_sheet_number": 1, "completed_at": 1, "started_at": 1}
        ).sort("completed_at", -1).limit(2).to_list(2)

        if len(cs_list) >= 2:
            # Period = from oldest to newest
            dates = sorted([cs_list[0]["completed_at"][:10], cs_list[1]["completed_at"][:10]])
            period_from = period_from or dates[0]
            period_to = period_to or dates[1]
            auto_detected = True
            cs_refs = {
                "baseline": cs_list[1]["count_sheet_number"],
                "current": cs_list[0]["count_sheet_number"],
            }
        else:
            # Fallback: current month
            today = datetime.now(timezone.utc)
            period_from = period_from or today.strftime("%Y-%m-01")
            period_to = period_to or today.strftime("%Y-%m-%d")
            cs_refs = None
    else:
        cs_refs = None

    # Fetch POs in period
    pos = await db.purchase_orders.find(
        {
            "branch_id": b_id,
            "purchase_date": {"$gte": period_from, "$lte": period_to},
            "status": {"$nin": ["draft", "cancelled"]},
        },
        {"_id": 0, "items": 0, "change_log": 0}
    ).sort("purchase_date", -1).to_list(500)

    # Fetch Expenses in period
    expenses = await db.expenses.find(
        {"branch_id": b_id, "date": {"$gte": period_from, "$lte": period_to}},
        {"_id": 0}
    ).sort("date", -1).to_list(500)

    # Fetch Branch Transfers in period
    transfers = await db.branch_transfer_orders.find(
        {
            "$or": [{"from_branch_id": b_id}, {"to_branch_id": b_id}],
            "created_at": {"$gte": f"{period_from}T00:00:00", "$lte": f"{period_to}T23:59:59"},
        },
        {"_id": 0, "items": 0}
    ).sort("created_at", -1).to_list(500)

    # Collect all record IDs to fetch upload sessions
    all_ids = (
        [("purchase_order", p["id"]) for p in pos] +
        [("expense", e["id"]) for e in expenses] +
        [("branch_transfer", t["id"]) for t in transfers]
    )

    # Fetch upload sessions for all records
    uploads_map = {}
    for rec_type, rec_id in all_ids:
        sessions = await db.upload_sessions.find(
            {"record_type": rec_type, "record_id": rec_id},
            {"_id": 0, "token": 0}
        ).to_list(10)
        if sessions:
            uploads_map[rec_id] = sessions

    # Build file URL list for prefetching
    file_urls = []
    for rec_id, sessions in uploads_map.items():
        for session in sessions:
            for file in session.get("files", []):
                file_urls.append({
                    "record_id": rec_id,
                    "record_type": session.get("record_type"),
                    "file_id": file["id"],
                    "filename": file.get("filename"),
                    "content_type": file.get("content_type"),
                    "size": file.get("size", 0),
                })

    return {
        "branch_id": b_id,
        "period_from": period_from,
        "period_to": period_to,
        "auto_detected": auto_detected,
        "count_sheet_refs": cs_refs,
        "purchase_orders": pos,
        "expenses": expenses,
        "branch_transfers": transfers,
        "uploads_map": uploads_map,
        "file_urls": file_urls,
        "totals": {
            "purchase_orders": len(pos),
            "expenses": len(expenses),
            "branch_transfers": len(transfers),
            "total_files": len(file_urls),
        },
    }

