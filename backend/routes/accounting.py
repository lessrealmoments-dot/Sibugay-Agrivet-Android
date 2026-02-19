"""
Accounting routes: Fund wallets, expenses, receivables, payables.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id, update_cashier_wallet,
    get_branch_filter, apply_branch_filter
)

router = APIRouter(tags=["Accounting"])

# Preset expense categories
EXPENSE_CATEGORIES = [
    "Utilities", "Rent", "Supplies", "Transportation", "Fuel/Gas",
    "Employee Advance", "Farm Expense", "Repairs & Maintenance",
    "Marketing", "Salaries & Wages", "Communication", "Insurance",
    "Professional Fees", "Taxes & Licenses", "Office Supplies",
    "Equipment", "Miscellaneous"
]


# ==================== FUND WALLETS ====================
@router.get("/fund-wallets")
async def list_fund_wallets(user=Depends(get_current_user), branch_id: Optional[str] = None):
    """List all fund wallets (cashier drawer, safe, bank accounts)."""
    query = {"active": True}
    if branch_id:
        query["branch_id"] = branch_id
    wallets = await db.fund_wallets.find(query, {"_id": 0}).to_list(50)
    for w in wallets:
        if w["type"] == "safe":
            lots = await db.safe_lots.find(
                {"wallet_id": w["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}
            ).to_list(500)
            w["balance"] = sum(lot["remaining_amount"] for lot in lots)
            w["lots"] = lots
    return wallets


@router.post("/fund-wallets")
async def create_fund_wallet(data: dict, user=Depends(get_current_user)):
    """Create a new fund wallet."""
    check_perm(user, "accounting", "manage_funds")
    wallet = {
        "id": new_id(),
        "branch_id": data["branch_id"],
        "type": data["type"],
        "name": data["name"],
        "balance": float(data.get("balance", 0)),
        "bank_name": data.get("bank_name", ""),
        "account_number": data.get("account_number", ""),
        "active": True,
        "created_at": now_iso(),
    }
    await db.fund_wallets.insert_one(wallet)
    del wallet["_id"]
    return wallet


@router.post("/fund-wallets/{wallet_id}/deposit")
async def deposit_to_wallet(wallet_id: str, data: dict, user=Depends(get_current_user)):
    """Deposit money to a wallet."""
    check_perm(user, "accounting", "manage_funds")
    wallet = await db.fund_wallets.find_one({"id": wallet_id}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    amount = float(data["amount"])
    if wallet["type"] == "safe":
        await db.safe_lots.insert_one({
            "id": new_id(),
            "branch_id": wallet["branch_id"],
            "wallet_id": wallet_id,
            "date_received": data.get("date", now_iso()[:10]),
            "original_amount": amount,
            "remaining_amount": amount,
            "source_reference": data.get("reference", "Manual deposit"),
            "created_by": user["id"],
            "created_at": now_iso()
        })
    else:
        await db.fund_wallets.update_one({"id": wallet_id}, {"$inc": {"balance": amount}})
    
    await db.wallet_movements.insert_one({
        "id": new_id(),
        "wallet_id": wallet_id,
        "branch_id": wallet["branch_id"],
        "type": "deposit",
        "amount": amount,
        "reference": data.get("reference", ""),
        "user_id": user["id"],
        "user_name": user.get("full_name", user["username"]),
        "created_at": now_iso()
    })
    return {"message": "Deposited", "amount": amount}


@router.post("/fund-wallets/pay")
async def pay_from_wallet(data: dict, user=Depends(get_current_user)):
    """Pay from a wallet (deduct funds)."""
    check_perm(user, "accounting", "manage_funds")
    wallet_id = data["wallet_id"]
    amount = float(data["amount"])
    wallet = await db.fund_wallets.find_one({"id": wallet_id}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if wallet["type"] == "safe":
        lots = await db.safe_lots.find(
            {"wallet_id": wallet_id, "remaining_amount": {"$gt": 0}}, {"_id": 0}
        ).sort("remaining_amount", -1).to_list(500)
        total_available = sum(lot["remaining_amount"] for lot in lots)
        if total_available < amount:
            raise HTTPException(status_code=400, detail="Insufficient Safe balance")
        remaining = amount
        usages = []
        for lot in lots:
            if remaining <= 0:
                break
            take = min(lot["remaining_amount"], remaining)
            await db.safe_lots.update_one({"id": lot["id"]}, {"$inc": {"remaining_amount": -take}})
            usages.append({"lot_id": lot["id"], "lot_date": lot["date_received"], "amount_used": take})
            await db.safe_lot_usages.insert_one({
                "id": new_id(),
                "lot_id": lot["id"],
                "payment_id": data.get("reference_id", ""),
                "branch_id": wallet["branch_id"],
                "amount_used": take,
                "used_by_user_id": user["id"],
                "used_at": now_iso()
            })
            remaining -= take
        summary = ", ".join([f"{u['lot_date']} lot: ₱{u['amount_used']:.2f}" for u in usages])
    else:
        if wallet["balance"] < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient {wallet['type']} balance")
        await db.fund_wallets.update_one({"id": wallet_id}, {"$inc": {"balance": -amount}})
        summary = f"Deducted ₱{amount:.2f} from {wallet['name']}"
    
    await db.wallet_movements.insert_one({
        "id": new_id(),
        "wallet_id": wallet_id,
        "branch_id": wallet["branch_id"],
        "type": "payment",
        "amount": -amount,
        "reference": data.get("reference", ""),
        "description": data.get("description", ""),
        "user_id": user["id"],
        "user_name": user.get("full_name", user["username"]),
        "created_at": now_iso()
    })
    return {"message": "Payment processed", "summary": summary}


@router.get("/safe-lots")
async def list_safe_lots(user=Depends(get_current_user), branch_id: Optional[str] = None):
    """List safe lots with remaining balance."""
    query = {"remaining_amount": {"$gt": 0}}
    if branch_id:
        query["branch_id"] = branch_id
    lots = await db.safe_lots.find(query, {"_id": 0}).sort("date_received", 1).to_list(500)
    return lots


@router.get("/fund-wallets/{wallet_id}/movements")
async def get_wallet_movements(wallet_id: str, user=Depends(get_current_user), limit: int = 50):
    """Get movement history for a wallet."""
    movements = await db.wallet_movements.find(
        {"wallet_id": wallet_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return movements


# ==================== EXPENSES ====================
@router.get("/expenses")
async def list_expenses(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    category: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List expenses with optional filters."""
    check_perm(user, "accounting", "view")
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    if category:
        query["category"] = category
    if payment_method:
        query["payment_method"] = payment_method
    if date_from:
        query["date"] = {"$gte": date_from}
    if date_to:
        query.setdefault("date", {})["$lte"] = date_to
    if search:
        query["$or"] = [
            {"description": {"$regex": search, "$options": "i"}},
            {"reference_number": {"$regex": search, "$options": "i"}},
            {"notes": {"$regex": search, "$options": "i"}},
        ]
    total = await db.expenses.count_documents(query)
    expenses = await db.expenses.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"expenses": expenses, "total": total}


