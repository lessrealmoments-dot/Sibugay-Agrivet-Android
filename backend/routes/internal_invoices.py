"""
Internal Invoices — auto-generated when a branch transfer is created.
Tracks the financial obligation between branches (internal AP/AR).
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import get_current_user, now_iso, new_id

router = APIRouter(prefix="/internal-invoices", tags=["Internal Invoices"])


async def create_internal_invoice(transfer: dict, user: dict):
    """Auto-create an internal invoice from a branch transfer order."""
    items = transfer.get("items", [])
    total = round(sum(
        float(i.get("transfer_capital", 0)) * float(i.get("qty", 0)) for i in items
    ), 2)

    # Default payment terms: Net 15
    terms_days = 15
    created_at = datetime.now(timezone.utc)
    due_date = (created_at + timedelta(days=terms_days)).isoformat()

    count = await db.internal_invoices.count_documents({})
    invoice_number = f"INV-{created_at.strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"

    invoice = {
        "id": new_id(),
        "invoice_number": invoice_number,
        "transfer_id": transfer["id"],
        "transfer_number": transfer.get("order_number", ""),
        "request_po_id": transfer.get("request_po_id", ""),
        "request_po_number": transfer.get("request_po_number", ""),
        "from_branch_id": transfer["from_branch_id"],
        "to_branch_id": transfer["to_branch_id"],
        "items": [{
            "product_id": i.get("product_id", ""),
            "product_name": i.get("product_name", ""),
            "sku": i.get("sku", ""),
            "category": i.get("category", ""),
            "unit": i.get("unit", ""),
            "qty": float(i.get("qty", 0)),
            "requested_qty": float(i.get("requested_qty", 0)) if i.get("requested_qty") else None,
            "transfer_capital": float(i.get("transfer_capital", 0)),
            "branch_retail": float(i.get("branch_retail", 0)),
            "line_total": round(float(i.get("transfer_capital", 0)) * float(i.get("qty", 0)), 2),
        } for i in items],
        "subtotal": total,
        "grand_total": total,
        "status": "prepared",  # prepared → sent → received → paid
        "payment_status": "unpaid",  # unpaid → paid
        "terms_days": terms_days,
        "due_date": due_date,
        "created_by": user.get("id", ""),
        "created_by_name": user.get("full_name", user.get("username", "")),
        "created_at": now_iso(),
        "sent_at": None,
        "received_at": None,
        "paid_at": None,
    }

    await db.internal_invoices.insert_one(invoice)
    del invoice["_id"]

    # Store invoice_id on the transfer
    await db.branch_transfer_orders.update_one(
        {"id": transfer["id"]},
        {"$set": {"invoice_id": invoice["id"], "invoice_number": invoice["invoice_number"]}}
    )

    return invoice


async def update_invoice_status(transfer_id: str, new_status: str, extra_fields: dict = None):
    """Update invoice status when transfer status changes."""
    invoice = await db.internal_invoices.find_one(
        {"transfer_id": transfer_id}, {"_id": 0}
    )
    if not invoice:
        return

    update = {"status": new_status}
    if new_status == "sent":
        update["sent_at"] = now_iso()
    elif new_status == "received":
        update["received_at"] = now_iso()
    elif new_status == "paid":
        update["paid_at"] = now_iso()
        update["payment_status"] = "paid"

    if extra_fields:
        update.update(extra_fields)

    await db.internal_invoices.update_one(
        {"transfer_id": transfer_id}, {"$set": update}
    )


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("")
async def list_internal_invoices(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    """List internal invoices. Admin sees all, branch users see their branch."""
    q = {}
    user_branch = user.get("branch_id")
    is_admin = user.get("role") == "admin"

    if branch_id:
        q["$or"] = [{"from_branch_id": branch_id}, {"to_branch_id": branch_id}]
    elif not is_admin and user_branch:
        q["$or"] = [{"from_branch_id": user_branch}, {"to_branch_id": user_branch}]

    if status:
        q["status"] = status
    if payment_status:
        q["payment_status"] = payment_status

    total = await db.internal_invoices.count_documents(q)
    invoices = await db.internal_invoices.find(
        q, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    # Enrich with branch names
    branch_cache = {}
    for inv in invoices:
        for key in ["from_branch_id", "to_branch_id"]:
            bid = inv.get(key, "")
            if bid and bid not in branch_cache:
                b = await db.branches.find_one({"id": bid}, {"_id": 0, "name": 1})
                branch_cache[bid] = b.get("name", "") if b else ""
            inv[f"{key.replace('_id','_name')}"] = branch_cache.get(bid, "")

    return {"invoices": invoices, "total": total}


@router.get("/summary")
async def get_invoice_summary(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
):
    """Get summary of internal invoices for dashboard."""
    user_branch = branch_id or user.get("branch_id", "")
    is_admin = user.get("role") == "admin"

    # Payables: invoices where this branch is the TO (receiver/buyer)
    payable_q = {"payment_status": "unpaid"}
    if user_branch and not is_admin:
        payable_q["to_branch_id"] = user_branch
    elif user_branch:
        payable_q["to_branch_id"] = user_branch

    payables = await db.internal_invoices.find(payable_q, {"_id": 0}).to_list(200)

    now = datetime.now(timezone.utc)
    total_payable = sum(inv.get("grand_total", 0) for inv in payables)
    overdue = [inv for inv in payables if inv.get("due_date") and datetime.fromisoformat(inv["due_date"].replace("Z", "+00:00")) < now]
    overdue_total = sum(inv.get("grand_total", 0) for inv in overdue)
    due_soon = [inv for inv in payables
                if inv.get("due_date")
                and now <= datetime.fromisoformat(inv["due_date"].replace("Z", "+00:00")) <= now + timedelta(days=7)]
    due_soon_total = sum(inv.get("grand_total", 0) for inv in due_soon)

    # Receivables: invoices where this branch is the FROM (supplier/sender)
    receivable_q = {"payment_status": "unpaid"}
    if user_branch and not is_admin:
        receivable_q["from_branch_id"] = user_branch
    elif user_branch:
        receivable_q["from_branch_id"] = user_branch

    receivables = await db.internal_invoices.find(receivable_q, {"_id": 0}).to_list(200)
    total_receivable = sum(inv.get("grand_total", 0) for inv in receivables)

    return {
        "payable": {
            "total": round(total_payable, 2),
            "count": len(payables),
            "overdue_total": round(overdue_total, 2),
            "overdue_count": len(overdue),
            "due_soon_total": round(due_soon_total, 2),
            "due_soon_count": len(due_soon),
        },
        "receivable": {
            "total": round(total_receivable, 2),
            "count": len(receivables),
        }
    }


@router.get("/{invoice_id}")
async def get_internal_invoice(invoice_id: str, user=Depends(get_current_user)):
    """Get a single internal invoice."""
    invoice = await db.internal_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Enrich with branch names
    for key in ["from_branch_id", "to_branch_id"]:
        bid = invoice.get(key, "")
        b = await db.branches.find_one({"id": bid}, {"_id": 0, "name": 1})
        invoice[f"{key.replace('_id','_name')}"] = b.get("name", "") if b else ""

    return invoice


@router.get("/by-transfer/{transfer_id}")
async def get_invoice_by_transfer(transfer_id: str, user=Depends(get_current_user)):
    """Get the internal invoice linked to a transfer."""
    invoice = await db.internal_invoices.find_one(
        {"transfer_id": transfer_id}, {"_id": 0}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="No invoice for this transfer")

    for key in ["from_branch_id", "to_branch_id"]:
        bid = invoice.get(key, "")
        b = await db.branches.find_one({"id": bid}, {"_id": 0, "name": 1})
        invoice[f"{key.replace('_id','_name')}"] = b.get("name", "") if b else ""

    return invoice
