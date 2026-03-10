"""
Universal Transaction Search — search across all transaction types.
Supports: invoices, purchase orders, expenses, internal invoices, fund transfers, payments.
"""
from fastapi import APIRouter, Depends
from typing import Optional
from config import db
from utils import (
    get_current_user,
    get_branch_filter, apply_branch_filter,
)

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/transactions")
async def search_transactions(
    q: str = "",
    type: Optional[str] = "all",
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    user=Depends(get_current_user),
):
    """
    Universal transaction search.
    q: search term (matches number, customer/vendor name, description)
    type: all | invoice | po | expense | internal_invoice | fund_transfer
    """
    results = []
    branch_filter = await get_branch_filter(user, branch_id)

    if not q and not date_from and not date_to:
        return {"results": [], "total": 0}

    # Build text search conditions
    text_conditions = []
    if q:
        regex = {"$regex": q, "$options": "i"}
        text_conditions = [regex]

    per_type_limit = limit if type != "all" else max(limit // 5, 10)

    # ── Invoices / Sales ─────────────────────────────────────────────────
    if type in ("all", "invoice", "sale"):
        query = {"status": {"$ne": "voided"}}
        query = apply_branch_filter(query, branch_filter)
        if text_conditions:
            query["$or"] = [
                {"invoice_number": text_conditions[0]},
                {"customer_name": text_conditions[0]},
                {"customer_contact": text_conditions[0]},
            ]
        if date_from:
            query.setdefault("order_date", {})["$gte"] = date_from
        if date_to:
            query.setdefault("order_date", {})["$lte"] = date_to

        invoices = await db.invoices.find(
            query,
            {"_id": 0, "id": 1, "invoice_number": 1, "customer_name": 1,
             "grand_total": 1, "balance": 1, "payment_type": 1, "status": 1,
             "order_date": 1, "branch_id": 1, "created_at": 1, "fund_source": 1,
             "sale_type": 1, "prefix": 1}
        ).sort("created_at", -1).limit(per_type_limit).to_list(per_type_limit)

        for inv in invoices:
            results.append({
                "type": "invoice",
                "id": inv["id"],
                "number": inv.get("invoice_number", ""),
                "title": inv.get("customer_name", "Walk-in"),
                "amount": inv.get("grand_total", 0),
                "balance": inv.get("balance", 0),
                "status": inv.get("status", ""),
                "date": inv.get("order_date", ""),
                "branch_id": inv.get("branch_id", ""),
                "sub_type": inv.get("sale_type", inv.get("prefix", "")),
                "created_at": inv.get("created_at", ""),
            })

    # ── Purchase Orders ──────────────────────────────────────────────────
    if type in ("all", "po", "purchase_order"):
        query = {}
        query = apply_branch_filter(query, branch_filter)
        if text_conditions:
            query["$or"] = [
                {"po_number": text_conditions[0]},
                {"vendor": text_conditions[0]},
                {"dr_number": text_conditions[0]},
            ]
        if date_from:
            query.setdefault("purchase_date", {})["$gte"] = date_from
        if date_to:
            query.setdefault("purchase_date", {})["$lte"] = date_to

        pos = await db.purchase_orders.find(
            query,
            {"_id": 0, "id": 1, "po_number": 1, "vendor": 1, "grand_total": 1,
             "balance": 1, "status": 1, "payment_status": 1,
             "purchase_date": 1, "branch_id": 1, "created_at": 1, "dr_number": 1}
        ).sort("created_at", -1).limit(per_type_limit).to_list(per_type_limit)

        for po in pos:
            results.append({
                "type": "purchase_order",
                "id": po["id"],
                "number": po.get("po_number", ""),
                "title": po.get("vendor", ""),
                "amount": po.get("grand_total", 0),
                "balance": po.get("balance", 0),
                "status": po.get("status", ""),
                "date": po.get("purchase_date", ""),
                "branch_id": po.get("branch_id", ""),
                "sub_type": "PO",
                "created_at": po.get("created_at", ""),
            })

    # ── Expenses ─────────────────────────────────────────────────────────
    if type in ("all", "expense"):
        query = {"voided": {"$ne": True}}
        query = apply_branch_filter(query, branch_filter)
        if text_conditions:
            query["$or"] = [
                {"description": text_conditions[0]},
                {"category": text_conditions[0]},
                {"vendor_name": text_conditions[0]},
                {"reference_number": text_conditions[0]},
            ]
        if date_from:
            query.setdefault("date", {})["$gte"] = date_from
        if date_to:
            query.setdefault("date", {})["$lte"] = date_to

        expenses = await db.expenses.find(
            query,
            {"_id": 0, "id": 1, "description": 1, "category": 1, "amount": 1,
             "date": 1, "branch_id": 1, "created_at": 1, "fund_source": 1,
             "vendor_name": 1, "reference_number": 1,
             "linked_invoice_number": 1}
        ).sort("created_at", -1).limit(per_type_limit).to_list(per_type_limit)

        for exp in expenses:
            results.append({
                "type": "expense",
                "id": exp["id"],
                "number": exp.get("linked_invoice_number") or exp.get("reference_number") or "",
                "title": exp.get("description", exp.get("category", "")),
                "amount": exp.get("amount", 0),
                "balance": 0,
                "status": exp.get("category", ""),
                "date": exp.get("date", ""),
                "branch_id": exp.get("branch_id", ""),
                "sub_type": exp.get("category", "Expense"),
                "created_at": exp.get("created_at", ""),
            })

    # ── Internal Invoices ────────────────────────────────────────────────
    if type in ("all", "internal_invoice"):
        query = {}
        if text_conditions:
            query["$or"] = [
                {"invoice_number": text_conditions[0]},
                {"from_branch_name": text_conditions[0]},
                {"to_branch_name": text_conditions[0]},
            ]
        if date_from:
            query.setdefault("created_at", {})["$gte"] = f"{date_from}T00:00:00"
        if date_to:
            query.setdefault("created_at", {})["$lte"] = f"{date_to}T23:59:59"

        int_invoices = await db.internal_invoices.find(
            query,
            {"_id": 0, "id": 1, "invoice_number": 1, "from_branch_name": 1,
             "to_branch_name": 1, "grand_total": 1, "balance": 1,
             "status": 1, "created_at": 1, "from_branch_id": 1, "to_branch_id": 1}
        ).sort("created_at", -1).limit(per_type_limit).to_list(per_type_limit)

        for ii in int_invoices:
            results.append({
                "type": "internal_invoice",
                "id": ii["id"],
                "number": ii.get("invoice_number", ""),
                "title": f"{ii.get('from_branch_name', '')} → {ii.get('to_branch_name', '')}",
                "amount": ii.get("grand_total", 0),
                "balance": ii.get("balance", 0),
                "status": ii.get("status", ""),
                "date": (ii.get("created_at") or "")[:10],
                "branch_id": ii.get("to_branch_id", ""),
                "sub_type": "Internal",
                "created_at": ii.get("created_at", ""),
            })

    # ── Fund Transfers ───────────────────────────────────────────────────
    if type in ("all", "fund_transfer"):
        query = {}
        query = apply_branch_filter(query, branch_filter)
        if text_conditions:
            query["$or"] = [
                {"note": text_conditions[0]},
                {"transfer_type": text_conditions[0]},
                {"authorized_by": text_conditions[0]},
            ]
        if date_from:
            query.setdefault("date", {})["$gte"] = date_from
        if date_to:
            query.setdefault("date", {})["$lte"] = date_to

        transfers = await db.fund_transfers.find(
            query,
            {"_id": 0, "id": 1, "transfer_type": 1, "amount": 1, "note": 1,
             "date": 1, "branch_id": 1, "created_at": 1, "authorized_by": 1,
             "target_wallet": 1}
        ).sort("created_at", -1).limit(per_type_limit).to_list(per_type_limit)

        for ft in transfers:
            label = (ft.get("transfer_type") or "").replace("_", " ").title()
            results.append({
                "type": "fund_transfer",
                "id": ft.get("id", ""),
                "number": "",
                "title": f"{label}: {ft.get('note', '')}",
                "amount": ft.get("amount", 0),
                "balance": 0,
                "status": ft.get("transfer_type", ""),
                "date": ft.get("date", (ft.get("created_at") or "")[:10]),
                "branch_id": ft.get("branch_id", ""),
                "sub_type": label,
                "created_at": ft.get("created_at", ""),
            })

    # Sort all results by created_at descending
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"results": results[:limit], "total": len(results)}
