"""
Customer management routes with multi-branch support.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id,
    get_branch_filter, apply_branch_filter, get_default_branch, CUSTOMER_SCOPE
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
    """List all customers with optional search. Respects branch isolation."""
    query = {"active": True}
    
    # Apply branch filter if customer scope is branch-specific
    if CUSTOMER_SCOPE == "branch":
        branch_filter = await get_branch_filter(user, branch_id)
        # For customers without branch_id (legacy), include them for admins
        if branch_filter and user.get("role") != "admin":
            query = apply_branch_filter(query, branch_filter)
    
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
    total_invoiced = sum(inv.get("grand_total", 0) for inv in invoices)
    total_paid = sum(inv.get("amount_paid", 0) for inv in invoices)
    total_balance = sum(inv.get("balance", 0) for inv in invoices if inv.get("status") != "paid")
    
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
