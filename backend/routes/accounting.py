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
    """Create a new expense. If category is 'Employee Advance', updates employee's advance balance."""
    check_perm(user, "accounting", "create_expense")
    branch_id = data.get("branch_id") or ""  # Safe: never raise KeyError
    if not branch_id:
        raise HTTPException(status_code=400, detail="Branch is required. Please select a specific branch before recording expenses.")
    expense = {
        "id": new_id(),
        "branch_id": branch_id,
        "category": data.get("category", "Miscellaneous"),
        "description": data.get("description", ""),
        "notes": data.get("notes", ""),
        "amount": float(data["amount"]),
        "payment_method": data.get("payment_method", "Cash"),
        "reference_number": data.get("reference_number", ""),
        "date": data.get("date", now_iso()[:10]),
        # Employee CA fields
        "employee_id": data.get("employee_id", ""),
        "employee_name": data.get("employee_name", ""),
        "manager_approved_by": data.get("manager_approved_by", ""),
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)

    # If Employee Advance: update employee's advance balance
    if expense["category"] == "Employee Advance" and expense.get("employee_id"):
        await db.employees.update_one(
            {"id": expense["employee_id"]},
            {"$inc": {"advance_balance": expense["amount"]}, "$set": {"updated_at": now_iso()}}
        )

    ref_text = f"Expense: {data.get('category', 'General')} - {data.get('description', '')}"
    if data.get("reference_number"):
        ref_text += f" (Ref: {data['reference_number']})"
    if data.get("employee_name"):
        ref_text += f" [{data['employee_name']}]"
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
    """
    Void an expense and return the funds to the ORIGINAL fund source.
    FIX: uses the expense's own fund_source, not always cashier.
    """
    check_perm(user, "accounting", "edit_expense")
    expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.get("voided"):
        raise HTTPException(status_code=400, detail="Expense is already voided")

    branch_id = expense["branch_id"]
    amount = float(expense.get("amount", 0))
    fund_source = expense.get("fund_source", "cashier")
    ref_text = f"Expense voided: {expense.get('description', '')}"

    # Return funds to the ORIGINAL source (not always cashier)
    if amount > 0:
        if fund_source == "safe":
            safe_wallet = await db.fund_wallets.find_one(
                {"branch_id": branch_id, "type": "safe", "active": True}, {"_id": 0}
            )
            if safe_wallet:
                await db.safe_lots.insert_one({
                    "id": new_id(), "branch_id": branch_id,
                    "wallet_id": safe_wallet["id"],
                    "date_received": now_iso()[:10],
                    "original_amount": amount,
                    "remaining_amount": amount,
                    "source_reference": ref_text,
                    "created_by": user["id"],
                    "created_at": now_iso(),
                })
        else:
            await update_cashier_wallet(branch_id, amount, ref_text)

    # Soft-void: keep the record for audit trail
    await db.expenses.update_one(
        {"id": expense_id},
        {"$set": {
            "voided": True,
            "voided_at": now_iso(),
            "voided_by": user.get("full_name", user["username"]),
            "void_reason": "Manually deleted",
        }}
    )

    # Reverse employee advance balance if applicable
    if expense.get("category") == "Employee Advance" and expense.get("employee_id") and amount > 0:
        await db.employees.update_one(
            {"id": expense["employee_id"]},
            {"$inc": {"advance_balance": -amount}, "$set": {"updated_at": now_iso()}}
        )

    return {"message": f"Expense voided and ₱{amount:,.2f} returned to {fund_source}"}


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
    """
    List all outstanding receivables — reads from invoices collection (the live AR system).
    Includes farm expenses, cash advances, credit sales, and partial payments.
    Legacy 'receivables' collection is no longer used.
    """
    query = {"customer_id": {"$ne": None}, "balance": {"$gt": 0}, "status": {"$nin": ["voided", "paid"]}}
    if branch_id:
        query["branch_id"] = branch_id
    if status:
        query["status"] = status

    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    TYPE_LABELS = {
        "farm_expense": "Farm Expense",
        "cash_advance": "Customer Cash Out",  # Never "Cash Advance" — reserved for employee advances
        "interest_charge": "Interest Charge",
        "penalty_charge": "Penalty Charge",
        "walk_in": "Credit Sale",
    }

    result = []
    for inv in invoices:
        sale_type = inv.get("sale_type", "walk_in")
        type_label = TYPE_LABELS.get(sale_type, "Invoice")
        items_preview = ", ".join(i.get("product_name", "Service") for i in inv.get("items", [])[:2])
        description = f"{type_label}: {items_preview}" if items_preview else type_label

        result.append({
            "id": inv["id"],
            "invoice_id": inv["id"],
            "invoice_number": inv.get("invoice_number", ""),
            "customer_id": inv.get("customer_id"),
            "customer_name": inv.get("customer_name", ""),
            "description": description,
            "amount": inv.get("grand_total", 0),
            "paid": inv.get("amount_paid", 0),
            "balance": inv.get("balance", 0),
            "status": inv.get("status", "open"),
            "due_date": inv.get("due_date", ""),
            "sale_type": sale_type,
            "created_at": inv.get("created_at", ""),
        })

    return result


