"""
Dashboard routes: statistics, summaries, multi-branch overview.
Supports multi-branch data isolation with owner cross-branch views.
"""
from fastapi import APIRouter, Depends
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import (
    get_current_user, get_branch_filter, apply_branch_filter, 
    get_user_branches, get_default_branch
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def dashboard_stats(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None
):
    """
    Get dashboard statistics. Respects branch isolation.
    - Admin/Owner: Can see all branches or filter by specific branch
    - Regular users: Only see their assigned branch
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Get branch filter based on user access
    branch_filter = await get_branch_filter(user, branch_id)
    
    # Today's sales from invoices
    invoice_query = {"status": {"$ne": "voided"}, "created_at": {"$gte": today}}
    invoice_query = apply_branch_filter(invoice_query, branch_filter)
    
    today_invoices = await db.invoices.find(invoice_query, {"_id": 0}).to_list(10000)
    today_revenue = sum(inv.get("grand_total", 0) for inv in today_invoices)
    today_count = len(today_invoices)
    
    # Also check legacy sales collection
    sales_query = {"status": "completed", "created_at": {"$gte": today}}
    sales_query = apply_branch_filter(sales_query, branch_filter)
    today_sales = await db.sales.find(sales_query, {"_id": 0}).to_list(10000)
    today_revenue += sum(s.get("total", 0) for s in today_sales)
    today_count += len(today_sales)
    
    # Total products (global - not branch-specific)
    total_products = await db.products.count_documents({"active": True})
    
    # Low stock check (branch-specific inventory)
    low_stock_pipeline = [
        {"$match": {"active": True}},
        {"$lookup": {
            "from": "inventory",
            "let": {"product_id": "$id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$product_id", "$$product_id"]}}},
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
    
    # Total customers (may be branch-specific or global)
    customer_query = {"active": True}
    if branch_filter and user.get("role") != "admin":
        customer_query = apply_branch_filter(customer_query, branch_filter)
    total_customers = await db.customers.count_documents(customer_query)
    
    # Receivables - from invoices (branch-filtered)
    receivables_match = {"status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}
    receivables_match = apply_branch_filter(receivables_match, branch_filter)
    
    invoice_rec_pipeline = [
        {"$match": receivables_match},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]
    inv_rec_result = await db.invoices.aggregate(invoice_rec_pipeline).to_list(1)
    invoice_receivables = inv_rec_result[0]["total"] if inv_rec_result else 0
    
    # Legacy receivables
    legacy_rec_query = {"status": {"$ne": "paid"}}
    legacy_rec_query = apply_branch_filter(legacy_rec_query, branch_filter)
    legacy_rec_pipeline = [
        {"$match": legacy_rec_query},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]
    legacy_rec_result = await db.receivables.aggregate(legacy_rec_pipeline).to_list(1)
    legacy_receivables = legacy_rec_result[0]["total"] if legacy_rec_result else 0
    
    total_receivables = invoice_receivables + legacy_receivables
    
    # Today's expenses (branch-filtered)
    expense_query = {"date": today}
    expense_query = apply_branch_filter(expense_query, branch_filter)
    today_expenses = await db.expenses.find(expense_query, {"_id": 0}).to_list(1000)
    today_expense_total = sum(e.get("amount", 0) for e in today_expenses)
    
    # Recent sales (branch-filtered)
    recent_invoice_query = {"status": {"$ne": "voided"}}
    recent_invoice_query = apply_branch_filter(recent_invoice_query, branch_filter)
    recent_invoices = await db.invoices.find(
        recent_invoice_query, {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    # Normalize invoice format
    for inv in recent_invoices:
        inv["sale_number"] = inv.get("invoice_number", "")
        inv["total"] = inv.get("grand_total", 0)
    
    recent_sales_query = {"status": "completed"}
    recent_sales_query = apply_branch_filter(recent_sales_query, branch_filter)
    recent_sales_raw = await db.sales.find(
        recent_sales_query, {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    all_recent = recent_invoices + recent_sales_raw
    all_recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    recent_sales = all_recent[:5]
    
    # Top products (branch-filtered)
    top_inv_pipeline = [
        {"$match": apply_branch_filter({"status": {"$ne": "voided"}}, branch_filter)},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_name",
            "total_qty": {"$sum": "$items.quantity"},
            "total_revenue": {"$sum": "$items.total"}
        }},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products_inv = await db.invoices.aggregate(top_inv_pipeline).to_list(5)
    
    top_sales_pipeline = [
        {"$match": apply_branch_filter({"status": "completed"}, branch_filter)},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_name",
            "total_qty": {"$sum": "$items.quantity"},
            "total_revenue": {"$sum": "$items.total"}
        }},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products_sales = await db.sales.aggregate(top_sales_pipeline).to_list(5)
    
    # Merge top products
    product_totals = {}
    for p in top_products_inv + top_products_sales:
        name = p["_id"]
        if name and name not in product_totals:
            product_totals[name] = {"qty": 0, "revenue": 0}
        if name:
            product_totals[name]["qty"] += p.get("total_qty", 0)
            product_totals[name]["revenue"] += p.get("total_revenue", 0)
    
    top_products = sorted(
        [{"name": k, "quantity": v["qty"], "revenue": v["revenue"]} for k, v in product_totals.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:5]
    
    # Get branches user can access
    user_branches = await get_user_branches(user)
    branches = await db.branches.find(
        {"active": True, "id": {"$in": user_branches}} if user_branches else {"active": True},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "today_revenue": today_revenue,
        "today_sales_count": today_count,
        "today_expenses": today_expense_total,
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "total_customers": total_customers,
        "total_receivables": total_receivables,
        "recent_sales": recent_sales,
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
        
        # Today's revenue for this branch
        today_invoices = await db.invoices.find(
            {"branch_id": branch_id, "status": {"$ne": "voided"}, "created_at": {"$gte": today}},
            {"_id": 0, "grand_total": 1}
        ).to_list(10000)
        today_revenue = sum(inv.get("grand_total", 0) for inv in today_invoices)
        today_sales_count = len(today_invoices)
        
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
            safe_balance = sum(l.get("remaining_amount", 0) for l in lots)
        
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
            {"$match": {"stock": {"$lte": 10}, "stock": {"$gte": 0}}},
            {"$count": "total"}
        ]
        low_stock_result = await db.products.aggregate(low_stock_pipeline).to_list(1)
        low_stock_count = low_stock_result[0]["total"] if low_stock_result else 0
        
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
            "receivables": receivables,
            "today_expenses": expenses,
            "net_today": today_revenue - expenses,
            "cashier_balance": cashier_balance,
            "safe_balance": safe_balance,
            "total_cash": cashier_balance + safe_balance,
            "low_stock_count": low_stock_count,
            "status": status,
        })
    
    # Calculate totals
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