@router.get("/expenses/categories")
async def get_expense_categories(user=Depends(get_current_user)):
    """Get preset expense categories."""
    return EXPENSE_CATEGORIES


@router.post("/expenses")
async def create_expense(data: dict, user=Depends(get_current_user)):
    """Create a new expense."""
    check_perm(user, "accounting", "create_expense")
    expense = {
        "id": new_id(),
        "branch_id": data["branch_id"],
        "category": data.get("category", "Miscellaneous"),
        "description": data.get("description", ""),
        "notes": data.get("notes", ""),
        "amount": float(data["amount"]),
        "payment_method": data.get("payment_method", "Cash"),
        "reference_number": data.get("reference_number", ""),
        "date": data.get("date", now_iso()[:10]),
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)
    
    ref_text = f"Expense: {data.get('category', 'General')} - {data.get('description', '')}"
    if data.get("reference_number"):
        ref_text += f" (Ref: {data['reference_number']})"
    await update_cashier_wallet(data["branch_id"], -float(data["amount"]), ref_text)
    
    del expense["_id"]
    return expense


@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: str, data: dict, user=Depends(get_current_user)):
    """Update an existing expense."""
    check_perm(user, "accounting", "edit_expense")
    expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    old_amount = expense.get("amount", 0)
    new_amount = float(data.get("amount", old_amount))
    amount_diff = new_amount - old_amount
    
    allowed = ["category", "description", "notes", "amount", "payment_method", "reference_number", "date"]
    update = {k: v for k, v in data.items() if k in allowed}
    if "amount" in update:
        update["amount"] = float(update["amount"])
    update["updated_at"] = now_iso()
    update["updated_by"] = user["id"]
    update["updated_by_name"] = user.get("full_name", user["username"])
    
    await db.expenses.update_one({"id": expense_id}, {"$set": update})
    
    if amount_diff != 0:
        await update_cashier_wallet(
            expense["branch_id"],
            -amount_diff,
            f"Expense adjusted: {expense.get('description', '')} ({'+' if amount_diff > 0 else ''}{amount_diff:.2f})"
        )
    
    return await db.expenses.find_one({"id": expense_id}, {"_id": 0})


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, user=Depends(get_current_user)):
    """Delete an expense and refund to wallet."""
    check_perm(user, "accounting", "edit_expense")
    expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    await update_cashier_wallet(
        expense["branch_id"],
        expense["amount"],
        f"Expense deleted: {expense.get('description', '')}"
    )
    await db.expenses.delete_one({"id": expense_id})
    return {"message": "Expense deleted and funds returned"}