@router.post("/receivables/{rec_id}/payment")
async def pay_receivable(rec_id: str, data: dict, user=Depends(get_current_user)):
    """
    Record payment on a receivable (invoice). Updates invoice, customer balance, and cashier wallet.
    rec_id is an invoice ID — the legacy receivables collection is no longer used.
    """
    check_perm(user, "accounting", "receive_payment")

    inv = await db.invoices.find_one({"id": rec_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice/Receivable not found")
    if inv.get("balance", 0) <= 0:
        raise HTTPException(status_code=400, detail="Already fully paid")

    amount = float(data["amount"])
    amount = min(amount, inv["balance"])  # Cap at balance
    new_balance = max(0, round(inv["balance"] - amount, 2))
    new_paid = round(inv.get("amount_paid", 0) + amount, 2)
    new_status = "paid" if new_balance <= 0 else "partial"

    payment_record = {
        "id": new_id(),
        "amount": amount,
        "date": data.get("date", now_iso()[:10]),
        "method": data.get("method", "Cash"),
        "reference": data.get("reference", ""),
        "fund_source": "cashier",
        "applied_to_interest": 0,
        "applied_to_principal": amount,
        "recorded_by": user.get("full_name", user["username"]),
        "recorded_at": now_iso(),
    }

    await db.invoices.update_one({"id": rec_id}, {
        "$set": {"balance": new_balance, "amount_paid": new_paid, "status": new_status},
        "$push": {"payments": payment_record}
    })

    # Update customer balance
    if inv.get("customer_id"):
        await db.customers.update_one({"id": inv["customer_id"]}, {"$inc": {"balance": -amount}})

    # Update cashier wallet
    branch_id = inv.get("branch_id", "")
    if branch_id:
        await update_cashier_wallet(branch_id, amount, f"Receivable payment {inv.get('invoice_number', '')} — {inv.get('customer_name', '')}")

    return {"message": "Payment recorded", "new_balance": new_balance, "status": new_status}


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


# ==================== CUSTOMER INVOICE / PAYMENT MANAGEMENT ====================

@router.get("/customers/{customer_id}/invoices")
async def get_customer_open_invoices(customer_id: str, user=Depends(get_current_user)):
    """Get all open invoices for a customer. Sorted: penalty → interest → regular (oldest first)."""
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}},
        {"_id": 0}
    ).to_list(500)

    def sort_key(inv):
        t = inv.get("sale_type", "regular")
        if t == "penalty_charge":
            return (0, inv.get("order_date", ""))
        if t == "interest_charge":
            return (1, inv.get("order_date", ""))
        return (2, inv.get("order_date", ""))

    invoices.sort(key=sort_key)
    return invoices


