"""
Branch management routes.
"""
from fastapi import APIRouter, Depends
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/branches", tags=["Branches"])


@router.get("")
async def list_branches(user=Depends(get_current_user)):
    """List all active branches."""
    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)
    return branches


@router.post("")
async def create_branch(data: dict, user=Depends(get_current_user)):
    """Create a new branch."""
    check_perm(user, "branches", "create")
    
    branch = {
        "id": new_id(),
        "name": data["name"],
        "address": data.get("address", ""),
        "phone": data.get("phone", ""),
        "active": True,
        "created_at": now_iso()
    }
    await db.branches.insert_one(branch)
    del branch["_id"]
    return branch


@router.put("/{branch_id}")
async def update_branch(branch_id: str, data: dict, user=Depends(get_current_user)):
    """Update branch details."""
    check_perm(user, "branches", "edit")
    
    update = {k: v for k, v in data.items() if k in ("name", "address", "phone")}
    update["updated_at"] = now_iso()
    
    await db.branches.update_one({"id": branch_id}, {"$set": update})
    branch = await db.branches.find_one({"id": branch_id}, {"_id": 0})
    return branch


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str, user=Depends(get_current_user)):
    """Soft delete a branch."""
    check_perm(user, "branches", "delete")
    await db.branches.update_one({"id": branch_id}, {"$set": {"active": False}})
    return {"message": "Branch deleted"}
