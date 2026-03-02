"""
Backup management routes — full-site + per-org backups.
Super admin: full site backup/restore, all org backups, schedule config.
Company owner: their org backup/restore only.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, now_iso, new_id
from services.backup_service import create_backup, list_backups, restore_backup
from services.org_backup_service import (
    create_org_backup, list_org_backups, restore_org_backup, get_org_data_stats
)
import os

router = APIRouter(prefix="/backups", tags=["Backups"])

DB_NAME = os.environ.get("DB_NAME", "test_database")


# ── Full Site Backup (Super Admin) ────────────────────────────────────────────

@router.post("/site/trigger")
async def trigger_site_backup(user=Depends(get_current_user)):
    """Manually trigger a full database backup. Super admin only."""
    if not user.get("is_super_admin") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    result = await create_backup(DB_NAME)
    return result


@router.get("/site/list")
async def list_site_backups(user=Depends(get_current_user)):
    """List all full-site backups."""
    if not user.get("is_super_admin") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    backups = await list_backups(DB_NAME)
    return {"backups": backups, "count": len(backups)}


@router.post("/site/restore/{filename}")
async def restore_site_backup(filename: str, user=Depends(get_current_user)):
    """Restore full database from a specific backup. Super admin only."""
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin required")
    result = await restore_backup(DB_NAME, filename)
    return result


# ── Per-Org Backup ────────────────────────────────────────────────────────────

@router.post("/org/{org_id}/trigger")
async def trigger_org_backup(org_id: str, user=Depends(get_current_user)):
    """Trigger a backup for a specific organization."""
    # Super admin can backup any org. Company admin can only backup their own.
    if not user.get("is_super_admin"):
        if user.get("organization_id") != org_id:
            raise HTTPException(status_code=403, detail="You can only backup your own organization")
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required")

    from motor.motor_asyncio import AsyncIOMotorClient
    raw_db = AsyncIOMotorClient(os.environ.get("MONGO_URL"))[DB_NAME]
    org = await raw_db.organizations.find_one({"id": org_id}, {"_id": 0, "name": 1})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await create_org_backup(
        org_id,
        org_name=org.get("name", ""),
        triggered_by=user.get("full_name", user.get("username", ""))
    )
    return result


@router.get("/org/{org_id}/list")
async def list_org_backup_history(org_id: str, user=Depends(get_current_user)):
    """List all backups for a specific organization."""
    if not user.get("is_super_admin"):
        if user.get("organization_id") != org_id and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

    backups = await list_org_backups(org_id)
    return {"backups": backups, "count": len(backups)}


@router.post("/org/{org_id}/restore/{filename}")
async def restore_org_from_backup(org_id: str, filename: str, data: dict = None, user=Depends(get_current_user)):
    """Restore an org from a specific backup point. Requires admin."""
    if data is None:
        data = {}
    if not user.get("is_super_admin"):
        if user.get("organization_id") != org_id:
            raise HTTPException(status_code=403, detail="You can only restore your own organization")
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required")

    # PIN verification for dangerous operation
    pin = str(data.get("pin", ""))
    if pin:
        from routes.verify import verify_pin_for_action
        verifier = await verify_pin_for_action(pin, "backup_restore")
        if not verifier:
            raise HTTPException(status_code=403, detail="Invalid PIN")

    result = await restore_org_backup(
        org_id, filename,
        restored_by=user.get("full_name", user.get("username", ""))
    )
    return result


@router.get("/org/{org_id}/stats")
async def get_org_backup_stats(org_id: str, user=Depends(get_current_user)):
    """Get data size stats for an org (document counts per collection)."""
    if not user.get("is_super_admin"):
        if user.get("organization_id") != org_id and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    stats = await get_org_data_stats(org_id)
    return stats


# ── All Orgs Summary (Super Admin) ───────────────────────────────────────────

@router.get("/org-summary")
async def get_all_orgs_backup_summary(user=Depends(get_current_user)):
    """Get backup summary for all organizations. Super admin only."""
    if not user.get("is_super_admin") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    from motor.motor_asyncio import AsyncIOMotorClient
    raw_db = AsyncIOMotorClient(os.environ.get("MONGO_URL"))[DB_NAME]

    orgs = await raw_db.organizations.find({}, {"_id": 0, "id": 1, "name": 1, "plan": 1}).to_list(500)
    result = []
    for org in orgs:
        org_id = org["id"]
        # Get last backup
        last_backup = await raw_db.org_backups.find_one(
            {"org_id": org_id, "type": {"$exists": False}},
            {"_id": 0}, sort=[("created_at", -1)]
        )
        # Get doc count
        stats = await get_org_data_stats(org_id)
        result.append({
            "org_id": org_id,
            "org_name": org.get("name", ""),
            "plan": org.get("plan", ""),
            "total_documents": stats["total_documents"],
            "last_backup_at": last_backup.get("created_at") if last_backup else None,
            "last_backup_size_mb": last_backup.get("size_mb") if last_backup else None,
            "last_backup_docs": last_backup.get("total_documents") if last_backup else None,
        })

    return {"organizations": result, "total": len(result)}


# ── Backup Schedule Config ────────────────────────────────────────────────────

@router.get("/schedule")
async def get_backup_schedule(user=Depends(get_current_user)):
    """Get current backup schedule configuration."""
    if not user.get("is_super_admin") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    from motor.motor_asyncio import AsyncIOMotorClient
    raw_db = AsyncIOMotorClient(os.environ.get("MONGO_URL"))[DB_NAME]
    config = await raw_db.system_settings.find_one({"key": "backup_schedule"}, {"_id": 0})
    if not config:
        config = {
            "key": "backup_schedule",
            "site_backup_hours": [1],
            "org_backup_hours": [1, 7, 13, 19],
            "org_backup_enabled": False,
        }
    return config


@router.put("/schedule")
async def update_backup_schedule(data: dict, user=Depends(get_current_user)):
    """Update backup schedule. Restarts scheduler jobs."""
    if not user.get("is_super_admin") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    site_hours = data.get("site_backup_hours", [1])
    org_hours = data.get("org_backup_hours", [1, 7, 13, 19])
    org_enabled = data.get("org_backup_enabled", False)

    from motor.motor_asyncio import AsyncIOMotorClient
    raw_db = AsyncIOMotorClient(os.environ.get("MONGO_URL"))[DB_NAME]
    await raw_db.system_settings.update_one(
        {"key": "backup_schedule"},
        {"$set": {
            "key": "backup_schedule",
            "site_backup_hours": site_hours,
            "org_backup_hours": org_hours,
            "org_backup_enabled": org_enabled,
            "updated_at": now_iso(),
        }},
        upsert=True,
    )
    return {"message": "Schedule updated. Restart backend to apply new schedule.",
            "site_backup_hours": site_hours, "org_backup_hours": org_hours}


# ── Legacy endpoints (backward compat) ───────────────────────────────────────

@router.post("/trigger")
async def trigger_backup_legacy(user=Depends(get_current_user)):
    """Legacy: trigger full-site backup."""
    return await trigger_site_backup(user=user)


@router.get("")
async def list_backups_legacy(user=Depends(get_current_user)):
    """Legacy: list full-site backups."""
    return await list_site_backups(user=user)


@router.post("/restore/{filename}")
async def restore_backup_legacy(filename: str, user=Depends(get_current_user)):
    """Legacy: restore full-site backup."""
    return await restore_site_backup(filename, user=user)