@router.post("/customers/{customer_id}/generate-interest")
async def generate_interest_invoice(customer_id: str, data: dict, user=Depends(get_current_user)):
    """Calculate accrued interest for all overdue invoices and create one consolidated interest invoice."""
    check_perm(user, "accounting", "create_expense")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    as_of_str = data.get("as_of_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    comp_date = datetime.strptime(as_of_str, "%Y-%m-%d")
    grace_period = int(customer.get("grace_period", 7))
    default_rate = float(customer.get("interest_rate", 0))

    if not default_rate:
        return {"message": "Customer has no interest rate configured", "total_interest": 0, "grace_period": grace_period}

    open_invoices = await db.invoices.find(
        {"customer_id": customer_id, "balance": {"$gt": 0},
         "status": {"$nin": ["voided", "paid"]},
         "sale_type": {"$nin": ["interest_charge", "penalty_charge"]}},
        {"_id": 0}
    ).to_list(500)

    interest_lines, total_interest, branch_id = [], 0, ""

    for inv in open_invoices:
        rate = float(inv.get("interest_rate") or default_rate)
        if rate <= 0:
            continue
        due_str = inv.get("due_date") or inv.get("order_date") or as_of_str
        due_date = datetime.strptime(due_str, "%Y-%m-%d")
        grace_end = due_date + timedelta(days=grace_period)
        last_int_str = inv.get("last_interest_date")
        start_date = datetime.strptime(last_int_str, "%Y-%m-%d") if last_int_str else grace_end
        days = max(0, (comp_date - start_date).days)
        if days <= 0:
            continue
        principal = max(0, inv.get("balance", 0) - inv.get("interest_accrued", 0) - inv.get("penalties", 0))
        if principal <= 0:
            continue
        interest = round(principal * (rate / 100 / 30) * days, 2)
        total_interest += interest
        branch_id = inv.get("branch_id", branch_id)
        interest_lines.append({
            "product_id": "", "product_name": f"Interest — {inv.get('invoice_number','')} ({days}d × {rate}%/mo)",
            "description": f"Principal ₱{principal:.2f} | {start_date.strftime('%b %d')} – {comp_date.strftime('%b %d, %Y')}",
            "quantity": 1, "rate": interest, "discount_type": "amount",
            "discount_value": 0, "discount_amount": 0, "total": interest,
            "source_invoice_id": inv["id"], "source_invoice_number": inv.get("invoice_number", ""),
        })
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"last_interest_date": as_of_str}})

    if total_interest <= 0:
        return {"message": "No interest accrued — invoices still within grace period", "total_interest": 0, "grace_period": grace_period}

    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("interest_charge", "INT") if settings else "INT"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"

    interest_invoice = {
        "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
        "customer_id": customer_id, "customer_name": customer.get("name", ""),
        "branch_id": branch_id, "order_date": as_of_str, "invoice_date": as_of_str, "due_date": as_of_str,
        "items": interest_lines, "subtotal": round(total_interest, 2), "freight": 0, "overall_discount": 0,
        "grand_total": round(total_interest, 2), "amount_paid": 0, "balance": round(total_interest, 2),
        "interest_rate": 0, "interest_accrued": 0, "penalties": 0, "last_interest_date": None,
        "sale_type": "interest_charge", "status": "open", "payments": [],
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]), "created_at": now_iso(),
    }
    await db.invoices.insert_one(interest_invoice)
    del interest_invoice["_id"]
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": round(total_interest, 2)}})

    return {"message": "Interest invoice created", "invoice_number": inv_number,
            "total_interest": round(total_interest, 2), "invoice": interest_invoice}


@router.post("/customers/{customer_id}/generate-penalty")
async def generate_penalty_invoice(customer_id: str, data: dict, user=Depends(get_current_user)):
    """Generate a one-time penalty invoice for all overdue invoices not yet penalized."""
    check_perm(user, "accounting", "create_expense")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    penalty_rate = float(data.get("penalty_rate", 5))
    as_of_str = data.get("as_of_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    comp_date = datetime.strptime(as_of_str, "%Y-%m-%d")
    grace_period = int(customer.get("grace_period", 7))

    open_invoices = await db.invoices.find(
        {"customer_id": customer_id, "balance": {"$gt": 0},
         "status": {"$nin": ["voided", "paid"]},
         "sale_type": {"$nin": ["interest_charge", "penalty_charge"]},
         "penalty_applied": {"$ne": True}},
        {"_id": 0}
    ).to_list(500)

    penalty_lines, total_penalty, branch_id = [], 0, ""

    for inv in open_invoices:
        due_str = inv.get("due_date") or inv.get("order_date") or as_of_str
        due_date = datetime.strptime(due_str, "%Y-%m-%d")
        if comp_date <= due_date + timedelta(days=grace_period):
            continue
        principal = max(0, inv.get("balance", 0) - inv.get("penalties", 0))
        if principal <= 0:
            continue
        penalty = round(principal * penalty_rate / 100, 2)
        total_penalty += penalty
        branch_id = inv.get("branch_id", branch_id)
        penalty_lines.append({
            "product_id": "", "product_name": f"Penalty — {inv.get('invoice_number','')} ({penalty_rate}%)",
            "description": f"Overdue balance ₱{principal:.2f} × {penalty_rate}%",
            "quantity": 1, "rate": penalty, "discount_type": "amount",
            "discount_value": 0, "discount_amount": 0, "total": penalty,
            "source_invoice_id": inv["id"], "source_invoice_number": inv.get("invoice_number", ""),
        })
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"penalty_applied": True, "last_penalty_date": as_of_str}})

    if total_penalty <= 0:
        return {"message": "No penalties applicable — invoices within grace period or already penalized", "total_penalty": 0, "grace_period": grace_period}

    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("penalty_charge", "PEN") if settings else "PEN"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"

    penalty_invoice = {
        "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
        "customer_id": customer_id, "customer_name": customer.get("name", ""),
        "branch_id": branch_id, "order_date": as_of_str, "invoice_date": as_of_str, "due_date": as_of_str,
        "items": penalty_lines, "subtotal": round(total_penalty, 2), "freight": 0, "overall_discount": 0,
        "grand_total": round(total_penalty, 2), "amount_paid": 0, "balance": round(total_penalty, 2),
        "interest_rate": 0, "interest_accrued": 0, "penalties": 0, "last_interest_date": None,
        "sale_type": "penalty_charge", "status": "open", "payments": [], "penalty_rate_applied": penalty_rate,
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]), "created_at": now_iso(),
    }
    await db.invoices.insert_one(penalty_invoice)
    del penalty_invoice["_id"]
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": round(total_penalty, 2)}})

    return {"message": "Penalty invoice created", "invoice_number": inv_number,
            "total_penalty": round(total_penalty, 2), "invoice": penalty_invoice}


