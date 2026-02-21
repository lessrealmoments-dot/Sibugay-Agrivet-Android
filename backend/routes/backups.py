"""
Backup API routes — manual trigger, list, and restore.
Automatic schedule is wired up in main.py via APScheduler.
"""
from fastapi import APIRouter, Depends, HTTPException
from config import db
from utils import get_current_user
from services.backup_service import (
    create_backup, list_backups, restore_backup, delete_old_local_backups
)
import os

router = APIRouter(prefix="/backups", tags=["Backups"])

DB_NAME = os.environ.get("DB_NAME", "agripos_production")


@router.post("/create")
async def trigger_backup(user=Depends(get_current_user)):
    """Manually trigger a database backup (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    result = await create_backup(DB_NAME)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/list")
async def get_backup_list(user=Depends(get_current_user)):
    """List all available backups."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    backups = await list_backups(DB_NAME)
    return {"backups": backups, "count": len(backups)}


@router.post("/restore/{filename}")
async def restore_from_backup(filename: str, user=Depends(get_current_user)):
    """Restore database from a specific backup file (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    result = await restore_backup(DB_NAME, filename)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
