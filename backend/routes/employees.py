"""
Employee management routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("")
async def list_employees(user=Depends(get_current_user), branch_id: Optional[str] = None, active: bool = True):
    """List all employees."""
    query = {"active": active}
    if branch_id:
        query["branch_id"] = branch_id
    employees = await db.employees.find(query, {"_id": 0}).to_list(200)
    return employees


@router.post("")
async def create_employee(data: dict, user=Depends(get_current_user)):
    """Create a new employee."""
    check_perm(user, "settings", "manage_users")
    employee = {
        "id": new_id(),
        "name": data["name"],
        "position": data.get("position", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "branch_id": data.get("branch_id", ""),
        "hire_date": data.get("hire_date", now_iso()[:10]),
        "salary": float(data.get("salary", 0)),
        "advance_balance": 0.0,
        "notes": data.get("notes", ""),
        "active": True,
        "created_at": now_iso(),
    }
    await db.employees.insert_one(employee)
    del employee["_id"]
    return employee


@router.get("/{emp_id}")
async def get_employee(emp_id: str, user=Depends(get_current_user)):
    """Get employee details."""
    employee = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/{emp_id}")
async def update_employee(emp_id: str, data: dict, user=Depends(get_current_user)):
    """Update employee details."""
    check_perm(user, "settings", "manage_users")
    allowed = ["name", "position", "phone", "email", "branch_id", "salary", "notes", "active"]
    update = {k: v for k, v in data.items() if k in allowed}
    if "salary" in update:
        update["salary"] = float(update["salary"])
    update["updated_at"] = now_iso()
    await db.employees.update_one({"id": emp_id}, {"$set": update})
    return await db.employees.find_one({"id": emp_id}, {"_id": 0})


@router.delete("/{emp_id}")
async def delete_employee(emp_id: str, user=Depends(get_current_user)):
    """Soft delete an employee."""
    check_perm(user, "settings", "manage_users")
    await db.employees.update_one({"id": emp_id}, {"$set": {"active": False}})
    return {"message": "Employee deleted"}


@router.get("/{emp_id}/advances")
async def get_employee_advances(emp_id: str, user=Depends(get_current_user)):
    """Get advance history for an employee."""
    advances = await db.expenses.find(
        {"employee_id": emp_id, "category": "Employee Advance"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return advances


@router.post("/{emp_id}/deduct-advance")
async def deduct_from_advance(emp_id: str, data: dict, user=Depends(get_current_user)):
    """Deduct from employee's advance balance (e.g., salary deduction)."""
    check_perm(user, "accounting", "create_expense")
    employee = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    amount = float(data["amount"])
    if amount > employee.get("advance_balance", 0):
        raise HTTPException(status_code=400, detail="Amount exceeds advance balance")
    
    await db.employees.update_one({"id": emp_id}, {"$inc": {"advance_balance": -amount}})
    
    # Log the deduction
    log = {
        "id": new_id(),
        "employee_id": emp_id,
        "type": "deduction",
        "amount": amount,
        "reason": data.get("reason", "Salary deduction"),
        "recorded_by": user["id"],
        "recorded_at": now_iso(),
    }
    await db.employee_advance_logs.insert_one(log)
    
    return {"message": "Advance deducted", "new_balance": employee.get("advance_balance", 0) - amount}
