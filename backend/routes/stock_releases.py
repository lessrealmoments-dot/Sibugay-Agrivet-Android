"""
Stock Release routes — manage partial stock release for invoices.
Tracks reservations, pending releases, and release history.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, now_iso

router = APIRouter(prefix="/stock-releases", tags=["Stock Releases"])


@router.get("")
async def list_pending_releases(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,   # not_released | partially_released | fully_released
    user=Depends(get_current_user),
):
    """List invoices with partial release mode. Used by close wizard and admin view."""
    q = {"release_mode": "partial"}
    if branch_id:
        q["branch_id"] = branch_id
    elif user.get("role") != "admin" and user.get("branch_id"):
        q["branch_id"] = user["branch_id"]

    if status:
        q["stock_release_status"] = status
    else:
        # Default: show non-fully-released
        q["stock_release_status"] = {"$in": ["not_released", "partially_released"]}

    invoices = await db.invoices.find(
        q,
        {"_id": 0, "id": 1, "invoice_number": 1, "customer_name": 1, "grand_total": 1,
         "stock_release_status": 1, "stock_releases": 1, "created_at": 1,
         "branch_id": 1, "items": 1}
    ).sort("created_at", -1).limit(200).to_list(200)

    # Enrich with reservation summary
    results = []
    for inv in invoices:
        reservations = await db.sale_reservations.find(
            {"invoice_id": inv["id"]}, {"_id": 0}
        ).to_list(100)
        total_ordered = sum(r["sold_qty_ordered"] for r in reservations)
        total_released = sum(r["sold_qty_released"] for r in reservations)
        total_remaining = sum(r["sold_qty_remaining"] for r in reservations)
        results.append({
            **inv,
            "reservation_summary": {
                "total_items": len(reservations),
                "total_ordered": total_ordered,
                "total_released": total_released,
                "total_remaining": total_remaining,
                "pct_released": round(total_released / total_ordered * 100, 1) if total_ordered > 0 else 0,
            }
        })

    return {"invoices": results, "total": len(results)}


@router.get("/summary")
async def get_pending_releases_summary(
    branch_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Quick count of pending releases for dashboard / Z-report warning."""
    q = {"release_mode": "partial", "stock_release_status": {"$in": ["not_released", "partially_released"]}}
    if branch_id:
        q["branch_id"] = branch_id
    elif user.get("role") != "admin" and user.get("branch_id"):
        q["branch_id"] = user["branch_id"]

    count = await db.invoices.count_documents(q)

    # Count total qty still reserved
    q2 = {"qty_remaining": {"$gt": 0}}
    if branch_id:
        q2["branch_id"] = branch_id
    elif user.get("role") != "admin" and user.get("branch_id"):
        q2["branch_id"] = user["branch_id"]

    res_agg = await db.sale_reservations.aggregate([
        {"$match": q2},
        {"$group": {"_id": None, "total_qty": {"$sum": "$qty_remaining"}, "total_invoices": {"$addToSet": "$invoice_id"}}}
    ]).to_list(1)

    total_qty = round(float(res_agg[0]["total_qty"]), 2) if res_agg else 0

    # Check for overdue (>30 days)
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).isoformat()
    overdue_count = await db.sale_reservations.count_documents(
        {**q2, "expires_at": {"$lt": now_str}}
    )

    return {
        "pending_invoice_count": count,
        "total_reserved_qty": total_qty,
        "overdue_reservations": overdue_count,
        "has_overdue": overdue_count > 0,
    }


@router.get("/{invoice_id}")
async def get_invoice_release_detail(invoice_id: str, user=Depends(get_current_user)):
    """Get full release detail for an invoice — reservations and release history."""
    invoice = await db.invoices.find_one(
        {"id": invoice_id, "release_mode": "partial"}, {"_id": 0}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found or is not a partial-release invoice")

    reservations = await db.sale_reservations.find(
        {"invoice_id": invoice_id}, {"_id": 0}
    ).to_list(100)

    return {
        "invoice": {
            "id": invoice["id"],
            "invoice_number": invoice.get("invoice_number"),
            "customer_name": invoice.get("customer_name"),
            "grand_total": invoice.get("grand_total"),
            "stock_release_status": invoice.get("stock_release_status"),
            "stock_releases": invoice.get("stock_releases", []),
            "branch_id": invoice.get("branch_id"),
            "created_at": invoice.get("created_at"),
        },
        "reservations": reservations,
    }