@router.post("/expenses/farm")
async def create_farm_expense_with_invoice(data: dict, user=Depends(get_current_user)):
    """Create a farm expense and auto-generate an invoice for the customer."""
    check_perm(user, "accounting", "create_expense")
    
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer is required for farm expense")
    
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    amount = float(data["amount"])
    branch_id = data["branch_id"]
    
    expense = {
        "id": new_id(),
        "branch_id": branch_id,
        "category": "Farm Expense",
        "description": data.get("description", "Farm Service"),
        "notes": data.get("notes", ""),
        "amount": amount,
        "payment_method": data.get("payment_method", "Cash"),
        "reference_number": data.get("reference_number", ""),
        "date": data.get("date", now_iso()[:10]),
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "linked_invoice_id": None,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await update_cashier_wallet(branch_id, -amount, f"Farm Expense for {customer.get('name', '')}: {data.get('description', '')}")
    
    # Auto-generate invoice
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("service_invoice", "SVC") if settings else "SVC"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"
    
    invoice = {
        "id": new_id(),
        "invoice_number": inv_number,
        "prefix": prefix,
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "branch_id": branch_id,
        "order_date": data.get("date", now_iso()[:10]),
        "invoice_date": data.get("date", now_iso()[:10]),
        "due_date": data.get("date", now_iso()[:10]),
        "items": [{
            "product_id": "",
            "product_name": f"Farm Service: {data.get('description', 'Farm Expense')}",
            "description": data.get("notes", ""),
            "quantity": 1,
            "rate": amount,
            "discount_type": "amount",
            "discount_value": 0,
            "discount_amount": 0,
            "total": amount,
        }],
        "subtotal": amount,
        "freight": 0,
        "overall_discount": 0,
        "grand_total": amount,
        "amount_paid": 0,
        "balance": amount,
        "interest_rate": customer.get("interest_rate", 0),
        "interest_accrued": 0,
        "penalties": 0,
        "last_interest_date": None,
        "sale_type": "farm_expense",
        "status": "open",
        "payments": [],
        "cashier_id": user["id"],
        "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await db.invoices.insert_one(invoice)
    del invoice["_id"]
    
    expense["linked_invoice_id"] = invoice["id"]
    await db.expenses.insert_one(expense)
    del expense["_id"]
    
    # Update customer balance
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": amount}})
    
    return {"expense": expense, "invoice": invoice}


@router.post("/expenses/customer-cashout")
async def create_customer_cashout(data: dict, user=Depends(get_current_user)):
    """Create a cash-out expense for a customer (advance/loan)."""
    check_perm(user, "accounting", "create_expense")
    
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer is required")
    
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    amount = float(data["amount"])
    branch_id = data["branch_id"]
    
    expense = {
        "id": new_id(),
        "branch_id": branch_id,
        "category": "Customer Cash-out",
        "description": data.get("description", f"Cash advance to {customer.get('name', '')}"),
        "notes": data.get("notes", ""),
        "amount": amount,
        "payment_method": "Cash",
        "date": data.get("date", now_iso()[:10]),
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await update_cashier_wallet(branch_id, -amount, f"Cash-out to {customer.get('name', '')}")
    
    # Create invoice for tracking
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("cash_advance", "CA") if settings else "CA"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"
    
    invoice = {
        "id": new_id(),
        "invoice_number": inv_number,
        "prefix": prefix,
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "branch_id": branch_id,
        "order_date": data.get("date", now_iso()[:10]),
        "invoice_date": data.get("date", now_iso()[:10]),
        "due_date": data.get("date", now_iso()[:10]),
        "items": [{
            "product_id": "",
            "product_name": "Cash Advance",
            "description": data.get("notes", ""),
            "quantity": 1,
            "rate": amount,
            "total": amount,
        }],
        "subtotal": amount,
        "grand_total": amount,
        "amount_paid": 0,
        "balance": amount,
        "interest_rate": customer.get("interest_rate", 0),
        "interest_accrued": 0,
        "penalties": 0,
        "sale_type": "cash_advance",
        "status": "open",
        "payments": [],
        "cashier_id": user["id"],
        "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await db.invoices.insert_one(invoice)
    del invoice["_id"]
    
    expense["linked_invoice_id"] = invoice["id"]
    await db.expenses.insert_one(expense)
    del expense["_id"]
    
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": amount}})
    
    return {"expense": expense, "invoice": invoice}


@router.post("/expenses/employee-advance")
async def create_employee_advance(data: dict, user=Depends(get_current_user)):
    """Create an employee advance expense."""
    check_perm(user, "accounting", "create_expense")
    
    employee_id = data.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee is required")
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    amount = float(data["amount"])
    branch_id = data["branch_id"]
    
    expense = {
        "id": new_id(),
        "branch_id": branch_id,
        "category": "Employee Advance",
        "description": data.get("description", f"Advance to {employee.get('name', '')}"),
        "notes": data.get("notes", ""),
        "amount": amount,
        "payment_method": "Cash",
        "date": data.get("date", now_iso()[:10]),
        "employee_id": employee_id,
        "employee_name": employee.get("name", ""),
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    await update_cashier_wallet(branch_id, -amount, f"Employee advance to {employee.get('name', '')}")
    await db.employees.update_one({"id": employee_id}, {"$inc": {"advance_balance": amount}})
    await db.expenses.insert_one(expense)
    del expense["_id"]
    
    return expense


# ==================== RECEIVABLES ====================
@router.get("/receivables")
async def list_receivables(user=Depends(get_current_user), branch_id: Optional[str] = None, status: Optional[str] = None):
    """List receivables (legacy AR system)."""
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    if status:
        query["status"] = status
    receivables = await db.receivables.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return receivables


@router.post("/receivables/{rec_id}/payment")
async def pay_receivable(rec_id: str, data: dict, user=Depends(get_current_user)):
    """Record payment on a receivable."""
    check_perm(user, "accounting", "receive_payment")
    rec = await db.receivables.find_one({"id": rec_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Receivable not found")
    
    amount = float(data["amount"])
    new_balance = max(0, round(rec["balance"] - amount, 2))
    new_paid = rec.get("paid", 0) + amount
    
    await db.receivables.update_one({"id": rec_id}, {
        "$set": {"balance": new_balance, "paid": new_paid, "status": "paid" if new_balance <= 0 else "partial"}
    })
    
    return {"message": "Payment recorded", "new_balance": new_balance}


# ==================== PAYABLES ====================
@router.get("/payables")
async def list_payables(user=Depends(get_current_user), branch_id: Optional[str] = None, status: Optional[str] = None):
    """List payables (amounts owed to suppliers)."""
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    if status:
        query["status"] = status
    payables = await db.payables.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return payables


@router.post("/payables")
async def create_payable(data: dict, user=Depends(get_current_user)):
    """Create a new payable."""
    check_perm(user, "accounting", "create_expense")
    payable = {
        "id": new_id(),
        "supplier": data["supplier"],
        "branch_id": data.get("branch_id", ""),
        "description": data.get("description", ""),
        "amount": float(data["amount"]),
        "paid": 0,
        "balance": float(data["amount"]),
        "due_date": data.get("due_date", ""),
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.payables.insert_one(payable)
    del payable["_id"]
    return payable


@router.post("/payables/{pay_id}/payment")
async def pay_payable(pay_id: str, data: dict, user=Depends(get_current_user)):
    """Record payment on a payable."""
    check_perm(user, "accounting", "create_expense")
    pay = await db.payables.find_one({"id": pay_id}, {"_id": 0})
    if not pay:
        raise HTTPException(status_code=404, detail="Payable not found")
    
    amount = float(data["amount"])
    new_paid = pay.get("paid", 0) + amount
    new_balance = max(0, round(pay["amount"] - new_paid, 2))
    
    await db.payables.update_one({"id": pay_id}, {
        "$set": {"paid": new_paid, "balance": new_balance, "status": "paid" if new_balance <= 0 else "partial"}
    })
    
    if data.get("deduct_from_wallet"):
        await update_cashier_wallet(pay.get("branch_id", ""), -amount, f"Payable payment: {pay.get('supplier', '')}")
    
    return {"message": "Payment recorded", "new_balance": new_balance}


# ==================== CUSTOMER INTEREST/PENALTY GENERATION ====================
@router.get("/customers/{customer_id}/charges-preview")
async def preview_customer_charges(customer_id: str, as_of_date: Optional[str] = None, user=Depends(get_current_user)):
    """Preview interest and penalty charges for a customer WITHOUT creating invoices."""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    comp_date_str = as_of_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d")
    
    grace_period = customer.get("grace_period", 7)
    default_interest_rate = customer.get("interest_rate", 0)
    
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}}, {"_id": 0}
    ).to_list(500)
    
    interest_preview = []
    penalty_preview = []
    total_interest = 0
    total_penalty = 0
    total_principal = 0
    
    for inv in invoices:
        if inv.get("sale_type") in ("interest_charge", "penalty_charge"):
            continue
        
        rate = inv.get("interest_rate") or default_interest_rate
        due_date_str = inv.get("due_date") or inv.get("order_date") or comp_date_str
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        grace_end_date = due_date + timedelta(days=grace_period)
        days_overdue = max(0, (comp_date - due_date).days)
        days_for_interest = max(0, (comp_date - grace_end_date).days)
        
        principal = inv.get("balance", 0) - inv.get("interest_accrued", 0) - inv.get("penalties", 0)
        total_principal += max(0, principal)
        
        if rate > 0 and days_for_interest > 0 and principal > 0:
            monthly_rate = rate / 100
            daily_rate = monthly_rate / 30
            interest = round(principal * daily_rate * days_for_interest, 2)
            total_interest += interest
            interest_preview.append({
                "invoice_number": inv.get("invoice_number", ""),
                "invoice_id": inv["id"],
                "principal": principal,
                "rate": rate,
                "days_overdue": days_overdue,
                "days_for_interest": days_for_interest,
                "grace_period": grace_period,
                "interest_amount": interest,
            })
    
    return {
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "as_of_date": comp_date_str,
        "total_principal": total_principal,
        "total_interest": total_interest,
        "total_penalty": total_penalty,
        "interest_preview": interest_preview,
        "penalty_preview": penalty_preview,
    }


@router.post("/customers/{customer_id}/receive-payment")
async def receive_customer_payment(customer_id: str, data: dict, user=Depends(get_current_user)):
    """Receive payment from a customer and apply to invoices."""
    check_perm(user, "accounting", "receive_payment")
    
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    amount = float(data["amount"])
    branch_id = data.get("branch_id", "")
    
    invoice_id = data.get("invoice_id")
    if invoice_id:
        inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        interest_owed = inv.get("interest_accrued", 0) + inv.get("penalties", 0)
        applied_interest = min(amount, interest_owed)
        applied_principal = amount - applied_interest
        new_interest = max(0, round(inv.get("interest_accrued", 0) - applied_interest, 2))
        new_balance = round(inv["balance"] - amount, 2)
        new_paid = round(inv["amount_paid"] + amount, 2)
        new_status = "paid" if new_balance <= 0 else "partial"
        
        payment = {
            "id": new_id(),
            "amount": amount,
            "date": data.get("date", now_iso()[:10]),
            "method": data.get("method", "Cash"),
            "reference": data.get("reference", ""),
            "applied_to_interest": applied_interest,
            "applied_to_principal": applied_principal,
            "recorded_by": user.get("full_name", user["username"]),
            "recorded_at": now_iso(),
        }
        
        await db.invoices.update_one({"id": invoice_id}, {
            "$set": {"balance": max(0, new_balance), "amount_paid": new_paid, "interest_accrued": new_interest, "status": new_status},
            "$push": {"payments": payment}
        })
    
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": -amount}})
    await update_cashier_wallet(branch_id, amount, f"Payment from {customer.get('name', '')} - {data.get('reference', '')}")
    
    return {"message": "Payment received", "amount": amount}
