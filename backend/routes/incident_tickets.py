"""
Incident Tickets — Track and investigate transfer variances (shortages, excesses, damage).
Created when a sender accepts a variance but wants it investigated.

Phase 2: Structured resolution with resolution_type, accountable_party, sender confirmation.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/incident-tickets", tags=["Incident Tickets"])

RESOLUTION_TYPES = {
    "transit_loss": "Transit Loss — goods lost during transport",
    "sender_error": "Sender Error — sender miscounted, no actual loss",
    "receiver_error": "Receiver Error — receiver miscounted, corrected",
    "write_off": "Write Off — accepted business loss",
    "insurance_claim": "Insurance Claim — claimed from logistics provider",
    "partial_recovery": "Partial Recovery — partial compensation received",
}


@router.get("")
async def list_incident_tickets(
    user=Depends(get_current_user),
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    transfer_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    """List incident tickets with optional filters."""
    query = {}
    if status:
        query["status"] = status
    if branch_id:
        query["$or"] = [{"from_branch_id": branch_id}, {"to_branch_id": branch_id}]
    if transfer_id:
        query["transfer_id"] = transfer_id

    total = await db.incident_tickets.count_documents(query)
    tickets = await db.incident_tickets.find(query, {"_id": 0}).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(limit)
    return {"tickets": tickets, "total": total}


@router.get("/summary")
async def incident_summary(user=Depends(get_current_user)):
    """Summary stats for incident tickets dashboard."""
    pipeline = [
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_capital_loss": {"$sum": "$total_capital_loss"},
            "total_retail_loss": {"$sum": "$total_retail_loss"},
            "total_recovery": {"$sum": {"$ifNull": ["$recovery_amount", 0]}},
        }}
    ]
    results = await db.incident_tickets.aggregate(pipeline).to_list(20)

    # Separate pipeline: capital loss excluding sender_error (no real loss)
    real_loss_pipeline = [
        {"$match": {"resolution_type": {"$ne": "sender_error"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_capital_loss"}}},
    ]
    real_loss_result = await db.incident_tickets.aggregate(real_loss_pipeline).to_list(1)
    total_real_capital_loss = real_loss_result[0]["total"] if real_loss_result else 0

    summary = {
        "open": 0, "investigating": 0, "resolved": 0, "closed": 0,
        "total_unresolved_capital_loss": 0, "total_unresolved_retail_loss": 0,
        "total_recovered": 0,
        "total_real_capital_loss": total_real_capital_loss,
    }
    for r in results:
        s = r["_id"]
        summary[s] = r["count"]
        if s in ("open", "investigating"):
            summary["total_unresolved_capital_loss"] += r["total_capital_loss"]
            summary["total_unresolved_retail_loss"] += r["total_retail_loss"]
        summary["total_recovered"] += r.get("total_recovery", 0)
    return summary


@router.get("/resolution-types")
async def get_resolution_types(user=Depends(get_current_user)):
    """Return available resolution types for the resolve dialog."""
    return [{"value": k, "label": v} for k, v in RESOLUTION_TYPES.items()]


@router.get("/{ticket_id}")
async def get_incident_ticket(ticket_id: str, user=Depends(get_current_user)):
    """Get full ticket detail including timeline."""
    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Assign a ticket to a user for investigation."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    assigned_to_id = data.get("assigned_to_id", "")
    assigned_to_name = data.get("assigned_to_name", "")

    event = {
        "action": "assigned",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": f"Assigned to {assigned_to_name}",
        "at": now_iso(),
    }

    await db.incident_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "assigned_to_id": assigned_to_id,
            "assigned_to_name": assigned_to_name,
            "status": "investigating",
            "updated_at": now_iso(),
        }, "$push": {"timeline": event}}
    )
    return {"message": f"Ticket assigned to {assigned_to_name}"}


@router.put("/{ticket_id}/add-note")
async def add_ticket_note(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Add an investigation note to the ticket timeline."""
    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    note = data.get("note", "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="Note is required")

    event = {
        "action": "note",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": note,
        "at": now_iso(),
    }

    await db.incident_tickets.update_one(
        {"id": ticket_id},
        {"$set": {"updated_at": now_iso()}, "$push": {"timeline": event}}
    )
    return {"message": "Note added"}


@router.put("/{ticket_id}/sender-confirm")
async def sender_confirm(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Sender confirms the actual qty they sent. If it matches receiver, variance is cancelled."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] in ("resolved", "closed"):
        raise HTTPException(status_code=400, detail="Ticket already resolved/closed")

    confirmed_items = data.get("confirmed_items", [])
    note = data.get("note", "").strip()

    # Compare sender's confirmed qty with receiver's qty
    variance_cancelled = True
    updated_items = []
    for item in ticket.get("items", []):
        # Find sender's confirmed qty for this product
        confirmed = next(
            (c for c in confirmed_items if c.get("product_id") == item.get("product_id")),
            None
        )
        sender_qty = confirmed["sender_confirmed_qty"] if confirmed else item.get("qty_ordered", 0)
        receiver_qty = item.get("qty_received", 0)

        new_item = {**item, "sender_confirmed_qty": sender_qty}
        if sender_qty != receiver_qty:
            variance_cancelled = False
        updated_items.append(new_item)

    detail = "Sender confirmed quantities"
    if note:
        detail += f": {note}"
    if variance_cancelled:
        detail += " — ALL VARIANCES CANCELLED (sender confirms receiver was correct)"

    event = {
        "action": "sender_confirmed",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": detail,
        "confirmed_items": confirmed_items,
        "variance_cancelled": variance_cancelled,
        "at": now_iso(),
    }

    update_set = {
        "items": updated_items,
        "sender_confirmed": True,
        "sender_confirmed_at": now_iso(),
        "sender_confirmed_by_id": user["id"],
        "sender_confirmed_by_name": user.get("full_name", user["username"]),
        "updated_at": now_iso(),
    }

    if variance_cancelled:
        # Auto-resolve: sender confirms they actually sent what receiver got
        update_set["status"] = "resolved"
        update_set["resolution_type"] = "sender_error"
        update_set["resolution_note"] = "Sender confirmed actual quantities match receiver. No real loss."
        update_set["resolved_at"] = now_iso()
        update_set["resolved_by_id"] = user["id"]
        update_set["resolved_by_name"] = user.get("full_name", user["username"])

        resolve_event = {
            "action": "resolved",
            "by_id": user["id"],
            "by_name": user.get("full_name", user["username"]),
            "detail": "Auto-resolved: Sender confirmed no actual loss (sender_error)",
            "at": now_iso(),
        }
        await db.incident_tickets.update_one(
            {"id": ticket_id},
            {"$set": update_set, "$push": {"timeline": {"$each": [event, resolve_event]}}}
        )

        # Update the transfer to clear shortage flags
        if ticket.get("transfer_id"):
            await db.branch_transfer_orders.update_one(
                {"id": ticket["transfer_id"]},
                {"$set": {"has_shortage": False, "sender_confirmed_no_loss": True, "updated_at": now_iso()}}
            )

        return {"message": "Variance cancelled — sender confirms no actual loss", "auto_resolved": True}
    else:
        await db.incident_tickets.update_one(
            {"id": ticket_id},
            {"$set": update_set, "$push": {"timeline": event}}
        )
        return {"message": "Sender confirmation recorded. Variance still exists — proceed to resolve.", "auto_resolved": False}


@router.put("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Resolve a ticket with structured resolution type, accountable party, and recovery."""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or admin required")

    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=400, detail="Ticket is already closed")

    resolution_note = data.get("resolution_note", "").strip()
    if not resolution_note:
        raise HTTPException(status_code=400, detail="Resolution note is required")

    # ── PIN Authorization ──
    pin = data.get("pin", "").strip()
    if not pin:
        raise HTTPException(status_code=400, detail="Authorization PIN required")

    from routes.verify import verify_pin_for_action
    verifier = await verify_pin_for_action(pin, "incident_resolve", branch_id=ticket.get("to_branch_id"))
    if not verifier:
        raise HTTPException(status_code=403, detail="Invalid PIN — authorization denied")

    resolution_type = data.get("resolution_type", "write_off")
    if resolution_type not in RESOLUTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid resolution type: {resolution_type}")

    accountable_party = data.get("accountable_party", "").strip()
    recovery_amount = float(data.get("recovery_amount", 0))

    type_label = RESOLUTION_TYPES.get(resolution_type, resolution_type)
    detail_parts = [f"Resolved as: {type_label}"]
    if accountable_party:
        detail_parts.append(f"Charged to: {accountable_party}")
    if recovery_amount > 0:
        detail_parts.append(f"Recovery: PHP {recovery_amount:,.2f}")
    detail_parts.append(f"Approved by: {verifier['verifier_name']} ({verifier['method']})")
    detail_parts.append(resolution_note)

    event = {
        "action": "resolved",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": " | ".join(detail_parts),
        "resolution_type": resolution_type,
        "accountable_party": accountable_party,
        "recovery_amount": recovery_amount,
        "approved_by_id": verifier["verifier_id"],
        "approved_by_name": verifier["verifier_name"],
        "approval_method": verifier["method"],
        "at": now_iso(),
    }

    await db.incident_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "resolved",
            "resolution_type": resolution_type,
            "resolution_note": resolution_note,
            "accountable_party": accountable_party,
            "recovery_amount": recovery_amount,
            "resolved_by_id": user["id"],
            "resolved_by_name": user.get("full_name", user["username"]),
            "approved_by_id": verifier["verifier_id"],
            "approved_by_name": verifier["verifier_name"],
            "approval_method": verifier["method"],
            "resolved_at": now_iso(),
            "updated_at": now_iso(),
        }, "$push": {"timeline": event}}
    )

    # Create audit log
    await db.audit_log.insert_one({
        "id": new_id(),
        "type": "incident_resolved",
        "entity_type": "incident_ticket",
        "entity_id": ticket_id,
        "description": f"Incident {ticket['ticket_number']} resolved as {resolution_type}: {resolution_note}",
        "metadata": {
            "transfer_id": ticket.get("transfer_id"),
            "order_number": ticket.get("order_number"),
            "resolution_type": resolution_type,
            "accountable_party": accountable_party,
            "total_capital_loss": ticket.get("total_capital_loss", 0),
            "recovery_amount": recovery_amount,
        },
        "user_id": user["id"],
        "user_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    })

    return {"message": f"Ticket resolved as {resolution_type}", "status": "resolved"}


@router.put("/{ticket_id}/close")
async def close_ticket(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Close a resolved ticket (final step)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    ticket = await db.incident_tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    event = {
        "action": "closed",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": data.get("note", "Closed by admin"),
        "at": now_iso(),
    }

    await db.incident_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "closed",
            "closed_at": now_iso(),
            "updated_at": now_iso(),
        }, "$push": {"timeline": event}}
    )
    return {"message": "Ticket closed"}