@router.post("/customers/{customer_id}/receive-payment")
async def receive_customer_payment(customer_id: str, data: dict, user=Depends(get_current_user)):
    """QuickBooks-style: apply payment across multiple invoices with per-row allocation."""
    check_perm(user, "accounting", "receive_payment")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    allocations = data.get("allocations", [])  # [{invoice_id, amount}]
    total_amount = round(sum(float(a.get("amount", 0)) for a in allocations if float(a.get("amount", 0)) > 0), 2)
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be > 0")

    method = data.get("method", "Cash")
    reference = data.get("reference", "")
    pay_date = data.get("date", now_iso()[:10])
    branch_id = data.get("branch_id", "")
    total_applied, applied_invoices = 0, []

    for alloc in allocations:
        apply = round(float(alloc.get("amount", 0)), 2)
        if apply <= 0:
            continue
        inv = await db.invoices.find_one({"id": alloc["invoice_id"], "customer_id": customer_id}, {"_id": 0})
        if not inv or inv.get("balance", 0) <= 0:
            continue
        apply = min(apply, inv["balance"])
        new_balance = max(0, round(inv["balance"] - apply, 2))
        new_paid = round(inv.get("amount_paid", 0) + apply, 2)
        new_status = "paid" if new_balance <= 0 else "partial"
        payment_record = {
            "id": new_id(), "amount": apply, "date": pay_date, "method": method,
            "reference": reference, "fund_source": "cashier",
            "applied_to_interest": 0, "applied_to_principal": apply,
            "recorded_by": user.get("full_name", user["username"]), "recorded_at": now_iso(),
        }
        await db.invoices.update_one({"id": inv["id"]}, {
            "$set": {"balance": new_balance, "amount_paid": new_paid, "status": new_status},
            "$push": {"payments": payment_record}
        })
        if not branch_id and inv.get("branch_id"):
            branch_id = inv["branch_id"]
        total_applied = round(total_applied + apply, 2)
        applied_invoices.append({"invoice_id": inv["id"], "invoice_number": inv.get("invoice_number"),
                                  "applied": apply, "new_balance": new_balance})

    if total_applied <= 0:
        raise HTTPException(status_code=400, detail="No payment could be applied")

    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": -total_applied}})
    if branch_id:
        await update_cashier_wallet(branch_id, total_applied, f"Payment — {customer.get('name','')} {reference or method}")

    return {"message": "Payment applied", "total_applied": total_applied, "applied_invoices": applied_invoices,
            "deposited_to": "Cashier Drawer"}


@router.get("/customers/{customer_id}/payment-history")
async def get_customer_payment_history(customer_id: str, user=Depends(get_current_user)):
    """Get all payment records for a customer across all invoices."""
    invoices = await db.invoices.find(
        {"customer_id": customer_id},
        {"_id": 0, "invoice_number": 1, "sale_type": 1, "payments": 1}
    ).to_list(500)
    history = []
    for inv in invoices:
        for p in inv.get("payments", []):
            history.append({
                "date": p.get("date", ""), "invoice_number": inv.get("invoice_number", ""),
                "sale_type": inv.get("sale_type", "regular"), "method": p.get("method", ""),
                "reference": p.get("reference", ""), "amount": p.get("amount", 0),
                "recorded_by": p.get("recorded_by", ""), "recorded_at": p.get("recorded_at", ""),
            })
    history.sort(key=lambda x: x.get("recorded_at", ""), reverse=True)
    return history


