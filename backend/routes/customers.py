"""
Customer management routes with multi-branch support.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id,
    get_default_branch, ensure_branch_access
)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("")
async def list_customers(
    user=Depends(get_current_user),
    search: Optional[str] = None,
    branch_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List customers filtered by branch.
    - Specific branch_id provided → only that branch's customers
    - Admin with no branch_id → all customers (consolidated owner view)
    - Non-admin with no branch_id → their assigned branch only
    """
    query = {"active": True}

    if branch_id:
        # Explicit branch requested — verify access and filter
        await ensure_branch_access(user, branch_id)
        query["branch_id"] = branch_id
    elif user.get("role") != "admin":
        # Non-admin: restrict to their assigned branch
        user_branch = user.get("branch_id")
        if user_branch:
            query["branch_id"] = user_branch
        else:
            # No branch assigned — show nothing
            return {"customers": [], "total": 0}
    # Admin with no branch_id → no filter (sees all, for consolidated view)

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]

    total = await db.customers.count_documents(query)
    customers = await db.customers.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    return {"customers": customers, "total": total}


@router.post("")
async def create_customer(data: dict, user=Depends(get_current_user)):
    """Create a new customer."""
    check_perm(user, "customers", "create")
    
    # Determine branch_id
    branch_id = data.get("branch_id")
    if not branch_id:
        branch_id = await get_default_branch(user)
    
    customer = {
        "id": new_id(),
        "name": data["name"],
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "price_scheme": data.get("price_scheme", "retail"),
        "credit_limit": float(data.get("credit_limit", 0)),
        "interest_rate": float(data.get("interest_rate", 0)),
        "grace_period": int(data.get("grace_period", 7)),
        "balance": 0.0,
        "branch_id": branch_id,  # Branch assignment
        "active": True,
        "created_at": now_iso(),
    }
    await db.customers.insert_one(customer)
    del customer["_id"]
    return customer


@router.get("/receivables-summary")
async def customer_receivables_summary(
    branch_id: Optional[str] = None,
    include_zero: bool = False,
    user=Depends(get_current_user),
):
    """Aggregate open invoices per customer: total balance, overdue balance, invoice count."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    inv_match = {"status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}}
    if branch_id:
        inv_match["branch_id"] = branch_id

    pipeline = [
        {"$match": inv_match},
        {
            "$addFields": {
                "is_overdue": {
                    "$cond": [
                        {"$and": [
                            {"$ne": [{"$ifNull": ["$due_date", None]}, None]},
                            {"$lt": ["$due_date", today_str]},
                        ]},
                        True,
                        False,
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": "$customer_id",
                "total_balance": {"$sum": "$balance"},
                "overdue_balance": {
                    "$sum": {"$cond": ["$is_overdue", "$balance", 0]}
                },
                "invoice_count": {"$sum": 1},
                "overdue_count": {
                    "$sum": {"$cond": ["$is_overdue", 1, 0]}
                },
            }
        },
        {"$sort": {"total_balance": -1}},
    ]

    agg_results = await db.invoices.aggregate(pipeline).to_list(5000)

    cust_ids = [r["_id"] for r in agg_results if r["_id"]]
    agg_map = {r["_id"]: r for r in agg_results}

    cust_query = {"active": True}
    if branch_id:
        cust_query["branch_id"] = branch_id

    if include_zero:
        customers = await db.customers.find(cust_query, {"_id": 0}).to_list(5000)
    else:
        cust_query["id"] = {"$in": cust_ids}
        customers = await db.customers.find(cust_query, {"_id": 0}).to_list(5000)

    result = []
    for c in customers:
        agg = agg_map.get(c["id"], {})
        result.append({
            "id": c["id"],
            "name": c.get("name", ""),
            "phone": c.get("phone", ""),
            "balance": round(agg.get("total_balance", 0), 2),
            "overdue_balance": round(agg.get("overdue_balance", 0), 2),
            "invoice_count": agg.get("invoice_count", 0),
            "overdue_count": agg.get("overdue_count", 0),
            "interest_rate": c.get("interest_rate", 0),
            "grace_period": c.get("grace_period", 7),
            "credit_limit": c.get("credit_limit", 0),
        })

    return result


@router.get("/{customer_id}")
async def get_customer(customer_id: str, user=Depends(get_current_user)):
    """Get customer details."""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}")
async def update_customer(customer_id: str, data: dict, user=Depends(get_current_user)):
    """Update customer details."""
    check_perm(user, "customers", "edit")
    
    allowed = ["name", "phone", "email", "address", "price_scheme", 
               "credit_limit", "interest_rate", "grace_period"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    
    await db.customers.update_one({"id": customer_id}, {"$set": update})
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    return customer


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, user=Depends(get_current_user)):
    """Soft delete a customer."""
    check_perm(user, "customers", "delete")
    await db.customers.update_one({"id": customer_id}, {"$set": {"active": False}})
    return {"message": "Customer deleted"}


@router.get("/{customer_id}/transactions")
async def get_customer_transactions(customer_id: str, user=Depends(get_current_user)):
    """Get all transactions for a customer (invoices + payments + receivables)."""
    # Get all invoices for customer
    invoices = await db.invoices.find(
        {"customer_id": customer_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    # Get all receivables (from old POS system)
    receivables = await db.receivables.find(
        {"customer_id": customer_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    # Get customer info
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    
    # Calculate totals
    total_invoiced = sum(inv.get("grand_total", 0) for inv in invoices if inv.get("status") != "voided")
    total_paid = sum(inv.get("amount_paid", 0) for inv in invoices if inv.get("status") != "voided")
    total_balance = sum(inv.get("balance", 0) for inv in invoices if inv.get("status") not in ["paid", "voided"])
    
    # Add receivables totals
    total_receivables = sum(r.get("balance", 0) for r in receivables if r.get("status") != "paid")
    
    return {
        "customer": customer,
        "invoices": invoices,
        "receivables": receivables,
        "summary": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_balance": total_balance + total_receivables,
            "invoice_count": len(invoices),
            "open_invoices": len([i for i in invoices if i.get("status") not in ["paid", "voided"]]),
        }
    }
