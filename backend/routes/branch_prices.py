"""
Branch Price Overrides
======================
Stores per-branch price overrides for products.
Falls back to product.prices (global default) when no override exists.

Schema per document:
  { product_id, branch_id, prices: {scheme_key: price}, cost_price, ... }

Fallback chain: branch_prices → product.prices (global)
"""
import math
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from config import db
from utils import get_current_user, check_perm, now_iso, new_id

router = APIRouter(prefix="/branch-prices", tags=["Branch Prices"])


@router.get("")
async def list_branch_prices(
    branch_id: Optional[str] = None,
    product_id: Optional[str] = None,
    user=Depends(get_current_user)
):
    """
    Flexible filter: by branch_id, product_id, or both.
    - branch_id only  → all overrides for a branch (for bulk sync / BranchPricesPage)
    - product_id only → all overrides across branches for one product (ProductDetailPage)
    - both            → single record lookup
    """
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    if product_id:
        query["product_id"] = product_id

    overrides = await db.branch_prices.find(query, {"_id": 0}).to_list(10000)
    return overrides


@router.put("/{product_id}")
async def upsert_branch_price(product_id: str, data: dict, user=Depends(get_current_user)):
    """
    Set or update branch-specific prices for a product.
    Body: { branch_id, prices: {scheme_key: price}, cost_price? }
    """
    check_perm(user, "products", "edit")

    branch_id = data.get("branch_id")
    if not branch_id:
        raise HTTPException(status_code=400, detail="branch_id is required")

    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate prices > 0 (can be 0 to clear, but not negative)
    prices = data.get("prices", {})
    for scheme, price in prices.items():
        if float(price) < 0:
            raise HTTPException(status_code=400, detail=f"Price for {scheme} cannot be negative")

    existing = await db.branch_prices.find_one(
        {"product_id": product_id, "branch_id": branch_id}, {"_id": 0}
    )

    update_doc = {
        "product_id": product_id,
        "branch_id": branch_id,
        "prices": prices,
        "updated_at": now_iso(),
        "updated_by_id": user["id"],
        "updated_by_name": user.get("full_name", user["username"]),
    }
    # Optional branch-specific cost (landed cost may differ by transport)
    if "cost_price" in data and data["cost_price"] is not None:
        update_doc["cost_price"] = float(data["cost_price"])

    if existing:
        await db.branch_prices.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": update_doc}
        )
    else:
        update_doc["id"] = new_id()
        update_doc["created_at"] = now_iso()
        await db.branch_prices.insert_one(update_doc)

    result = await db.branch_prices.find_one(
        {"product_id": product_id, "branch_id": branch_id}, {"_id": 0}
    )
    return result


@router.delete("/{product_id}")
async def delete_branch_price(
    product_id: str,
    branch_id: str,
    user=Depends(get_current_user)
):
    """Remove branch price override — product reverts to global default prices."""
    check_perm(user, "products", "edit")

    result = await db.branch_prices.delete_one(
        {"product_id": product_id, "branch_id": branch_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No override found for this product/branch")

    return {"message": "Override removed — product now uses global default prices"}
