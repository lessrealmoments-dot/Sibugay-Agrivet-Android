"""
Security tracking: failed PIN/TOTP attempt logging and brute-force alerting.

When a user (cashier, manager, etc.) enters the wrong PIN 5+ times within a
30-minute window, a security notification is sent to all admins and an audit
entry is logged — silently, without alerting the employee.
"""
from datetime import datetime, timezone, timedelta
from config import db
from utils.helpers import new_id, now_iso

ATTEMPT_THRESHOLD = 5          # alert after this many failures
WINDOW_MINUTES = 30            # rolling time window


async def log_failed_pin_attempt(user: dict, context: str, attempt_type: str):
    """
    Log a failed PIN/TOTP attempt for the authenticated user.
    Triggers a security alert to admins when threshold is reached.

    Args:
        user:         The currently logged-in user (who submitted the wrong PIN)
        context:      Human-readable description of what they were trying to do
        attempt_type: One of "transaction_verify" | "fund_transfer" | "admin_action"
    """
    user_id   = user.get("id", "unknown")
    user_name = user.get("full_name") or user.get("username") or "Unknown User"
    branch_id = user.get("branch_id")

    # 1. Log the attempt
    await db.pin_attempt_log.insert_one({
        "id":           new_id(),
        "user_id":      user_id,
        "user_name":    user_name,
        "attempt_type": attempt_type,
        "context":      context,
        "branch_id":    branch_id,
        "success":      False,
        "attempted_at": now_iso(),
    })

    # 2. Count failures for this user in the rolling window
    window_start = (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)).isoformat()
    recent_failures = await db.pin_attempt_log.count_documents({
        "user_id":      user_id,
        "success":      False,
        "attempted_at": {"$gte": window_start},
    })

    # 3. Alert on threshold and every subsequent attempt (5, 6, 7, ...)
    if recent_failures >= ATTEMPT_THRESHOLD:
        await _raise_security_alert(user_id, user_name, branch_id, recent_failures, context, attempt_type)


async def log_successful_pin_attempt(user: dict, context: str, attempt_type: str):
    """
    Log a successful PIN attempt (for audit completeness).
    Optionally useful for anomaly detection later.
    """
    await db.pin_attempt_log.insert_one({
        "id":           new_id(),
        "user_id":      user.get("id", "unknown"),
        "user_name":    user.get("full_name") or user.get("username") or "Unknown",
        "attempt_type": attempt_type,
        "context":      context,
        "branch_id":    user.get("branch_id"),
        "success":      True,
        "attempted_at": now_iso(),
    })


async def _raise_security_alert(user_id, user_name, branch_id, failure_count, context, attempt_type):
    """
    Create a security notification for admins and log to security_events.
    Only fires once per threshold crossing (every attempt at/above threshold).
    Deduplication: skip if an identical alert was sent in the last 5 minutes.
    """
    dedup_window = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    recent_alert = await db.security_events.find_one({
        "user_id":    user_id,
        "event_type": "failed_pin_brute_force",
        "created_at": {"$gte": dedup_window},
    })
    if recent_alert:
        return  # Already alerted recently — don't spam

    type_labels = {
        "transaction_verify": "Transaction Verification",
        "fund_transfer":      "Fund Transfer",
        "admin_action":       "Admin Action Authorization",
    }
    action_label = type_labels.get(attempt_type, attempt_type)

    # --- Audit log entry ---
    event = {
        "id":           new_id(),
        "event_type":   "failed_pin_brute_force",
        "user_id":      user_id,
        "user_name":    user_name,
        "branch_id":    branch_id,
        "failure_count": failure_count,
        "attempt_type": attempt_type,
        "context":      context,
        "severity":     "high" if failure_count >= 10 else "medium",
        "created_at":   now_iso(),
    }
    await db.security_events.insert_one(event)

    # --- Notification to all admins ---
    admins = await db.users.find(
        {"role": "admin", "active": True}, {"_id": 0, "id": 1}
    ).to_list(50)
    target_ids = [a["id"] for a in admins]

    severity_label = "URGENT" if failure_count >= 10 else "Warning"

    await db.notifications.insert_one({
        "id":       new_id(),
        "type":     "security_alert",
        "title":    f"Security {severity_label}: Repeated Wrong PIN",
        "message":  (
            f"{user_name} has entered the wrong PIN {failure_count} times "
            f"in the last {WINDOW_MINUTES} minutes while attempting: {action_label}. "
            f"Context: {context}"
        ),
        "branch_id":        branch_id,
        "metadata": {
            "user_id":       user_id,
            "user_name":     user_name,
            "failure_count": failure_count,
            "attempt_type":  attempt_type,
            "context":       context,
            "severity":      "high" if failure_count >= 10 else "medium",
        },
        "target_user_ids":  target_ids,
        "read_by":          [],
        "created_at":       now_iso(),
    })
