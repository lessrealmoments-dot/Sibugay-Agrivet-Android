"""
Count Sheets routes: Inventory verification and adjustment workflow.

Features:
- Snapshot system inventory at a point in time
- Track actual counts vs system counts
- Calculate variances and losses
- Apply adjustments with full audit trail
- Only parent products (repacks excluded)
- One active count sheet per branch at a time
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from config import db
from utils import (
    get_current_user, check_perm, now_iso, new_id,
    log_movement, get_branch_filter, apply_branch_filter
)

router = APIRouter(prefix="/count-sheets", tags=["Count Sheets"])

# Capital price source options
CAPITAL_PRICE_SOURCES = [
    {"key": "manual", "label": "Manual Cost Price", "description": "Uses the cost_price field from product"},
    {"key": "last_purchase", "label": "Last Purchase Price", "description": "Uses the most recent PO price"},
    {"key": "moving_average", "label": "Moving Average", "description": "Weighted average of all purchases"},
]


async def generate_count_sheet_number(branch_id: str) -> str:
    """Generate sequential count sheet number: CS-YYYY-NNNN"""
    year = datetime.now(timezone.utc).year
    prefix = f"CS-{year}-"
    
    # Find the highest number for this year
    last = await db.count_sheets.find_one(
        {"count_sheet_number": {"$regex": f"^{prefix}"}},
        {"count_sheet_number": 1},
        sort=[("count_sheet_number", -1)]
    )
    
    if last:
        try:
            last_num = int(last["count_sheet_number"].split("-")[-1])
            next_num = last_num + 1
        except:
            next_num = 1
    else:
        next_num = 1
    
    return f"{prefix}{str(next_num).zfill(4)}"


async def get_product_capital_price(product: dict, source: str, branch_id: str) -> float:
    """Get capital price based on selected source."""
    if source == "manual":
        return float(product.get("cost_price", 0))
    
    elif source == "last_purchase":
        # Find most recent PO with this product
        po = await db.purchase_orders.find_one(
            {
                "items.product_id": product["id"],
                "status": {"$in": ["received", "partial"]}
            },
            {"items": 1},
            sort=[("created_at", -1)]
        )
        if po:
            for item in po.get("items", []):
                if item.get("product_id") == product["id"]:
                    return float(item.get("cost", item.get("unit_cost", product.get("cost_price", 0))))
        return float(product.get("cost_price", 0))
    
    elif source == "moving_average":
        # Calculate weighted average from all POs
        pipeline = [
            {"$match": {"items.product_id": product["id"], "status": {"$in": ["received", "partial"]}}},
            {"$unwind": "$items"},
            {"$match": {"items.product_id": product["id"]}},
            {"$group": {
                "_id": None,
                "total_cost": {"$sum": {"$multiply": ["$items.quantity", "$items.cost"]}},
                "total_qty": {"$sum": "$items.quantity"}
            }}
        ]
        result = await db.purchase_orders.aggregate(pipeline).to_list(1)
        if result and result[0]["total_qty"] > 0:
            return round(result[0]["total_cost"] / result[0]["total_qty"], 2)
        return float(product.get("cost_price", 0))
    
    return float(product.get("cost_price", 0))


@router.get("/capital-sources")
async def get_capital_price_sources(user=Depends(get_current_user)):
    """Get available capital price source options."""
    return CAPITAL_PRICE_SOURCES


@router.get("")
async def list_count_sheets(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
):
    """List count sheets with optional filters."""
    check_perm(user, "count_sheets", "view")
    
    query = {}
    branch_filter = await get_branch_filter(user, branch_id)
    query = apply_branch_filter(query, branch_filter)
    
    if status:
        query["status"] = status
    
    total = await db.count_sheets.count_documents(query)
    sheets = await db.count_sheets.find(query, {"_id": 0, "items": 0}).sort(
        [("created_at", -1)]
    ).skip(skip).limit(limit).to_list(limit)
    
    # Add branch names
    for sheet in sheets:
        branch = await db.branches.find_one({"id": sheet.get("branch_id")}, {"_id": 0, "name": 1})
        sheet["branch_name"] = branch["name"] if branch else ""
    
    return {"count_sheets": sheets, "total": total}


@router.get("/{sheet_id}")
async def get_count_sheet(sheet_id: str, user=Depends(get_current_user)):
    """Get count sheet details with all items."""
    check_perm(user, "count_sheets", "view")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    # Add branch name
    branch = await db.branches.find_one({"id": sheet.get("branch_id")}, {"_id": 0, "name": 1})
    sheet["branch_name"] = branch["name"] if branch else ""
    
    return sheet


@router.post("")
async def create_count_sheet(data: dict, user=Depends(get_current_user)):
    """Create a new count sheet in draft status."""
    check_perm(user, "count_sheets", "create")
    
    branch_id = data["branch_id"]
    
    # Check for existing in-progress count sheet for this branch
    existing = await db.count_sheets.find_one({
        "branch_id": branch_id,
        "status": {"$in": ["draft", "in_progress"]}
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An active count sheet ({existing['count_sheet_number']}) already exists for this branch. Please complete or cancel it first."
        )
    
    count_sheet_number = await generate_count_sheet_number(branch_id)
    
    sheet = {
        "id": new_id(),
        "count_sheet_number": count_sheet_number,
        "branch_id": branch_id,
        "status": "draft",
        "capital_price_source": data.get("capital_price_source", "manual"),
        "filter_category": data.get("filter_category"),  # null = all categories
        "created_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "completed_by": None,
        "completed_by_name": None,
        "items": [],
        "summary": None,
        "adjustment_applied": False,
        "adjustment_applied_at": None,
        "adjustment_reference": None,
        "notes": data.get("notes", "")
    }
    
    await db.count_sheets.insert_one(sheet)
    del sheet["_id"]
    
    return sheet


@router.post("/{sheet_id}/snapshot")
async def take_snapshot(sheet_id: str, user=Depends(get_current_user)):
    """Take inventory snapshot and move to in_progress status."""
    check_perm(user, "count_sheets", "create")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    if sheet["status"] != "draft":
        raise HTTPException(status_code=400, detail="Can only snapshot a draft count sheet")
    
    branch_id = sheet["branch_id"]
    category_filter = sheet.get("filter_category")
    capital_source = sheet.get("capital_price_source", "manual")
    
    # Get all parent products (non-repacks), sorted by category then name
    product_query = {"active": True, "is_repack": {"$ne": True}}
    if category_filter:
        product_query["category"] = category_filter
    
    products = await db.products.find(product_query, {"_id": 0}).sort([
        ("category", 1),
        ("name", 1)
    ]).to_list(5000)
    
    # Build snapshot items
    items = []
    for product in products:
        # Get current inventory for this branch
        inv = await db.inventory.find_one(
            {"product_id": product["id"], "branch_id": branch_id},
            {"_id": 0}
        )
        system_qty = inv["quantity"] if inv else 0
        
        # Get capital price based on source
        capital_price = await get_product_capital_price(product, capital_source, branch_id)
        
        # Get retail price (first price scheme or manual)
        retail_price = float(product.get("prices", {}).get("retail", product.get("cost_price", 0) * 1.3))
        
        items.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "sku": product.get("sku", ""),
            "category": product.get("category", "General"),
            "unit": product.get("unit", "Piece"),
            "system_quantity": round(system_qty, 2),
            "actual_quantity": None,
            "variance": None,
            "capital_price": round(capital_price, 2),
            "retail_price": round(retail_price, 2),
            "loss_capital": None,
            "loss_retail": None,
            "notes": "",
            "counted": False
        })
    
    # Update count sheet
    await db.count_sheets.update_one(
        {"id": sheet_id},
        {"$set": {
            "status": "in_progress",
            "started_at": now_iso(),
            "items": items
        }}
    )
    
    updated = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    return updated


@router.put("/{sheet_id}/items")
async def update_counts(sheet_id: str, data: dict, user=Depends(get_current_user)):
    """Update actual counts for items."""
    check_perm(user, "count_sheets", "count")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    if sheet["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Can only update counts for in-progress count sheets")
    
    updates = data.get("items", [])  # [{product_id, actual_quantity, notes?}]
    
    items = sheet["items"]
    for update in updates:
        product_id = update.get("product_id")
        actual_qty = update.get("actual_quantity")
        notes = update.get("notes", "")
        
        for item in items:
            if item["product_id"] == product_id:
                if actual_qty is not None:
                    actual_qty = float(actual_qty)
                    item["actual_quantity"] = actual_qty
                    item["counted"] = True
                    item["variance"] = round(actual_qty - item["system_quantity"], 2)
                    
                    # Calculate losses (negative variance = loss, positive = gain)
                    if item["variance"] != 0:
                        item["loss_capital"] = round(item["variance"] * item["capital_price"], 2)
                        item["loss_retail"] = round(item["variance"] * item["retail_price"], 2)
                    else:
                        item["loss_capital"] = 0
                        item["loss_retail"] = 0
                
                if notes:
                    item["notes"] = notes
                break
    
    await db.count_sheets.update_one(
        {"id": sheet_id},
        {"$set": {"items": items}}
    )
    
    return {"message": "Counts updated", "updated": len(updates)}


@router.post("/{sheet_id}/complete")
async def complete_count_sheet(sheet_id: str, user=Depends(get_current_user)):
    """Complete/finalize the count sheet."""
    check_perm(user, "count_sheets", "complete")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    if sheet["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Can only complete an in-progress count sheet")
    
    # Check all items are counted (STRICT mode)
    items = sheet["items"]
    uncounted = [i for i in items if not i.get("counted", False)]
    
    if uncounted:
        uncounted_names = [i["product_name"] for i in uncounted[:5]]
        remaining = len(uncounted) - 5
        msg = f"All items must be counted. Uncounted: {', '.join(uncounted_names)}"
        if remaining > 0:
            msg += f" and {remaining} more"
        raise HTTPException(status_code=400, detail=msg)
    
    # Calculate summary
    total_loss_capital = sum(i["loss_capital"] for i in items if i.get("loss_capital", 0) < 0)
    total_loss_retail = sum(i["loss_retail"] for i in items if i.get("loss_retail", 0) < 0)
    total_gain_capital = sum(i["loss_capital"] for i in items if i.get("loss_capital", 0) > 0)
    total_gain_retail = sum(i["loss_retail"] for i in items if i.get("loss_retail", 0) > 0)
    
    summary = {
        "total_items": len(items),
        "items_counted": len([i for i in items if i.get("counted")]),
        "items_with_variance": len([i for i in items if i.get("variance", 0) != 0]),
        "items_with_shortage": len([i for i in items if (i.get("variance") or 0) < 0]),
        "items_with_surplus": len([i for i in items if (i.get("variance") or 0) > 0]),
        "total_loss_capital": round(total_loss_capital, 2),
        "total_loss_retail": round(total_loss_retail, 2),
        "total_gain_capital": round(total_gain_capital, 2),
        "total_gain_retail": round(total_gain_retail, 2),
        "net_variance_capital": round(total_loss_capital + total_gain_capital, 2),
        "net_variance_retail": round(total_loss_retail + total_gain_retail, 2)
    }
    
    await db.count_sheets.update_one(
        {"id": sheet_id},
        {"$set": {
            "status": "completed",
            "completed_at": now_iso(),
            "completed_by": user["id"],
            "completed_by_name": user.get("full_name", user["username"]),
            "summary": summary
        }}
    )
    
    updated = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    return updated


@router.post("/{sheet_id}/cancel")
async def cancel_count_sheet(sheet_id: str, data: dict, user=Depends(get_current_user)):
    """Cancel the count sheet."""
    check_perm(user, "count_sheets", "cancel")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    if sheet["status"] not in ["draft", "in_progress"]:
        raise HTTPException(status_code=400, detail="Can only cancel draft or in-progress count sheets")
    
    reason = data.get("reason", "")
    
    await db.count_sheets.update_one(
        {"id": sheet_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now_iso(),
            "cancelled_by": user["id"],
            "cancelled_by_name": user.get("full_name", user["username"]),
            "cancellation_reason": reason
        }}
    )
    
    return {"message": "Count sheet cancelled"}


@router.post("/{sheet_id}/adjust")
async def apply_adjustments(sheet_id: str, data: dict, user=Depends(get_current_user)):
    """Apply inventory adjustments based on count sheet variances."""
    check_perm(user, "count_sheets", "adjust")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    if sheet["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only adjust from a completed count sheet")
    
    if sheet.get("adjustment_applied"):
        raise HTTPException(status_code=400, detail="Adjustments have already been applied for this count sheet")
    
    branch_id = sheet["branch_id"]
    items = sheet["items"]
    adjustments = []
    
    for item in items:
        variance = item.get("variance", 0)
        if variance == 0:
            continue
        
        product_id = item["product_id"]
        
        # Get current inventory
        inv = await db.inventory.find_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"_id": 0}
        )
        current_qty = inv["quantity"] if inv else 0
        new_qty = item["actual_quantity"]
        
        # Update inventory
        if inv:
            await db.inventory.update_one(
                {"product_id": product_id, "branch_id": branch_id},
                {"$set": {"quantity": new_qty, "updated_at": now_iso()}}
            )
        else:
            await db.inventory.insert_one({
                "id": new_id(),
                "product_id": product_id,
                "branch_id": branch_id,
                "quantity": new_qty,
                "updated_at": now_iso()
            })
        
        # Log the movement
        await log_movement(
            product_id, branch_id, "count_adjustment", variance,
            sheet_id, sheet["count_sheet_number"], 0, user["id"],
            user.get("full_name", user["username"]),
            f"Count sheet adjustment: {item['system_quantity']} → {item['actual_quantity']}"
        )
        
        adjustments.append({
            "product_id": product_id,
            "product_name": item["product_name"],
            "sku": item["sku"],
            "system_before": item["system_quantity"],
            "actual_counted": item["actual_quantity"],
            "adjustment": variance,
            "capital_value": item.get("loss_capital", 0),
            "retail_value": item.get("loss_retail", 0)
        })
    
    # Create adjustment record for audit
    adjustment_record = {
        "id": new_id(),
        "count_sheet_id": sheet_id,
        "count_sheet_number": sheet["count_sheet_number"],
        "branch_id": branch_id,
        "adjustments": adjustments,
        "total_adjustments": len(adjustments),
        "total_capital_impact": sheet["summary"]["net_variance_capital"],
        "total_retail_impact": sheet["summary"]["net_variance_retail"],
        "applied_by": user["id"],
        "applied_by_name": user.get("full_name", user["username"]),
        "applied_at": now_iso(),
        "notes": data.get("notes", "")
    }
    
    await db.inventory_adjustments.insert_one(adjustment_record)
    
    # Update count sheet
    await db.count_sheets.update_one(
        {"id": sheet_id},
        {"$set": {
            "adjustment_applied": True,
            "adjustment_applied_at": now_iso(),
            "adjustment_reference": adjustment_record["id"]
        }}
    )
    
    return {
        "message": "Adjustments applied successfully",
        "adjustments_made": len(adjustments),
        "adjustment_id": adjustment_record["id"]
    }


@router.get("/{sheet_id}/print")
async def get_printable_sheet(sheet_id: str, user=Depends(get_current_user)):
    """Get count sheet formatted for printing."""
    check_perm(user, "count_sheets", "view")
    
    sheet = await db.count_sheets.find_one({"id": sheet_id}, {"_id": 0})
    if not sheet:
        raise HTTPException(status_code=404, detail="Count sheet not found")
    
    # Add branch name
    branch = await db.branches.find_one({"id": sheet.get("branch_id")}, {"_id": 0, "name": 1})
    sheet["branch_name"] = branch["name"] if branch else ""
    
    # Group items by category for printing
    categories = {}
    for item in sheet.get("items", []):
        cat = item.get("category", "General")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    
    # Sort categories alphabetically, items within each category alphabetically
    sorted_categories = {}
    for cat in sorted(categories.keys()):
        sorted_categories[cat] = sorted(categories[cat], key=lambda x: x.get("product_name", ""))
    
    sheet["items_by_category"] = sorted_categories
    
    return sheet


@router.get("/categories/list")
async def get_product_categories(user=Depends(get_current_user)):
    """Get list of all product categories for filtering."""
    categories = await db.products.distinct("category", {"active": True, "is_repack": {"$ne": True}})
    return sorted([c for c in categories if c])
