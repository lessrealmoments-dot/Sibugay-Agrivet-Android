"""
Incident Tickets — Track and investigate transfer variances (shortages, excesses, damage).
Created when a sender accepts a variance but wants it investigated.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/incident-tickets", tags=["Incident Tickets"])


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
        }}
    ]
    results = await db.incident_tickets.aggregate(pipeline).to_list(20)
    summary = {
        "open": 0, "investigating": 0, "resolved": 0, "closed": 0,
        "total_unresolved_capital_loss": 0, "total_unresolved_retail_loss": 0,
    }
    for r in results:
        s = r["_id"]
        summary[s] = r["count"]
        if s in ("open", "investigating"):
            summary["total_unresolved_capital_loss"] += r["total_capital_loss"]
            summary["total_unresolved_retail_loss"] += r["total_retail_loss"]
    return summary


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


@router.put("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, data: dict, user=Depends(get_current_user)):
    """Resolve a ticket with a resolution note and optional recovery amount."""
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

    recovery_amount = float(data.get("recovery_amount", 0))

    event = {
        "action": "resolved",
        "by_id": user["id"],
        "by_name": user.get("full_name", user["username"]),
        "detail": resolution_note,
        "recovery_amount": recovery_amount,
        "at": now_iso(),
    }

    await db.incident_tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "resolved",
            "resolution_note": resolution_note,
            "recovery_amount": recovery_amount,
            "resolved_by_id": user["id"],
            "resolved_by_name": user.get("full_name", user["username"]),
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
        "description": f"Incident {ticket['ticket_number']} resolved: {resolution_note}",
        "metadata": {
            "transfer_id": ticket.get("transfer_id"),
            "order_number": ticket.get("order_number"),
            "total_capital_loss": ticket.get("total_capital_loss", 0),
            "recovery_amount": recovery_amount,
        },
        "user_id": user["id"],
        "user_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    })

    return {"message": "Ticket resolved", "status": "resolved"}


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
