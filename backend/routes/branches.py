"""
Branch management routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from config import db, _raw_db
from utils import get_current_user, check_perm, now_iso, new_id, provision_branch_wallets

router = APIRouter(prefix="/branches", tags=["Branches"])


@router.get("")
async def list_branches(user=Depends(get_current_user)):
    """List all active branches."""
    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)
    return branches


@router.post("")
async def create_branch(data: dict, user=Depends(get_current_user)):
    """Create a new branch and auto-provision all 4 fund wallets."""
    check_perm(user, "branches", "create")

    # Enforce subscription branch limit
    org_id = user.get("organization_id")
    if org_id:
        org = await _raw_db.organizations.find_one({"id": org_id}, {"_id": 0})
        if org:
            max_branches = org.get("max_branches", 1)
            if max_branches > 0:  # 0 = unlimited (founders / trial)
                current_count = await db.branches.count_documents({"organization_id": org_id, "active": True})
                if current_count >= max_branches:
                    plan_name = org.get("plan", "basic").title()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Branch limit reached ({current_count}/{max_branches}). "
                               f"Your {plan_name} plan allows {max_branches} branch(es). "
                               f"Upgrade your plan or add an extra branch add-on to continue."
                    )

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
    # Auto-create all 4 wallets for this branch
    await provision_branch_wallets(branch["id"], branch["name"])
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
