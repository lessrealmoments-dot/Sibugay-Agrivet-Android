"""
AgriPOS API Server - Modular Version
Multi-branch Inventory, POS & Accounting System

This is the refactored, modular version of the AgriPOS backend.
Routes are organized by domain in the routes/ directory.
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

# =============================================================================
# CONFIGURATION
# =============================================================================
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
JWT_SECRET = os.environ.get('JWT_SECRET', 'agripos_default_secret')

app = FastAPI(title="AgriPOS API", description="Multi-branch Inventory, POS & Accounting System")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# AUTH HELPERS & PERMISSIONS
# =============================================================================
DEFAULT_PERMISSIONS = {
    "admin": {
        "branches": {"view": True, "create": True, "edit": True, "delete": True},
        "products": {"view": True, "create": True, "edit": True, "delete": True},
        "inventory": {"view": True, "adjust": True, "transfer": True},
        "pos": {"view": True, "sell": True, "void": True},
        "customers": {"view": True, "create": True, "edit": True, "delete": True},
        "price_schemes": {"view": True, "create": True, "edit": True, "delete": True},
        "accounting": {"view": True, "create": True, "edit": True, "delete": True},
        "reports": {"view": True, "export": True},
        "settings": {"view": True, "manage_users": True, "manage_roles": True},
    },
    "manager": {
        "branches": {"view": True, "create": False, "edit": True, "delete": False},
        "products": {"view": True, "create": True, "edit": True, "delete": False},
        "inventory": {"view": True, "adjust": True, "transfer": True},
        "pos": {"view": True, "sell": True, "void": True},
        "customers": {"view": True, "create": True, "edit": True, "delete": False},
        "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
        "accounting": {"view": True, "create": True, "edit": True, "delete": False},
        "reports": {"view": True, "export": True},
        "settings": {"view": True, "manage_users": False, "manage_roles": False},
    },
    "cashier": {
        "branches": {"view": True, "create": False, "edit": False, "delete": False},
        "products": {"view": True, "create": False, "edit": False, "delete": False},
        "inventory": {"view": True, "adjust": False, "transfer": False},
        "pos": {"view": True, "sell": True, "void": False},
        "customers": {"view": True, "create": True, "edit": False, "delete": False},
        "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
        "accounting": {"view": False, "create": False, "edit": False, "delete": False},
        "reports": {"view": False, "export": False},
        "settings": {"view": False, "manage_users": False, "manage_roles": False},
    },
}

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, role: str) -> str:
    payload = {"user_id": user_id, "role": role, "exp": datetime.now(timezone.utc).timestamp() + 86400}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user or not user.get("active", True):
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def check_perm(user: dict, module: str, action: str):
    if user.get("role") == "admin":
        return
    perms = user.get("permissions", {})
    if not perms.get(module, {}).get(action, False):
        raise HTTPException(status_code=403, detail=f"No permission: {module}.{action}")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def new_id():
    return str(uuid.uuid4())

# =============================================================================
# SHARED SERVICE FUNCTIONS
# =============================================================================
async def log_movement(product_id, branch_id, m_type, qty_change, ref_id, ref_number, price, user_id, user_name, notes=""):
    movement = {
        "id": new_id(), "product_id": product_id, "branch_id": branch_id, "type": m_type,
        "quantity_change": qty_change, "reference_id": ref_id, "reference_number": ref_number,
        "unit_price": price, "user_id": user_id, "user_name": user_name, "notes": notes, "created_at": now_iso(),
    }
    await db.inventory_movements.insert_one(movement)

async def log_sale_items(branch_id, date, items, invoice_number, customer_name, payment_method, cashier_name):
    last = await db.sales_log.find_one({"branch_id": branch_id, "date": date}, sort=[("sequence", -1)])
    seq = (last["sequence"] if last else 0) + 1
    for item in items:
        log_entry = {
            "id": new_id(), "branch_id": branch_id, "date": date, "sequence": seq, "time": now_iso(),
            "product_name": item.get("product_name", ""), "customer_name": customer_name,
            "invoice_number": invoice_number, "quantity": item.get("quantity", 1),
            "unit_price": item.get("price", 0), "discount": item.get("discount", 0),
            "line_total": item.get("total", item.get("quantity", 1) * item.get("price", 0) - item.get("discount", 0)),
            "payment_method": payment_method, "cashier": cashier_name,
        }
        await db.sales_log.insert_one(log_entry)
        seq += 1

async def get_active_date(branch_id):
    last_close = await db.daily_closes.find_one(
        {"branch_id": branch_id}, sort=[("date", -1)], projection={"_id": 0, "date": 1}
    )
    if last_close:
        last_date = datetime.fromisoformat(last_close["date"].replace("Z", "+00:00"))
        return (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

async def update_cashier_wallet(branch_id, amount, reference=""):
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier"}, {"_id": 0})
    if not wallet:
        wallet = {"id": new_id(), "branch_id": branch_id, "type": "cashier", "name": "Cashier Drawer", "balance": 0, "created_at": now_iso()}
        await db.fund_wallets.insert_one(wallet)
    new_balance = (wallet.get("balance", 0) or 0) + amount
    await db.fund_wallets.update_one({"id": wallet["id"]}, {"$set": {"balance": new_balance}})
    movement = {
        "id": new_id(), "wallet_id": wallet["id"], "wallet_name": "Cashier Drawer",
        "branch_id": branch_id, "type": "credit" if amount > 0 else "debit",
        "amount": abs(amount), "balance_after": new_balance, "reference": reference, "created_at": now_iso(),
    }
    await db.wallet_movements.insert_one(movement)
    return new_balance

# =============================================================================
# AUTH ROUTES
# =============================================================================
@api_router.post("/auth/login")
async def login(data: dict):
    user = await db.users.find_one({"username": data.get("username"), "active": True}, {"_id": 0})
    if not user or not verify_password(data.get("password", ""), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["id"], user["role"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}

@api_router.post("/auth/register")
async def register(data: dict, user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    existing = await db.users.find_one({"username": data["username"]}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    role = data.get("role", "cashier")
    new_user = {
        "id": new_id(), "username": data["username"], "full_name": data.get("full_name", ""),
        "email": data.get("email", ""), "password_hash": hash_password(data["password"]),
        "role": role, "branch_id": data.get("branch_id"),
        "permissions": data.get("permissions", DEFAULT_PERMISSIONS.get(role, DEFAULT_PERMISSIONS["cashier"])),
        "active": True, "created_at": now_iso(),
    }
    await db.users.insert_one(new_user)
    return {k: v for k, v in new_user.items() if k not in ("password_hash", "_id")}

@api_router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return {k: v for k, v in user.items() if k != "password_hash"}

@api_router.put("/auth/change-password")
async def change_password(data: dict, user=Depends(get_current_user)):
    if not verify_password(data.get("current_password", ""), user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(data["new_password"])}})
    return {"message": "Password changed"}

# =============================================================================
# BRANCH ROUTES
# =============================================================================
@api_router.get("/branches")
async def list_branches(user=Depends(get_current_user)):
    return await db.branches.find({"active": True}, {"_id": 0}).to_list(100)

@api_router.post("/branches")
async def create_branch(data: dict, user=Depends(get_current_user)):
    check_perm(user, "branches", "create")
    branch = {"id": new_id(), "name": data["name"], "address": data.get("address", ""), "phone": data.get("phone", ""), "active": True, "created_at": now_iso()}
    await db.branches.insert_one(branch)
    del branch["_id"]
    return branch

@api_router.put("/branches/{branch_id}")
async def update_branch(branch_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "branches", "edit")
    update = {k: v for k, v in data.items() if k in ("name", "address", "phone")}
    update["updated_at"] = now_iso()
    await db.branches.update_one({"id": branch_id}, {"$set": update})
    return await db.branches.find_one({"id": branch_id}, {"_id": 0})

@api_router.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, user=Depends(get_current_user)):
    check_perm(user, "branches", "delete")
    await db.branches.update_one({"id": branch_id}, {"$set": {"active": False}})
    return {"message": "Branch deleted"}

# =============================================================================
# PRODUCT ROUTES
# =============================================================================
@api_router.get("/products")
async def list_products(
    user=Depends(get_current_user),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_repack: Optional[bool] = None,
    parent_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    query = {"active": True}
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"sku": {"$regex": search, "$options": "i"}}]
    if category:
        query["category"] = category
    if is_repack is not None:
        query["is_repack"] = is_repack
    if parent_id:
        query["parent_id"] = parent_id
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    return {"products": products, "total": total, "skip": skip, "limit": limit}

@api_router.post("/products")
async def create_product(data: dict, user=Depends(get_current_user)):
    check_perm(user, "products", "create")
    sku = data.get("sku", "").strip()
    if sku:
        existing = await db.products.find_one({"sku": sku, "active": True}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")
    else:
        sku = f"P-{new_id()[:8].upper()}"
    product = {
        "id": new_id(), "sku": sku, "name": data["name"],
        "category": data.get("category", "General"), "description": data.get("description", ""),
        "unit": data.get("unit", "Piece"), "cost_price": float(data.get("cost_price", 0)),
        "prices": data.get("prices", {}), "parent_id": None, "is_repack": False,
        "units_per_parent": None, "repack_unit": None, "barcode": data.get("barcode", ""),
        "product_type": data.get("product_type", "stockable"),
        "capital_method": data.get("capital_method", "manual"),
        "reorder_point": float(data.get("reorder_point", 0)),
        "reorder_quantity": float(data.get("reorder_quantity", 0)),
        "unit_of_measurement": data.get("unit_of_measurement", data.get("unit", "Piece")),
        "last_vendor": data.get("last_vendor", ""),
        "active": True, "created_at": now_iso(),
    }
    await db.products.insert_one(product)
    del product["_id"]
    return product

@api_router.put("/products/{product_id}")
async def update_product(product_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "products", "edit")
    allowed = ["name", "category", "description", "unit", "cost_price", "prices", "barcode",
               "units_per_parent", "repack_unit", "product_type", "capital_method",
               "reorder_point", "reorder_quantity", "unit_of_measurement", "last_vendor"]
    update = {k: v for k, v in data.items() if k in allowed}
    if "cost_price" in update:
        update["cost_price"] = float(update["cost_price"])
    update["updated_at"] = now_iso()
    await db.products.update_one({"id": product_id}, {"$set": update})
    return await db.products.find_one({"id": product_id}, {"_id": 0})

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, user=Depends(get_current_user)):
    check_perm(user, "products", "delete")
    await db.products.update_one({"id": product_id}, {"$set": {"active": False}})
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(1000)
    for r in repacks:
        await db.products.update_one({"id": r["id"]}, {"$set": {"active": False}})
    return {"message": "Product and repacks deleted"}

@api_router.post("/products/{product_id}/generate-repack")
async def generate_repack(product_id: str, data: dict, user=Depends(get_current_user)):
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
        "id": new_id(), "sku": repack_sku, "name": repack_name,
        "category": parent["category"], "description": f"Repack from {parent['name']} ({parent['unit']})",
        "unit": data.get("unit", "Piece"),
        "cost_price": float(data.get("cost_price", 0)) if float(data.get("cost_price", 0)) > 0 else round(auto_cost, 2),
        "prices": data.get("prices", {}), "parent_id": product_id, "is_repack": True,
        "units_per_parent": units, "add_on_cost": add_on_cost,
        "repack_unit": data.get("unit", "Piece"), "barcode": data.get("barcode", ""),
        "product_type": "stockable", "capital_method": "manual",
        "reorder_point": 0, "reorder_quantity": 0,
        "unit_of_measurement": data.get("unit", "Piece"), "last_vendor": "",
        "active": True, "created_at": now_iso(),
    }
    await db.products.insert_one(repack)
    del repack["_id"]
    return repack

@api_router.get("/products/{product_id}/repacks")
async def get_repacks(product_id: str, user=Depends(get_current_user)):
    return await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(100)

@api_router.put("/products/{product_id}/update-price")
async def update_product_price(product_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "products", "edit")
    scheme = data.get("scheme")
    new_price = float(data.get("price", 0))
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if new_price < product.get("cost_price", 0) and new_price > 0:
        raise HTTPException(status_code=400, detail=f"Price ₱{new_price:.2f} is below capital ₱{product['cost_price']:.2f}")
    prices = product.get("prices", {})
    prices[scheme] = new_price
    await db.products.update_one({"id": product_id}, {"$set": {"prices": prices, "updated_at": now_iso()}})
    return {"message": f"{scheme} price updated to ₱{new_price:.2f}", "prices": prices}

@api_router.get("/products/categories/list")
async def list_categories(user=Depends(get_current_user)):
    return await db.products.distinct("category", {"active": True})

@api_router.get("/products/search-detail")
async def search_products_detail(q: str = "", branch_id: Optional[str] = None, user=Depends(get_current_user)):
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
        inv = await db.inventory.find_one({"product_id": p["id"], "branch_id": branch_id}, {"_id": 0}) if branch_id else None
        available = inv["quantity"] if inv else 0
        coming_r = await db.purchase_orders.aggregate([
            {"$match": {"status": {"$in": ["ordered", "draft"]}}}, {"$unwind": "$items"},
            {"$match": {"items.product_id": p["id"]}}, {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
        ]).to_list(1)
        reserved_r = await db.sales.aggregate([
            {"$match": {"status": "reserved"}}, {"$unwind": "$items"},
            {"$match": {"items.product_id": p["id"]}}, {"$group": {"_id": None, "t": {"$sum": "$items.quantity"}}}
        ]).to_list(1)
        result = {**p, "available": available, "reserved": reserved_r[0]["t"] if reserved_r else 0,
                  "coming": coming_r[0]["t"] if coming_r else 0}
        if p.get("is_repack") and p.get("parent_id"):
            parent = await db.products.find_one({"id": p["parent_id"]}, {"_id": 0})
            pinv = await db.inventory.find_one({"product_id": p["parent_id"], "branch_id": branch_id}, {"_id": 0}) if branch_id else None
            result["parent_name"] = parent["name"] if parent else ""
            result["parent_stock"] = pinv["quantity"] if pinv else 0
            result["parent_unit"] = parent["unit"] if parent else ""
        results.append(result)
    return results
