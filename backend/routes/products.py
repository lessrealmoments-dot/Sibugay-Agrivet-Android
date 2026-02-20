"""
Product management routes: CRUD, repacks, pricing, search.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("")
async def list_products(
    user=Depends(get_current_user),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_repack: Optional[bool] = None,
    parent_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List products with optional filters."""
    query = {"active": True}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category
    if is_repack is not None:
        query["is_repack"] = is_repack
    if parent_id:
        query["parent_id"] = parent_id
    
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    return {"products": products, "total": total, "skip": skip, "limit": limit}


@router.post("")
async def create_product(data: dict, user=Depends(get_current_user)):
    """Create a new product."""
    check_perm(user, "products", "create")
    
    sku = data.get("sku", "").strip()
    if sku:
        existing = await db.products.find_one({"sku": sku, "active": True}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")
    else:
        sku = f"P-{new_id()[:8].upper()}"
    
    product = {
        "id": new_id(),
        "sku": sku,
        "name": data["name"],
        "category": data.get("category", "General"),
        "description": data.get("description", ""),
        "unit": data.get("unit", "Piece"),
        "cost_price": float(data.get("cost_price", 0)),
        "prices": data.get("prices", {}),
        "parent_id": None,
        "is_repack": False,
        "units_per_parent": None,
        "repack_unit": None,
        "barcode": data.get("barcode", ""),
        "product_type": data.get("product_type", "stockable"),
        "capital_method": data.get("capital_method", "manual"),
        "reorder_point": float(data.get("reorder_point", 0)),
        "reorder_quantity": float(data.get("reorder_quantity", 0)),
        "unit_of_measurement": data.get("unit_of_measurement", data.get("unit", "Piece")),
        "last_vendor": data.get("last_vendor", ""),
        "active": True,
        "created_at": now_iso(),
    }
    await db.products.insert_one(product)
    del product["_id"]
    return product


@router.get("/search-detail")
async def search_products_detail(q: str = "", branch_id: Optional[str] = None, user=Depends(get_current_user)):
    """Enhanced product search with stock information."""
    if not q or len(q) < 1:
        return []
    
    query = {"active": True, "$or": [
        {"name": {"$regex": q, "$options": "i"}},
        {"sku": {"$regex": q, "$options": "i"}},
        {"barcode": {"$regex": q, "$options": "i"}},
    ]}
    products = await db.products.find(query, {"_id": 0}).limit(10).to_list(10)
    results = []
    
    for p in products:
        # For repacks: calculate available from parent stock
        if p.get("is_repack") and p.get("parent_id"):
            parent = await db.products.find_one({"id": p["parent_id"]}, {"_id": 0})
            pinv = await db.inventory.find_one(
                {"product_id": p["parent_id"], "branch_id": branch_id}, {"_id": 0}
            ) if branch_id else None
            parent_stock = pinv["quantity"] if pinv else 0
            units_per_parent = p.get("units_per_parent", 1)
            available = parent_stock * units_per_parent
            result = {
                **p,
                "available": available,
                "reserved": 0,
                "coming": 0,
                "parent_name": parent["name"] if parent else "",
                "parent_stock": parent_stock,
                "parent_unit": parent["unit"] if parent else "",
                "derived_from_parent": True,
            }
        else:
            # Regular product: use its own inventory
            inv = await db.inventory.find_one(
                {"product_id": p["id"], "branch_id": branch_id}, {"_id": 0}
            ) if branch_id else None
            available = inv["quantity"] if inv else 0
            
            coming_r = await db.purchase_orders.aggregate([
                {"$match": {"status": {"$in": ["ordered", "draft"]}}},
                {"$unwind": "$items"},
                {"$match": {"items.product_id": p["id"]}},
                {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
            ]).to_list(1)
            
            reserved_r = await db.sales.aggregate([
                {"$match": {"status": "reserved"}},
                {"$unwind": "$items"},
                {"$match": {"items.product_id": p["id"]}},
                {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
            ]).to_list(1)
            
            result = {
                **p,
                "available": available,
                "reserved": reserved_r[0]["t"] if reserved_r else 0,
                "coming": coming_r[0]["t"] if coming_r else 0
            }
        results.append(result)
    
    return results


@router.get("/categories")
async def list_categories(user=Depends(get_current_user)):
    """Get all product categories."""
    categories = await db.products.distinct("category", {"active": True})
    return categories


@router.get("/{product_id}")
async def get_product(product_id: str, user=Depends(get_current_user)):
    """Get a single product by ID."""
    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/detail")
async def get_product_detail(product_id: str, user=Depends(get_current_user)):
    """Get comprehensive product details including repacks, inventory, and vendors."""
    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get repacks
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    
    # Get inventory across all branches
    inv_records = await db.inventory.find({"product_id": product_id}, {"_id": 0}).to_list(100)
    
    # Build on_hand map by branch
    on_hand = {}
    total_qty = 0
    for inv in inv_records:
        branch_id = inv.get("branch_id")
        qty = inv.get("quantity", 0)
        on_hand[branch_id] = qty
        total_qty += qty
    
    # Calculate coming (from purchase orders)
    coming_r = await db.purchase_orders.aggregate([
        {"$match": {"status": {"$in": ["ordered", "draft"]}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
    ]).to_list(1)
    coming = coming_r[0]["t"] if coming_r else 0
    
    # Calculate reserved (from pending sales)
    reserved_r = await db.sales.aggregate([
        {"$match": {"status": "reserved"}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
    ]).to_list(1)
    reserved = reserved_r[0]["t"] if reserved_r else 0
    
    # Get vendors
    vendors = await db.product_vendors.find({"product_id": product_id}, {"_id": 0}).to_list(50)
    
    # Get parent product if this is a repack
    parent = None
    if product.get("parent_id"):
        parent = await db.products.find_one({"id": product["parent_id"]}, {"_id": 0})
    
    # Get cost info
    cost = {
        "cost_price": product.get("cost_price", 0),
        "capital_method": product.get("capital_method", "manual"),
    }
    
    return {
        "product": product,
        "repacks": repacks,
        "inventory": {
            "on_hand": on_hand,
            "total": total_qty,
            "coming": coming,
            "reserved": reserved
        },
        "cost": cost,
        "vendors": vendors,
        "parent": parent
    }


@router.put("/{product_id}")
async def update_product(product_id: str, data: dict, user=Depends(get_current_user)):
    """Update product details."""
    check_perm(user, "products", "edit")
    
    allowed = ["name", "category", "description", "unit", "cost_price", "prices", "barcode",
               "units_per_parent", "repack_unit", "product_type", "capital_method",
               "reorder_point", "reorder_quantity", "unit_of_measurement", "last_vendor"]
    update = {k: v for k, v in data.items() if k in allowed}
    
    if "cost_price" in update:
        update["cost_price"] = float(update["cost_price"])
    update["updated_at"] = now_iso()
    
    await db.products.update_one({"id": product_id}, {"$set": update})
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: str, user=Depends(get_current_user)):
    """Soft delete a product and its repacks."""
    check_perm(user, "products", "delete")
    
    await db.products.update_one({"id": product_id}, {"$set": {"active": False}})
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(1000)
    for r in repacks:
        await db.products.update_one({"id": r["id"]}, {"$set": {"active": False}})
    
    return {"message": "Product and repacks deleted"}


@router.post("/{product_id}/generate-repack")
async def generate_repack(product_id: str, data: dict, user=Depends(get_current_user)):
    """Generate a repack product from a parent product."""
    check_perm(user, "products", "create")
    
    parent = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent product not found")
    if parent.get("is_repack"):
        raise HTTPException(status_code=400, detail="Cannot create repack from a repack")
    
    repack_sku = f"R-{parent['sku']}"
    existing = await db.products.find_one({"sku": repack_sku, "active": True}, {"_id": 0})
    if existing:
        count = await db.products.count_documents({"parent_id": product_id, "active": True})
        repack_sku = f"R-{parent['sku']}-{count + 1}"
    
    repack_name = data.get("name", f"R {parent['name']}")
    units = int(data.get("units_per_parent", 1))
    add_on_cost = float(data.get("add_on_cost", 0))
    auto_cost = (parent.get("cost_price", 0) / units) + add_on_cost if units > 0 else 0
    
    repack = {
        "id": new_id(),
        "sku": repack_sku,
        "name": repack_name,
        "category": parent["category"],
        "description": f"Repack from {parent['name']} ({parent['unit']})",
        "unit": data.get("unit", "Piece"),
        "cost_price": float(data.get("cost_price", 0)) if float(data.get("cost_price", 0)) > 0 else round(auto_cost, 2),
        "prices": data.get("prices", {}),
        "parent_id": product_id,
        "is_repack": True,
        "units_per_parent": units,
        "add_on_cost": add_on_cost,
        "repack_unit": data.get("unit", "Piece"),
        "barcode": data.get("barcode", ""),
        "product_type": "stockable",
        "capital_method": "manual",
        "reorder_point": 0,
        "reorder_quantity": 0,
        "unit_of_measurement": data.get("unit", "Piece"),
        "last_vendor": "",
        "active": True,
        "created_at": now_iso(),
    }
    await db.products.insert_one(repack)
    del repack["_id"]
    return repack


@router.get("/{product_id}/repacks")
async def get_repacks(product_id: str, user=Depends(get_current_user)):
    """Get all repacks for a product."""
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    return repacks


@router.get("/{product_id}/movements")
async def get_product_movements(product_id: str, limit: int = 50, user=Depends(get_current_user)):
    """Get stock movements for a product."""
    movements = await db.movements.find(
        {"product_id": product_id}, 
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"movements": movements}


@router.get("/{product_id}/orders")
async def get_product_orders(product_id: str, limit: int = 50, user=Depends(get_current_user)):
    """Get purchase orders containing this product."""
    # Find POs that have this product in their items
    pipeline = [
        {"$match": {"items.product_id": product_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0}}
    ]
    orders = await db.purchase_orders.aggregate(pipeline).to_list(limit)
    return {"orders": orders}


@router.post("/{product_id}/vendors")
async def add_product_vendor(product_id: str, data: dict, user=Depends(get_current_user)):
    """Add a vendor for a product."""
    check_perm(user, "products", "edit")
    
    vendor = {
        "id": new_id(),
        "product_id": product_id,
        "vendor_name": data.get("vendor_name", ""),
        "vendor_contact": data.get("vendor_contact", ""),
        "last_price": float(data.get("last_price", 0)),
        "is_preferred": data.get("is_preferred", False),
        "created_at": now_iso()
    }
    await db.product_vendors.insert_one(vendor)
    del vendor["_id"]
    return vendor


@router.put("/{product_id}/update-price")
async def update_product_price(product_id: str, data: dict, user=Depends(get_current_user)):
    """Update a specific price scheme for a product."""
    check_perm(user, "products", "edit")
    
    scheme = data.get("scheme")
    new_price = float(data.get("price", 0))
    
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Hard rule: cannot set price below cost
    if new_price < product.get("cost_price", 0) and new_price > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Price ₱{new_price:.2f} is below capital ₱{product['cost_price']:.2f}"
        )
    
    prices = product.get("prices", {})
    prices[scheme] = new_price
    await db.products.update_one({"id": product_id}, {"$set": {"prices": prices, "updated_at": now_iso()}})
    
    return {"message": f"{scheme} price updated to ₱{new_price:.2f}", "prices": prices}