# ==================== CUSTOMER INTEREST/PENALTY GENERATION ====================
@router.get("/customers/{customer_id}/charges-preview")
async def preview_customer_charges(customer_id: str, as_of_date: Optional[str] = None, user=Depends(get_current_user)):
    """Preview interest for a customer WITHOUT creating invoices. Used for display only."""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    comp_date_str = as_of_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d")
    grace_period = int(customer.get("grace_period", 7))
    default_rate = float(customer.get("interest_rate", 0))

    invoices = await db.invoices.find(
        {"customer_id": customer_id, "balance": {"$gt": 0}, "status": {"$nin": ["voided", "paid"]}},
        {"_id": 0}
    ).to_list(500)

    interest_preview, total_interest, total_principal = [], 0, 0

    for inv in invoices:
        if inv.get("sale_type") in ("interest_charge", "penalty_charge"):
            continue
        rate = float(inv.get("interest_rate") or default_rate)
        if rate <= 0:
            continue
        due_str = inv.get("due_date") or inv.get("order_date") or comp_date_str
        due_date = datetime.strptime(due_str, "%Y-%m-%d")
        grace_end = due_date + timedelta(days=grace_period)
        last_int_str = inv.get("last_interest_date")
        start_date = datetime.strptime(last_int_str, "%Y-%m-%d") if last_int_str else grace_end
        days = max(0, (comp_date - start_date).days)
        principal = max(0, inv.get("balance", 0) - inv.get("interest_accrued", 0) - inv.get("penalties", 0))
        total_principal += principal
        if days > 0 and principal > 0:
            interest = round(principal * (rate / 100 / 30) * days, 2)
            total_interest += interest
            interest_preview.append({
                "invoice_number": inv.get("invoice_number", ""),
                "invoice_id": inv["id"],
                "principal": principal,
                "rate": rate,
                "days_for_interest": days,
                "interest_amount": interest,
            })

    return {
        "customer_id": customer_id,
        "total_principal": total_principal,
        "total_interest": round(total_interest, 2),
        "interest_preview": interest_preview,
    }


# ==================== CUSTOMER STATEMENT OF ACCOUNT ====================
@router.get("/customers/{customer_id}/statement")
async def get_customer_statement(
    customer_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user)
):
    """Full statement of account for a customer: all charges, payments, with running balance."""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    query = {"customer_id": customer_id}
    if date_from:
        query["order_date"] = {"$gte": date_from}
    if date_to:
        query.setdefault("order_date", {})["$lte"] = date_to

    invoices = await db.invoices.find(query, {"_id": 0}).sort("order_date", 1).to_list(1000)

    TYPE_LABELS = {
        "interest_charge": "Interest Charge",
        "penalty_charge": "Penalty Charge",
        "farm_expense": "Farm Expense",
        "cash_advance": "Customer Cash Out",  # Never "Cash Advance" — that's for employees
    }

    transactions = []
    for inv in invoices:
        label = TYPE_LABELS.get(inv.get("sale_type", ""), "Invoice")
        items_preview = ", ".join(
            i.get("product_name", "Service") for i in inv.get("items", [])[:2]
        )
        transactions.append({
            "date": inv.get("order_date", ""),
            "reference": inv.get("invoice_number", ""),
            "description": f"{label}: {items_preview}" if items_preview else label,
            "debit": inv.get("grand_total", 0),
            "credit": 0,
            "type": "charge",
            "invoice_id": inv["id"],
        })
        for p in inv.get("payments", []):
            transactions.append({
                "date": p.get("date", ""),
                "reference": inv.get("invoice_number", ""),
                "description": f"Payment — {p.get('method', 'Cash')}{' Ref:' + p['reference'] if p.get('reference') else ''}",
                "debit": 0,
                "credit": p.get("amount", 0),
                "type": "payment",
            })

    transactions.sort(key=lambda x: (x.get("date", ""), 0 if x["type"] == "charge" else 1))

    running = 0.0
    for t in transactions:
        running = round(running + t["debit"] - t["credit"], 2)
        t["running_balance"] = running

    return {
        "customer": customer,
        "transactions": transactions,
        "closing_balance": running,
        "statement_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "date_from": date_from,
        "date_to": date_to,
    }

