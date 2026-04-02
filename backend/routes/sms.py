"""
SMS Engine — Queue, Templates, Settings, and Auto-trigger helpers.
All SMS goes through the queue. An external gateway (phone app / API) polls
GET /pending and marks sent via PATCH /{id}/mark-sent.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db, _raw_db, logger as _config_logger
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/sms", tags=["SMS"])

# ── Default Templates (seeded on first access) ─────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "key": "credit_new",
        "name": "New Credit Notification",
        "body": (
            "Hi <customer_name>, ikaw ay may bagong credit na P<amount> "
            "sa <company_name> - <branch_name> ngayong <date>. "
            "Due date: <due_date>. "
            "Current total balance mo: P<total_balance>. "
            "Salamat po! - <company_name>"
        ),
        "placeholders": ["customer_name", "amount", "company_name", "branch_name",
                         "date", "due_date", "total_balance"],
        "trigger": "auto",
        "active": True,
    },
    {
        "key": "reminder_15day",
        "name": "15-Day Due Reminder",
        "body": (
            "Reminder: Hi <customer_name>, may balance ka pong "
            "P<total_balance> sa <company_name>. "
            "May P<amount_due_soon> na due sa <due_date> (15 days na lang po). "
            "Para maiwasan ang interest, bayaran po bago mag-due. Salamat!"
        ),
        "placeholders": ["customer_name", "total_balance", "company_name",
                         "amount_due_soon", "due_date"],
        "trigger": "scheduled",
        "active": True,
    },
    {
        "key": "reminder_7day",
        "name": "7-Day Due Reminder (with interest estimate)",
        "body": (
            "Urgent: Hi <customer_name>, P<amount_due_soon> mo po sa "
            "<company_name> ay due na sa <due_date> (7 days na lang). "
            "Kung hindi mababayaran on time, estimated interest po ay "
            "~P<est_interest>/month (<interest_rate>%/mo). "
            "Current total balance: P<total_balance>. "
            "Paki-settle na po. Salamat!"
        ),
        "placeholders": ["customer_name", "amount_due_soon", "company_name",
                         "due_date", "est_interest", "interest_rate", "total_balance"],
        "trigger": "scheduled",
        "active": True,
    },
    {
        "key": "overdue_notice",
        "name": "Overdue Notice",
        "body": (
            "Hi <customer_name>, ang P<amount_overdue> mo po sa "
            "<company_name> ay <days_overdue> days na overdue. "
            "Interest is accruing at <interest_rate>%/mo. "
            "Current total balance: P<total_balance>. "
            "Paki-settle na po agad. Salamat!"
        ),
        "placeholders": ["customer_name", "amount_overdue", "company_name",
                         "days_overdue", "interest_rate", "total_balance"],
        "trigger": "scheduled",
        "active": True,
    },
    {
        "key": "payment_received",
        "name": "Payment Received Confirmation",
        "body": (
            "Salamat <customer_name>! Natanggap na namin ang P<amount_paid> mo. "
            "Remaining balance: P<remaining_balance>. "
            "<next_due_info>"
            "Salamat po! - <company_name>"
        ),
        "placeholders": ["customer_name", "amount_paid", "remaining_balance",
                         "next_due_info", "company_name"],
        "trigger": "auto",
        "active": True,
    },
    {
        "key": "charge_applied",
        "name": "Interest/Penalty Applied",
        "body": (
            "Notice: <charge_type> of P<charge_amount> na-apply sa account mo, "
            "<customer_name>. New balance: P<total_balance>. "
            "Para maiwasan ang dagdag charges, bayaran po agad. "
            "- <company_name>"
        ),
        "placeholders": ["charge_type", "charge_amount", "customer_name",
                         "total_balance", "company_name"],
        "trigger": "auto",
        "active": True,
    },
    {
        "key": "delivery_ready",
        "name": "Delivery/Pickup Ready",
        "body": (
            "Hi <customer_name>, ang order mo po sa <company_name> - <branch_name> "
            "ay ready na for pickup. Ref: <reference_number>. "
            "Salamat po!"
        ),
        "placeholders": ["customer_name", "company_name", "branch_name",
                         "reference_number"],
        "trigger": "manual",
        "active": True,
    },
    {
        "key": "promo_blast",
        "name": "Promotional Message",
        "body": (
            "Hi <customer_name>! <promo_message> "
            "- <company_name> <branch_name>"
        ),
        "placeholders": ["customer_name", "promo_message", "company_name",
                         "branch_name"],
        "trigger": "manual",
        "active": True,
    },
    {
        "key": "monthly_summary",
        "name": "Monthly Statement Summary",
        "body": (
            "Monthly Summary: Hi <customer_name>, total balance mo po sa "
            "<company_name> ay P<total_balance>. "
            "Overdue: P<overdue_amount>. "
            "Paki-visit po kami para ma-settle. Salamat!"
        ),
        "placeholders": ["customer_name", "company_name", "total_balance",
                         "overdue_amount"],
        "trigger": "scheduled",
        "active": True,
    },
    {
        "key": "custom",
        "name": "Custom Message",
        "body": "<message>",
        "placeholders": ["message"],
        "trigger": "manual",
        "active": True,
    },
]


async def _ensure_templates():
    """Seed default templates for the current org if none exist yet."""
    count = await db.sms_templates.count_documents({})
    if count == 0:
        docs = []
        for t in DEFAULT_TEMPLATES:
            docs.append({**t, "id": new_id(), "created_at": now_iso(), "updated_at": now_iso()})
        await db.sms_templates.insert_many(docs)


# ── Template rendering helper ───────────────────────────────────────────────

def render_template(body: str, variables: dict) -> str:
    """Replace <placeholder> tokens with actual values."""
    result = body
    for key, val in variables.items():
        result = result.replace(f"<{key}>", str(val))
    return result


# ── Queue a single SMS (called by hooks / scheduler) ───────────────────────

async def queue_sms(
    template_key: str,
    customer_id: str,
    customer_name: str,
    phone: str,
    variables: dict,
    organization_id: str = "",
    branch_id: str = "",
    branch_name: str = "",
    trigger: str = "auto",
    trigger_ref: str = "",
    dedup_key: str = "",
):
    """Insert an SMS into the queue. Scoped to organization_id for multi-tenant isolation."""
    if not phone or not phone.strip():
        return None

    # Build org filter for _raw_db reads
    org_filter = {"organization_id": organization_id} if organization_id else {}

    # Check template — org-scoped first, fallback to global default
    template = None
    if organization_id:
        template = await _raw_db.sms_templates.find_one({"key": template_key, "organization_id": organization_id}, {"_id": 0})
    if not template:
        template = await _raw_db.sms_templates.find_one({"key": template_key, "organization_id": {"$exists": False}}, {"_id": 0})
    if not template:
        template = await _raw_db.sms_templates.find_one({"key": template_key}, {"_id": 0})
    if not template or not template.get("active", True):
        return None

    # Check per-trigger setting — org-scoped first, fallback to global
    setting = None
    base_setting_query = {"trigger_key": template_key, "$or": [{"branch_id": branch_id}, {"branch_id": None}, {"branch_id": ""}]}
    if organization_id:
        setting = await _raw_db.sms_settings.find_one({**base_setting_query, "organization_id": organization_id}, {"_id": 0})
    if not setting:
        setting = await _raw_db.sms_settings.find_one(base_setting_query, {"_id": 0})
    if setting and not setting.get("enabled", True):
        return None

    # De-duplication — always org-scoped to prevent cross-company dedup conflicts
    if dedup_key:
        existing = await _raw_db.sms_queue.find_one({"dedup_key": dedup_key, **org_filter}, {"_id": 0})
        if existing:
            return None

    message = render_template(template["body"], variables)
    doc = {
        "id": new_id(),
        "organization_id": organization_id,
        "template_key": template_key,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "phone": phone.strip(),
        "message": message,
        "status": "pending",
        "trigger": trigger,
        "trigger_ref": trigger_ref,
        "dedup_key": dedup_key,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "created_at": now_iso(),
        "sent_at": None,
        "failed_at": None,
        "error": None,
        "retry_count": 0,
    }
    await _raw_db.sms_queue.insert_one(doc)
    del doc["_id"]
    return doc


# ═══════════════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════════════


# ── Templates ───────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(user=Depends(get_current_user)):
    """List all SMS templates."""
    await _ensure_templates()
    templates = await db.sms_templates.find({}, {"_id": 0}).to_list(50)
    return templates


@router.put("/templates/{template_id}")
async def update_template(template_id: str, data: dict, user=Depends(get_current_user)):
    """Update template body or active status."""
    check_perm(user, "settings", "edit")
    allowed = {"body", "name", "active"}
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    update["updated_at"] = now_iso()
    result = await db.sms_templates.update_one({"id": template_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return await db.sms_templates.find_one({"id": template_id}, {"_id": 0})


# ── Settings ────────────────────────────────────────────────────────────────

@router.get("/settings")
async def list_sms_settings(user=Depends(get_current_user)):
    """List SMS trigger settings."""
    await _ensure_templates()
    settings = await db.sms_settings.find({}, {"_id": 0}).to_list(100)
    # Return merged with template defaults
    templates = await db.sms_templates.find({}, {"_id": 0}).to_list(50)
    settings_map = {s["trigger_key"]: s for s in settings}
    result = []
    for t in templates:
        s = settings_map.get(t["key"], {})
        result.append({
            "trigger_key": t["key"],
            "template_name": t["name"],
            "enabled": s.get("enabled", True),
            "branch_id": s.get("branch_id"),
        })
    return result


@router.put("/settings/{trigger_key}")
async def update_sms_setting(trigger_key: str, data: dict, user=Depends(get_current_user)):
    """Enable/disable a specific SMS trigger."""
    check_perm(user, "settings", "edit")
    enabled = data.get("enabled", True)
    branch_id = data.get("branch_id")
    await db.sms_settings.update_one(
        {"trigger_key": trigger_key, "branch_id": branch_id},
        {"$set": {"enabled": enabled, "updated_at": now_iso()},
         "$setOnInsert": {"id": new_id(), "trigger_key": trigger_key, "branch_id": branch_id}},
        upsert=True,
    )
    return {"trigger_key": trigger_key, "enabled": enabled}


# ── Queue ───────────────────────────────────────────────────────────────────

@router.get("/queue")
async def list_sms_queue(
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    user=Depends(get_current_user),
):
    """List SMS queue entries. Filter by status and branch."""
    query = {}
    if status:
        query["status"] = status
    if branch_id:
        query["branch_id"] = branch_id
    total = await db.sms_queue.count_documents(query)
    items = await db.sms_queue.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": items, "total": total}


@router.get("/queue/pending")
async def get_pending_sms(limit: int = 50, user=Depends(get_current_user)):
    """Get pending SMS for the gateway app to send."""
    items = await db.sms_queue.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("created_at", 1).limit(limit).to_list(limit)
    return items


@router.patch("/queue/{sms_id}/mark-sent")
async def mark_sms_sent(sms_id: str, user=Depends(get_current_user)):
    """Gateway app reports SMS was sent successfully."""
    result = await db.sms_queue.update_one(
        {"id": sms_id, "status": "pending"},
        {"$set": {"status": "sent", "sent_at": now_iso()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="SMS not found or not pending")
    return {"status": "sent"}


@router.patch("/queue/{sms_id}/mark-failed")
async def mark_sms_failed(sms_id: str, data: dict = None, user=Depends(get_current_user)):
    """Gateway app reports SMS send failure."""
    error = (data or {}).get("error", "Unknown error")
    await db.sms_queue.update_one(
        {"id": sms_id},
        {"$set": {"status": "failed", "failed_at": now_iso(), "error": error},
         "$inc": {"retry_count": 1}}
    )
    return {"status": "failed"}


@router.post("/queue/{sms_id}/retry")
async def retry_sms(sms_id: str, user=Depends(get_current_user)):
    """Re-queue a failed SMS."""
    result = await db.sms_queue.update_one(
        {"id": sms_id, "status": "failed"},
        {"$set": {"status": "pending", "error": None}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="SMS not found or not failed")
    return {"status": "pending"}


@router.post("/queue/{sms_id}/skip")
async def skip_sms(sms_id: str, user=Depends(get_current_user)):
    """Skip a pending SMS (admin decided not to send)."""
    result = await db.sms_queue.update_one(
        {"id": sms_id, "status": "pending"},
        {"$set": {"status": "skipped"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="SMS not found or not pending")
    return {"status": "skipped"}


# ── Manual Send / Compose ───────────────────────────────────────────────────

@router.post("/send")
async def send_manual_sms(data: dict, user=Depends(get_current_user)):
    """Manually compose and queue an SMS to a customer."""
    customer_id = data.get("customer_id", "")
    customer_name = data.get("customer_name", "")
    phone = data.get("phone", "")
    message = data.get("message", "")
    branch_id = data.get("branch_id", "")
    branch_name = data.get("branch_name", "")

    if not phone or not message:
        raise HTTPException(status_code=400, detail="Phone and message are required")

    # Auto-append signature server-side — cannot be removed or edited by the sender
    biz = await db.settings.find_one({"key": "company_info"}, {"_id": 0})
    company_name = (biz or {}).get("value", {}).get("name", "")
    sig_parts = [p for p in [company_name, branch_name] if p]
    if sig_parts:
        message = message + "\n\n- " + " | ".join(sig_parts)

    sent_by_name = user.get("full_name") or user.get("email", "")
    organization_id = user.get("organization_id", "")

    doc = {
        "id": new_id(),
        "organization_id": organization_id,
        "template_key": "custom",
        "customer_id": customer_id,
        "customer_name": customer_name,
        "phone": phone.strip(),
        "message": message,
        "status": "pending",
        "trigger": "manual",
        "trigger_ref": "",
        "dedup_key": "",
        "branch_id": branch_id,
        "branch_name": branch_name,
        "sent_by_name": sent_by_name,
        "created_at": now_iso(),
        "sent_at": None,
        "failed_at": None,
        "error": None,
        "retry_count": 0,
    }
    await db.sms_queue.insert_one(doc)
    del doc["_id"]
    return doc


@router.post("/blast")
async def send_promo_blast(data: dict, user=Depends(get_current_user)):
    """Send a promotional message to multiple customers.
    Body: { message, customer_ids?: [], filter?: { min_balance, branch_id }, branch_id, branch_name }
    """
    check_perm(user, "settings", "edit")
    message_text = data.get("message", "")
    if not message_text:
        raise HTTPException(status_code=400, detail="Message is required")

    branch_id = data.get("branch_id", "")
    branch_name = data.get("branch_name", "")
    customer_ids = data.get("customer_ids")
    filter_opts = data.get("filter", {})

    # Build customer query
    query = {"active": True}
    if customer_ids:
        query["id"] = {"$in": customer_ids}
    else:
        if filter_opts.get("branch_id"):
            query["branch_id"] = filter_opts["branch_id"]
        if filter_opts.get("min_balance"):
            query["balance"] = {"$gte": float(filter_opts["min_balance"])}

    customers = await db.customers.find(query, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(5000)

    # Get company name from settings
    biz = await db.settings.find_one({"key": "business_info"}, {"_id": 0})
    company_name = biz.get("value", {}).get("business_name", "AgriBooks") if biz else "AgriBooks"

    queued = 0
    for c in customers:
        phone = c.get("phone", "")
        if not phone:
            continue
        rendered = message_text.replace("<customer_name>", c.get("name", "Customer"))
        doc = {
            "id": new_id(),
            "template_key": "promo_blast",
            "customer_id": c["id"],
            "customer_name": c.get("name", ""),
            "phone": phone.strip(),
            "message": f"{rendered} - {company_name} {branch_name}".strip(),
            "status": "pending",
            "trigger": "manual",
            "trigger_ref": "blast",
            "dedup_key": "",
            "branch_id": branch_id,
            "branch_name": branch_name,
            "created_at": now_iso(),
            "sent_at": None,
            "failed_at": None,
            "error": None,
            "retry_count": 0,
        }
        await db.sms_queue.insert_one(doc)
        queued += 1

    return {"queued": queued, "total_customers": len(customers), "skipped_no_phone": len(customers) - queued}


# ── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
async def sms_stats(user=Depends(get_current_user)):
    """Get SMS queue statistics."""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    results = await db.sms_queue.aggregate(pipeline).to_list(10)
    stats = {r["_id"]: r["count"] for r in results}
    return {
        "pending": stats.get("pending", 0),
        "sent": stats.get("sent", 0),
        "failed": stats.get("failed", 0),
        "skipped": stats.get("skipped", 0),
        "total": sum(stats.values()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# INBOX — Incoming SMS from gateway phone (replies from customers)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/inbox")
async def receive_inbox_sms(data: dict, user=Depends(get_current_user)):
    """Gateway app posts incoming customer replies here."""
    phone = (data.get("phone") or "").strip()
    message = (data.get("message") or "").strip()
    if not phone or not message:
        raise HTTPException(status_code=400, detail="phone and message required")

    # Normalize phone — strip country code prefix if present
    normalized = phone.lstrip("+")
    if normalized.startswith("63") and len(normalized) > 10:
        normalized = "0" + normalized[2:]

    # Try to match customer by phone
    customer = await _raw_db.customers.find_one(
        {"phone": {"$in": [phone, normalized]}, "organization_id": user.get("organization_id")},
        {"_id": 0, "id": 1, "name": 1, "branch_id": 1}
    )
    if not customer:
        customer = await _raw_db.customers.find_one(
            {"phone": {"$in": [phone, normalized]}},
            {"_id": 0, "id": 1, "name": 1, "branch_id": 1}
        )

    doc = {
        "id": new_id(),
        "phone": phone,
        "message": message,
        "direction": "in",
        "customer_id": customer["id"] if customer else "",
        "customer_name": customer["name"] if customer else phone,
        "branch_id": customer.get("branch_id", "") if customer else "",
        "received_at": data.get("received_at", now_iso()),
        "created_at": now_iso(),
        "read": False,
    }
    await db.sms_inbox.insert_one(doc)
    del doc["_id"]
    return doc


@router.get("/conversations")
async def list_conversations(
    branch_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """List conversations grouped by phone.
    - branch_id provided → only phones that this branch has messaged (outgoing filter).
      Incoming replies for those phones are always included (shared inbox model).
    - No branch_id (admin consolidated) → all conversations.
    """
    # Determine phone scope when a specific branch is requested
    phone_filter: dict = {}
    if branch_id:
        phones_in_branch = await db.sms_queue.distinct(
            "phone",
            {"branch_id": branch_id, "status": {"$in": ["sent", "pending", "failed"]}},
        )
        if not phones_in_branch:
            return []
        phone_filter = {"phone": {"$in": phones_in_branch}}

    # Latest outgoing per phone — from ALL branches (full context for collaboration)
    out_pipeline = [
        {"$match": {"status": {"$in": ["sent", "pending", "failed"]}, **phone_filter}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$phone",
            "last_message": {"$first": "$message"},
            "last_time": {"$first": "$created_at"},
            "customer_name": {"$first": "$customer_name"},
            "customer_id": {"$first": "$customer_id"},
            "branch_ids": {"$addToSet": "$branch_id"},
            "branch_names": {"$addToSet": "$branch_name"},
        }},
    ]
    # Latest incoming per phone
    in_pipeline = [
        {"$match": phone_filter},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$phone",
            "last_message": {"$first": "$message"},
            "last_time": {"$first": "$created_at"},
            "customer_name": {"$first": "$customer_name"},
            "customer_id": {"$first": "$customer_id"},
            "unread": {"$sum": {"$cond": [{"$eq": ["$read", False]}, 1, 0]}},
        }},
    ]

    out_items = await db.sms_queue.aggregate(out_pipeline).to_list(500)
    in_items = await db.sms_inbox.aggregate(in_pipeline).to_list(500)

    # Merge — prefer whichever is most recent for the preview snippet
    merged = {}
    for item in out_items:
        phone = item["_id"]
        branch_ids = [b for b in item.get("branch_ids", []) if b]
        branch_names = [b for b in item.get("branch_names", []) if b]
        merged[phone] = {
            "phone": phone,
            "customer_name": item.get("customer_name", phone),
            "customer_id": item.get("customer_id", ""),
            "last_message": item.get("last_message", ""),
            "last_time": item.get("last_time", ""),
            "last_direction": "out",
            "unread": 0,
            "branch_ids": branch_ids,
            "branch_names": branch_names,
        }
    for item in in_items:
        phone = item["_id"]
        unread = item.get("unread", 0)
        if phone in merged:
            if item.get("last_time", "") > merged[phone]["last_time"]:
                merged[phone]["last_message"] = item.get("last_message", "")
                merged[phone]["last_time"] = item.get("last_time", "")
                merged[phone]["last_direction"] = "in"
            merged[phone]["unread"] = unread
        else:
            merged[phone] = {
                "phone": phone,
                "customer_name": item.get("customer_name", phone),
                "customer_id": item.get("customer_id", ""),
                "last_message": item.get("last_message", ""),
                "last_time": item.get("last_time", ""),
                "last_direction": "in",
                "unread": unread,
                "branch_ids": [],
                "branch_names": [],
            }

    result = sorted(merged.values(), key=lambda x: x.get("last_time", ""), reverse=True)
    return result


@router.get("/conversation/{phone}")
async def get_conversation(phone: str, user=Depends(get_current_user)):
    """Get full message thread for a phone number — sent + received merged."""
    # Normalize for lookup
    normalized = phone.lstrip("+")
    if normalized.startswith("63") and len(normalized) > 10:
        normalized = "0" + normalized[2:]
    phones = list({phone, normalized})

    # Outgoing messages
    out_msgs = await db.sms_queue.find(
        {"phone": {"$in": phones}, "status": {"$in": ["sent", "pending", "failed"]}},
        {"_id": 0, "id": 1, "message": 1, "created_at": 1, "status": 1,
         "customer_name": 1, "template_key": 1, "branch_id": 1, "branch_name": 1, "sent_by_name": 1}
    ).sort("created_at", 1).to_list(500)
    for m in out_msgs:
        m["direction"] = "out"

    # Incoming messages
    in_msgs = await db.sms_inbox.find(
        {"phone": {"$in": phones}},
        {"_id": 0, "id": 1, "message": 1, "created_at": 1, "customer_name": 1}
    ).sort("created_at", 1).to_list(500)
    for m in in_msgs:
        m["direction"] = "in"
        m["status"] = "received"

    # Mark inbox as read
    await db.sms_inbox.update_many({"phone": {"$in": phones}}, {"$set": {"read": True}})

    all_msgs = sorted(out_msgs + in_msgs, key=lambda x: x.get("created_at", ""))
    customer_name = all_msgs[0].get("customer_name", phone) if all_msgs else phone
    return {"phone": phone, "customer_name": customer_name, "messages": all_msgs}

