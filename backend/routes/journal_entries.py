"""
Journal Entries — Standard double-entry adjustment system.
Allows post-close corrections without altering original transactions.
Manager PIN required for authorization.

Entry types:
  - sale_adjustment: Correct a sale that was missed or entered wrong
  - expense_adjustment: Record a missed expense or correct an amount
  - inventory_adjustment: Write off, damage, or correct stock levels
  - price_correction: Fix a pricing error on a past transaction
  - fund_correction: Adjust fund balances (cashier/safe discrepancy)
  - general: Any other adjustment with memo

Each entry has debit/credit lines that MUST balance (total debits = total credits).
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/journal-entries", tags=["Journal Entries"])

ENTRY_TYPES = [
    "sale_adjustment", "expense_adjustment", "inventory_adjustment",
    "price_correction", "fund_correction", "incident_adjustment", "ap_payment", "general"
]

ENTRY_TYPE_LABELS = {
    "sale_adjustment": "Sale Adjustment",
    "expense_adjustment": "Expense Adjustment",
    "inventory_adjustment": "Inventory Adjustment",
    "price_correction": "Price Correction",
    "fund_correction": "Fund Correction",
    "incident_adjustment": "Incident Resolution Adjustment",
    "ap_payment": "Accounts Payable Payment",
    "general": "General Journal Entry",
}

# Standard chart of accounts for a retail POS
ACCOUNTS = [
    {"code": "1000", "name": "Cash - Cashier Drawer", "type": "asset"},
    {"code": "1010", "name": "Cash - Safe/Vault", "type": "asset"},
    {"code": "1020", "name": "Digital Wallet (GCash/Maya)", "type": "asset"},
    {"code": "1030", "name": "Cash - Bank Account", "type": "asset"},
    {"code": "1100", "name": "Accounts Receivable", "type": "asset"},
    {"code": "1110", "name": "Driver/Courier Receivable", "type": "asset"},
    {"code": "1120", "name": "Insurance Receivable", "type": "asset"},
    {"code": "1200", "name": "Inventory", "type": "asset"},
    {"code": "2000", "name": "Accounts Payable", "type": "liability"},
    {"code": "2100", "name": "Customer Deposits", "type": "liability"},
    {"code": "3000", "name": "Owner's Equity / Capital", "type": "equity"},
    {"code": "4000", "name": "Sales Revenue", "type": "revenue"},
    {"code": "4100", "name": "Interest Income", "type": "revenue"},
    {"code": "4200", "name": "Other Income", "type": "revenue"},
    {"code": "5000", "name": "Cost of Goods Sold", "type": "expense"},
    {"code": "5100", "name": "Operating Expenses", "type": "expense"},
    {"code": "5200", "name": "Salaries & Wages", "type": "expense"},
    {"code": "5300", "name": "Utilities", "type": "expense"},
    {"code": "5400", "name": "Transportation", "type": "expense"},
    {"code": "5500", "name": "Inventory Loss / Write-off", "type": "expense"},
    {"code": "5600", "name": "Returns & Refunds", "type": "expense"},
    {"code": "5900", "name": "Miscellaneous Expense", "type": "expense"},
]


@router.get("/accounts")
async def list_accounts(user=Depends(get_current_user)):
    """Return the chart of accounts for journal entry line items."""
    return {"accounts": ACCOUNTS}


@router.get("")
async def list_journal_entries(
    branch_id: Optional[str] = None,
    entry_type: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_id: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    user=Depends(get_current_user),
):
    """List journal entries with filters."""
    query = {}
    bid = branch_id or user.get("branch_id", "")
    if bid:
        query["branch_id"] = bid
    if entry_type:
        query["entry_type"] = entry_type
    if status:
        query["status"] = status
    if date_from or date_to:
        date_q = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to
        query["effective_date"] = date_q
    if product_id:
        query["lines.product_id"] = product_id

    total = await db.journal_entries.count_documents(query)
    entries = await db.journal_entries.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"entries": entries, "total": total}


@router.get("/{entry_id}")
async def get_journal_entry(entry_id: str, user=Depends(get_current_user)):
    entry = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Journal entry not found")
    return entry


@router.post("")
async def create_journal_entry(data: dict, user=Depends(get_current_user)):
    """
    Create a new journal entry. Requires manager PIN.
    Body: {
      entry_type: str,
      effective_date: str (YYYY-MM-DD, the date the adjustment applies to),
      memo: str (explanation of why this entry is needed),
      reference_number: str (optional, link to original transaction),
      reference_type: str (optional: invoice, expense, purchase_order, etc.),
      product_id: str (optional, for inventory adjustments),
      product_name: str (optional),
      lines: [{ account_code, account_name, debit, credit, memo }],
      pin: str (manager PIN for authorization)
    }
    """
    check_perm(user, "accounting", "create")

    # Validate PIN
    pin = str(data.get("pin", ""))
    if not pin:
        raise HTTPException(400, "Manager PIN required to create journal entries")

    from routes.verify import verify_pin_for_action
    verifier = await verify_pin_for_action(pin, "transaction_verify")
    if not verifier:
        raise HTTPException(400, "Invalid PIN")

    entry_type = data.get("entry_type", "general")
    if entry_type not in ENTRY_TYPES:
        raise HTTPException(400, f"Invalid entry type. Must be one of: {', '.join(ENTRY_TYPES)}")

    lines = data.get("lines", [])
    if not lines or len(lines) < 2:
        raise HTTPException(400, "Journal entry must have at least 2 lines (debit and credit)")

    # Validate balanced entry
    total_debit = round(sum(float(l.get("debit", 0)) for l in lines), 2)
    total_credit = round(sum(float(l.get("credit", 0)) for l in lines), 2)
    if total_debit != total_credit:
        raise HTTPException(400, f"Entry is not balanced. Debits ({total_debit}) must equal credits ({total_credit})")
    if total_debit == 0:
        raise HTTPException(400, "Entry amount cannot be zero")

    effective_date = data.get("effective_date")
    if not effective_date:
        raise HTTPException(400, "Effective date is required")

    memo = data.get("memo", "").strip()
    if not memo:
        raise HTTPException(400, "Memo/explanation is required for audit trail")

    branch_id = data.get("branch_id", user.get("branch_id", ""))

    # Generate JE number
    from utils.numbering import generate_next_number
    je_number = await generate_next_number("JE", branch_id)

    entry = {
        "id": new_id(),
        "je_number": je_number,
        "entry_type": entry_type,
        "entry_type_label": ENTRY_TYPE_LABELS.get(entry_type, entry_type),
        "branch_id": branch_id,
        "effective_date": effective_date,
        "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "memo": memo,
        "reference_number": data.get("reference_number", ""),
        "reference_type": data.get("reference_type", ""),
        "product_id": data.get("product_id", ""),
        "product_name": data.get("product_name", ""),
        "lines": [
            {
                "account_code": l.get("account_code", ""),
                "account_name": l.get("account_name", ""),
                "debit": round(float(l.get("debit", 0)), 2),
                "credit": round(float(l.get("credit", 0)), 2),
                "memo": l.get("memo", ""),
            }
            for l in lines
        ],
        "total_amount": total_debit,
        "status": "posted",
        "authorized_by_id": verifier["verifier_id"],
        "authorized_by_name": verifier["verifier_name"],
        "authorized_method": verifier["method"],
        "created_by_id": user["id"],
        "created_by_name": user.get("full_name", user.get("username", "")),
        "created_at": now_iso(),
        "voided": False,
        "void_reason": "",
        "voided_at": "",
        "voided_by": "",
    }

    await db.journal_entries.insert_one(entry)
    del entry["_id"]
    return entry


@router.post("/{entry_id}/void")
async def void_journal_entry(entry_id: str, data: dict, user=Depends(get_current_user)):
    """Void a journal entry. Requires PIN."""
    check_perm(user, "accounting", "create")

    pin = str(data.get("pin", ""))
    reason = data.get("reason", "").strip()
    if not pin or not reason:
        raise HTTPException(400, "PIN and reason required to void")

    from routes.verify import verify_pin_for_action
    verifier = await verify_pin_for_action(pin, "transaction_verify")
    if not verifier:
        raise HTTPException(400, "Invalid PIN")

    entry = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Journal entry not found")
    if entry.get("voided"):
        raise HTTPException(400, "Already voided")

    await db.journal_entries.update_one({"id": entry_id}, {"$set": {
        "voided": True,
        "status": "voided",
        "void_reason": reason,
        "voided_at": now_iso(),
        "voided_by": verifier["verifier_name"],
    }})

    return {"message": "Journal entry voided", "je_number": entry.get("je_number")}


@router.get("/by-product/{product_id}")
async def get_journal_entries_for_product(
    product_id: str,
    branch_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Get all journal entries related to a specific product — used by Smart Count Sheets."""
    query = {"product_id": product_id, "voided": {"$ne": True}}
    if branch_id:
        query["branch_id"] = branch_id
    entries = await db.journal_entries.find(query, {"_id": 0}).sort("effective_date", -1).to_list(50)
    return {"entries": entries, "total": len(entries)}


@router.get("/summary/period")
async def journal_entry_summary(
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Summary of journal entries for a period — totals by type."""
    query = {"voided": {"$ne": True}}
    bid = branch_id or user.get("branch_id", "")
    if bid:
        query["branch_id"] = bid
    if date_from or date_to:
        date_q = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to
        query["effective_date"] = date_q

    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$entry_type",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$total_amount"},
        }},
        {"$sort": {"total_amount": -1}},
    ]
    results = await db.journal_entries.aggregate(pipeline).to_list(20)

    total_entries = sum(r["count"] for r in results)
    total_amount = round(sum(r["total_amount"] for r in results), 2)

    return {
        "by_type": [
            {
                "entry_type": r["_id"],
                "label": ENTRY_TYPE_LABELS.get(r["_id"], r["_id"]),
                "count": r["count"],
                "total_amount": round(r["total_amount"], 2),
            }
            for r in results
        ],
        "total_entries": total_entries,
        "total_amount": total_amount,
    }
