"""
Employee management routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
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
        "employment_type": data.get("employment_type", "regular"),  # regular, contractual, daily_wage
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "branch_id": data.get("branch_id", ""),
        "hire_date": data.get("hire_date", now_iso()[:10]),
        "salary": float(data.get("salary", 0)),
        "daily_rate": float(data.get("daily_rate", 0)),
        "monthly_ca_limit": float(data.get("monthly_ca_limit", 0)),  # 0 = no limit
        "advance_balance": 0.0,  # Total unpaid cash advances
        "sss_number": data.get("sss_number", ""),
        "philhealth_number": data.get("philhealth_number", ""),
        "pagibig_number": data.get("pagibig_number", ""),
        "tin_number": data.get("tin_number", ""),
        "emergency_contact_name": data.get("emergency_contact_name", ""),
        "emergency_contact_phone": data.get("emergency_contact_phone", ""),
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
    allowed = [
        "name", "position", "employment_type", "phone", "email", "address",
        "branch_id", "salary", "daily_rate", "monthly_ca_limit", "hire_date",
        "sss_number", "philhealth_number", "pagibig_number", "tin_number",
        "emergency_contact_name", "emergency_contact_phone", "notes", "active"
    ]
    update = {k: v for k, v in data.items() if k in allowed}
    for f in ("salary", "daily_rate", "monthly_ca_limit"):
        if f in update:
            update[f] = float(update[f])
    update["updated_at"] = now_iso()
    await db.employees.update_one({"id": emp_id}, {"$set": update})
    return await db.employees.find_one({"id": emp_id}, {"_id": 0})


@router.delete("/{emp_id}")
async def delete_employee(emp_id: str, user=Depends(get_current_user)):
    """Soft delete an employee."""
    check_perm(user, "settings", "manage_users")
    await db.employees.update_one({"id": emp_id}, {"$set": {"active": False}})
    return {"message": "Employee deleted"}


@router.get("/{emp_id}/ca-summary")
async def get_employee_ca_summary(emp_id: str, user=Depends(get_current_user)):
    """Get Cash Advance summary for an employee (current month, previous month overage)."""
    employee = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    month_start = f"{year}-{month:02d}-01"

    # Previous month bounds
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    prev_start = f"{prev_year}-{prev_month:02d}-01"
    prev_end = month_start

    # Aggregation helpers
    async def sum_ca(date_filter):
        res = await db.expenses.aggregate([
            {"$match": {"employee_id": emp_id, "category": "Employee Advance", "date": date_filter}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)
        return res[0]["total"] if res else 0

    this_month_total = await sum_ca({"$gte": month_start})
    prev_month_total = await sum_ca({"$gte": prev_start, "$lt": prev_end})

    monthly_limit = float(employee.get("monthly_ca_limit", 0))
    prev_overage = max(0, prev_month_total - monthly_limit) if monthly_limit > 0 else 0
    remaining = max(0, monthly_limit - this_month_total) if monthly_limit > 0 else None
    is_over_limit = monthly_limit > 0 and this_month_total >= monthly_limit

    # Recent advances this month
    recent = await db.expenses.find(
        {"employee_id": emp_id, "category": "Employee Advance", "date": {"$gte": month_start}},
        {"_id": 0}
    ).sort("date", -1).to_list(20)

    return {
        "employee_id": emp_id,
        "employee_name": employee["name"],
        "monthly_ca_limit": monthly_limit,
        "this_month_total": this_month_total,
        "prev_month_total": prev_month_total,
        "prev_month_overage": prev_overage,  # Amount over limit last month
        "remaining_this_month": remaining,
        "total_advance_balance": float(employee.get("advance_balance", 0)),
        "is_over_limit": is_over_limit,
        "recent_advances": recent,
    }


@router.get("/{emp_id}/advances")
async def get_employee_advances(emp_id: str, user=Depends(get_current_user)):
    """Get full advance history for an employee."""
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

    log = {
        "id": new_id(),
        "employee_id": emp_id,
        "employee_name": employee["name"],
        "type": "deduction",
        "amount": amount,
        "reason": data.get("reason", "Salary deduction"),
        "recorded_by": user["id"],
        "recorded_by_name": user.get("full_name", user["username"]),
        "recorded_at": now_iso(),
    }
    await db.employee_advance_logs.insert_one(log)
    del log["_id"]
    return {"message": "Advance deducted", "new_balance": employee.get("advance_balance", 0) - amount, "log": log}
