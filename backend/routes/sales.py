"""
Unified Sales endpoint: handles cash, partial, and credit sales.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id,
    log_movement, log_sale_items, get_active_date, update_cashier_wallet,
    get_branch_cost,
)

router = APIRouter(tags=["Sales"])


@router.post("/unified-sale")
async def create_unified_sale(data: dict, user=Depends(get_current_user)):
    """
    Unified sales endpoint that handles all sale types:
    - Cash sales (immediate payment)
    - Partial payment (creates invoice with balance)
    - Credit sales (creates invoice, full balance to AR)
    
    Always creates an invoice record for proper tracking.
    """
    check_perm(user, "pos", "sell")
    
    branch_id = data.get("branch_id")
    if not branch_id:
        raise HTTPException(status_code=400, detail="Branch ID required")
    
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="No items in sale")
    
    customer_id = data.get("customer_id")
    customer_name = data.get("customer_name", "Walk-in")
    payment_type = data.get("payment_type", "cash")  # cash, partial, credit
    
    # Credit limit check for credit/partial sales
    if payment_type in ["partial", "credit"] and customer_id:
        customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
        if customer:
            current_balance = customer.get("balance", 0)
            credit_limit = customer.get("credit_limit", 0)
            balance_due = float(data.get("balance", 0))
            
            # Only block if credit limit is set and exceeded (unless manager approved)
            if credit_limit > 0 and not data.get("approved_by"):
                new_total = current_balance + balance_due
                if new_total > credit_limit:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Credit limit exceeded. Limit: ₱{credit_limit:.2f}, Current: ₱{current_balance:.2f}, This sale: ₱{balance_due:.2f}"
                    )
    
    # Get prefix settings
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = data.get("prefix", settings.get("value", {}).get("sales_invoice", "SI") if settings else "SI")
    
    # Generate invoice number
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"
    
    # Process items and compute totals
    sale_items = []
    subtotal = 0
    
    for item in items:
        product = await db.products.find_one({"id": item["product_id"], "active": True}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=400, detail=f"Product not found: {item['product_id']}")
        
        qty = float(item.get("quantity", 0))
        rate = float(item.get("rate", item.get("price", 0)))
        
        # Check capital rule using branch-specific cost (falls back to global cost)
        branch_cost = await get_branch_cost(product, branch_id)
        if rate > 0 and rate < branch_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell '{product['name']}' at ₱{rate:.2f} — below capital ₱{branch_cost:.2f}"
            )
        
        disc_type = item.get("discount_type", "amount")
        disc_val = float(item.get("discount_value", 0))
        disc_amt = disc_val if disc_type == "amount" else round(qty * rate * disc_val / 100, 2)
        line_total = round(qty * rate - disc_amt, 2)
        
        # Check and deduct inventory
        if product.get("is_repack") and product.get("parent_id"):
            # Repack: deduct from parent
            units_per_parent = product.get("units_per_parent", 1)
            parent_deduction = qty / units_per_parent
            parent_inv = await db.inventory.find_one(
                {"product_id": product["parent_id"], "branch_id": branch_id}, {"_id": 0}
            )
            parent_stock = parent_inv["quantity"] if parent_inv else 0
            available = parent_stock * units_per_parent
            
            if available < qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product['name']}: have {available:.0f}, need {qty:.0f}"
                )
            
            await db.inventory.update_one(
                {"product_id": product["parent_id"], "branch_id": branch_id},
                {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                upsert=True
            )
            await log_movement(
                product["parent_id"], branch_id, "sale", -parent_deduction, "", inv_number,
                rate * units_per_parent, user["id"], user.get("full_name", user["username"]),
                f"Sold as repack: {product['name']} x {qty}"
            )
        else:
            # Regular product
            inv = await db.inventory.find_one(
                {"product_id": item["product_id"], "branch_id": branch_id}, {"_id": 0}
            )
            current_stock = inv["quantity"] if inv else 0
            
            if current_stock < qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product['name']}: have {current_stock:.0f}, need {qty:.0f}"
                )
            
            await db.inventory.update_one(
                {"product_id": item["product_id"], "branch_id": branch_id},
                {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}},
                upsert=True
            )
            await log_movement(
                item["product_id"], branch_id, "sale", -qty, "", inv_number,
                rate, user["id"], user.get("full_name", user["username"])
            )
        
        sale_items.append({
            "product_id": item["product_id"],
            "product_name": product["name"],
            "sku": product.get("sku", ""),
            "description": item.get("description", ""),
            "quantity": qty,
            "rate": rate,
            "discount_type": disc_type,
            "discount_value": disc_val,
            "discount_amount": disc_amt,
            "total": line_total,
            "is_repack": product.get("is_repack", False),
            "cost_price": product.get("cost_price", 0),
        })
        subtotal += line_total
    
    # Calculate totals
    freight = float(data.get("freight", 0))
    overall_disc = float(data.get("overall_discount", 0))
    grand_total = round(subtotal + freight - overall_disc, 2)
    amount_paid = float(data.get("amount_paid", 0))
    balance = round(grand_total - amount_paid, 2)
    
    # Determine status
    if balance <= 0:
        status = "paid"
    elif amount_paid > 0:
        status = "partial"
    else:
        status = "open"
    
    # Get customer interest rate
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0}) if customer_id else None
    interest_rate = float(data.get("interest_rate", customer.get("interest_rate", 0) if customer else 0))
    
    # Compute due date
    terms_days = int(data.get("terms_days", 0))
    order_date = data.get("order_date", now_iso()[:10])
    if terms_days > 0:
        od = datetime.strptime(order_date, "%Y-%m-%d")
        due_date = (od + timedelta(days=terms_days)).strftime("%Y-%m-%d")
    else:
        due_date = order_date
    
    # Create invoice record
    invoice = {
        "id": data.get("id", new_id()),
        "invoice_number": inv_number,
        "prefix": prefix,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_contact": data.get("customer_contact", ""),
        "customer_phone": data.get("customer_phone", ""),
        "customer_address": data.get("customer_address", ""),
        "terms": data.get("terms", "COD"),
        "terms_days": terms_days,
        "customer_po": data.get("customer_po", ""),
        "sales_rep_id": data.get("sales_rep_id"),
        "sales_rep_name": data.get("sales_rep_name", ""),
        "branch_id": branch_id,
        "order_date": order_date,
        "invoice_date": data.get("invoice_date", order_date),
        "due_date": due_date,
        "items": sale_items,
        "subtotal": subtotal,
        "freight": freight,
        "overall_discount": overall_disc,
        "grand_total": grand_total,
        "amount_paid": amount_paid,
        "balance": max(0, balance),
        "interest_rate": interest_rate,
        "interest_accrued": 0,
        "penalties": 0,
        "last_interest_date": None,
        "sale_type": data.get("sale_type", "walk_in"),
        "payment_type": payment_type,
        "status": status,
        "payments": [],
        "approved_by": data.get("approved_by"),
        "mode": data.get("mode", "quick"),
        "cashier_id": user["id"],
        "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    # Record initial payment if any
    if amount_paid > 0:
        invoice["payments"].append({
            "id": new_id(),
            "amount": amount_paid,
            "date": order_date,
            "method": data.get("payment_method", "Cash"),
            "fund_source": data.get("fund_source", "cashier"),
            "reference": "",
            "applied_to_interest": 0,
            "applied_to_principal": amount_paid,
            "recorded_by": user.get("full_name", user["username"]),
            "recorded_at": now_iso(),
        })
        # Update cashier wallet
        await update_cashier_wallet(branch_id, amount_paid, f"Sale payment {inv_number}")
    
    await db.invoices.insert_one(invoice)
    del invoice["_id"]
    
    # Update customer balance for credit portion
    if customer_id and balance > 0:
        await db.customers.update_one(
            {"id": customer_id},
            {"$inc": {"balance": balance}}
        )
    
    # Log to sequential sales log
    active_date = await get_active_date(branch_id)
    for item in sale_items:
        prod = await db.products.find_one({"id": item["product_id"]}, {"_id": 0, "category": 1})
        item["category"] = prod.get("category", "General") if prod else "General"
    
    await log_sale_items(
        branch_id, active_date, sale_items, inv_number,
        customer_name, data.get("payment_method", "cash" if payment_type == "cash" else "credit"),
        user.get("full_name", user["username"])
    )
    
    return invoice
