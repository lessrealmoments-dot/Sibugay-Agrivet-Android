"""
Notifications routes.
In-app alerts for admin/owner users.
Currently triggered when manager PINs are used (credit sales, employee advances, etc.).
"""
from fastapi import APIRouter, Depends
from typing import Optional
from config import db
from utils import get_current_user, now_iso, new_id

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(
    user=Depends(get_current_user),
    unread_only: bool = False,
    limit: int = 30
):
    """Get notifications for the current user (admins see all)."""
    query = {}
    if user.get("role") != "admin":
        query["target_user_ids"] = user["id"]
    if unread_only:
        query["read_by"] = {"$not": {"$elemMatch": {"$eq": user["id"]}}}

    notifications = await db.notifications.find(query, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)

    # Mark read status per user
    uid = user["id"]
    for n in notifications:
        n["is_read"] = uid in n.get("read_by", [])

    unread_count = await db.notifications.count_documents({
        **query,
        "read_by": {"$not": {"$elemMatch": {"$eq": uid}}}
    })

    return {"notifications": notifications, "unread_count": unread_count}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: str, user=Depends(get_current_user)):
    """Mark a single notification as read for this user."""
    await db.notifications.update_one(
        {"id": notification_id},
        {"$addToSet": {"read_by": user["id"]}}
    )
    return {"message": "Marked as read"}


@router.put("/mark-all-read")
async def mark_all_read(user=Depends(get_current_user)):
    """Mark all notifications as read for this user."""
    query = {} if user.get("role") == "admin" else {"target_user_ids": user["id"]}
    await db.notifications.update_many(query, {"$addToSet": {"read_by": user["id"]}})
    return {"message": "All marked as read"}


async def create_pin_notification(context, manager_id: str, manager_name: str):
    """
    Create a notification for admin users when a manager PIN is used.
    context = { type, description, branch_id, branch_name, amount, ... }
    Also accepts a plain string context (treated as description).
    """
    # Normalize context to dict if a plain string was passed
    if isinstance(context, str):
        context = {"type": "admin_action", "description": context}

    # Get all admin user IDs to notify
    admins = await db.users.find(
        {"role": "admin", "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    target_ids = [a["id"] for a in admins]

    ctx_type = context.get("type", "pin_used")
    type_labels = {
        "credit_sale": "Credit Sale Approved",
        "employee_advance": "Employee Advance Approved",
        "price_override": "Price Override Approved",
        "inventory_seed": "Inventory Seed Authorized",
    }
    title = type_labels.get(ctx_type, "Manager PIN Used")

    description = context.get("description", "A manager PIN was used")
    branch_name = context.get("branch_name", "")
    location = f" at {branch_name}" if branch_name else ""

    notification = {
        "id": new_id(),
        "type": ctx_type,
        "title": title,
        "message": f"{manager_name} approved: {description}{location}",
        "manager_id": manager_id,
        "manager_name": manager_name,
        "branch_id": context.get("branch_id"),
        "branch_name": branch_name,
        "context_type": ctx_type,
        "metadata": context,
        "target_user_ids": target_ids,
        "read_by": [],
        "created_at": now_iso(),
    }
    await db.notifications.insert_one(notification)
    return notification
