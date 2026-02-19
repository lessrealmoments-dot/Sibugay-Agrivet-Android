from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import Optional, List
import uuid
from datetime import datetime, timezone
import bcrypt
import jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
JWT_SECRET = os.environ.get('JWT_SECRET', 'agripos_default_secret')

app = FastAPI(title="AgriPOS API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== AUTH HELPERS ====================
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

async def log_movement(product_id, branch_id, m_type, qty_change, ref_id, ref_number, price, user_id, user_name, notes=""):
    await db.movements.insert_one({
        "id": new_id(), "product_id": product_id, "branch_id": branch_id,
        "type": m_type, "quantity_change": qty_change,
        "reference_id": ref_id, "reference_number": ref_number,
        "price_at_time": float(price) if price else 0, "notes": notes,
        "user_id": user_id, "user_name": user_name, "created_at": now_iso()
    })

# ==================== AUTH ROUTES ====================
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
        "id": new_id(),
        "username": data["username"],
        "full_name": data.get("full_name", ""),
        "email": data.get("email", ""),
        "password_hash": hash_password(data["password"]),
        "role": role,
        "branch_id": data.get("branch_id"),
        "permissions": data.get("permissions", DEFAULT_PERMISSIONS.get(role, DEFAULT_PERMISSIONS["cashier"])),
        "active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(new_user)
    safe = {k: v for k, v in new_user.items() if k not in ("password_hash", "_id")}
    return safe

@api_router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return {k: v for k, v in user.items() if k != "password_hash"}

@api_router.put("/auth/change-password")
async def change_password(data: dict, user=Depends(get_current_user)):
    if not verify_password(data.get("current_password", ""), user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(data["new_password"])}})
    return {"message": "Password changed"}

# ==================== BRANCH ROUTES ====================
@api_router.get("/branches")
async def list_branches(user=Depends(get_current_user)):
    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)
    return branches

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
    branch = await db.branches.find_one({"id": branch_id}, {"_id": 0})
    return branch

@api_router.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, user=Depends(get_current_user)):
    check_perm(user, "branches", "delete")
    await db.branches.update_one({"id": branch_id}, {"$set": {"active": False}})
    return {"message": "Branch deleted"}

# ==================== PRODUCT ROUTES ====================
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

@api_router.post("/products")
async def create_product(data: dict, user=Depends(get_current_user)):
    check_perm(user, "products", "create")
    existing = await db.products.find_one({"sku": data["sku"], "active": True}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    product = {
        "id": new_id(), "sku": data["sku"], "name": data["name"],
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
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    return product

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
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    return repacks

@api_router.get("/products/categories/list")
async def list_categories(user=Depends(get_current_user)):
    categories = await db.products.distinct("category", {"active": True})
    return categories

# ==================== ENHANCED PRODUCT SEARCH ====================
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

# ==================== INVOICE / SALES ORDER SYSTEM ====================
@api_router.get("/invoices")
async def list_invoices(user=Depends(get_current_user), status: Optional[str] = None,
                        customer_id: Optional[str] = None, branch_id: Optional[str] = None,
                        skip: int = 0, limit: int = 50):
    query = {"status": {"$ne": "voided"}}
    if status: query["status"] = status
    if customer_id: query["customer_id"] = customer_id
    if branch_id: query["branch_id"] = branch_id
    total = await db.invoices.count_documents(query)
    items = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"invoices": items, "total": total}

@api_router.post("/invoices")
async def create_invoice(data: dict, user=Depends(get_current_user)):
    check_perm(user, "pos", "sell")
    # Get prefix settings
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = data.get("prefix", settings.get("value", {}).get("sales_invoice", "SI") if settings else "SI")
    # Auto-generate number
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"
    # Compute due date
    terms_days = int(data.get("terms_days", 0))
    order_date = data.get("order_date", now_iso()[:10])
    if terms_days > 0:
        from datetime import timedelta
        od = datetime.strptime(order_date, "%Y-%m-%d")
        due_date = (od + timedelta(days=terms_days)).strftime("%Y-%m-%d")
    else:
        due_date = order_date
    # Compute line items
    items = []
    subtotal = 0
    for item in data.get("items", []):
        qty = float(item.get("quantity", 0))
        rate = float(item.get("rate", 0))
        disc_type = item.get("discount_type", "amount")
        disc_val = float(item.get("discount_value", 0))
        disc_amt = disc_val if disc_type == "amount" else round(qty * rate * disc_val / 100, 2)
        line_total = round(qty * rate - disc_amt, 2)
        items.append({
            "product_id": item.get("product_id", ""), "product_name": item.get("product_name", ""),
            "description": item.get("description", ""), "quantity": qty, "rate": rate,
            "discount_type": disc_type, "discount_value": disc_val, "discount_amount": disc_amt,
            "total": line_total, "is_repack": item.get("is_repack", False),
        })
        subtotal += line_total
    freight = float(data.get("freight", 0))
    overall_disc = float(data.get("overall_discount", 0))
    grand_total = round(subtotal + freight - overall_disc, 2)
    amount_paid = float(data.get("amount_paid", 0))
    balance = round(grand_total - amount_paid, 2)
    # Get customer interest rate
    customer = await db.customers.find_one({"id": data.get("customer_id")}, {"_id": 0}) if data.get("customer_id") else None
    interest_rate = float(data.get("interest_rate", customer.get("interest_rate", 0) if customer else 0))
    status = "paid" if balance <= 0 else ("partial" if amount_paid > 0 else "open")
    sale_type = data.get("sale_type", "walk_in")
    invoice = {
        "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
        "customer_id": data.get("customer_id"), "customer_name": data.get("customer_name", "Walk-in"),
        "customer_contact": data.get("customer_contact", ""), "customer_phone": data.get("customer_phone", ""),
        "customer_address": data.get("customer_address", ""),
        "terms": data.get("terms", "COD"), "terms_days": terms_days, "customer_po": data.get("customer_po", ""),
        "sales_rep_id": data.get("sales_rep_id"), "sales_rep_name": data.get("sales_rep_name", ""),
        "branch_id": data.get("branch_id", ""),
        "order_date": order_date, "invoice_date": data.get("invoice_date", order_date), "due_date": due_date,
        "items": items, "subtotal": subtotal, "freight": freight, "overall_discount": overall_disc,
        "grand_total": grand_total, "amount_paid": amount_paid, "balance": balance,
        "interest_rate": interest_rate, "interest_accrued": 0, "penalties": 0,
        "last_interest_date": None, "sale_type": sale_type,
        "status": status, "payments": [],
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    # Handle inventory
    branch_id = data.get("branch_id", "")
    if sale_type != "delivery":
        for item in items:
            if item["product_id"]:
                await db.inventory.update_one(
                    {"product_id": item["product_id"], "branch_id": branch_id},
                    {"$inc": {"quantity": -item["quantity"]}, "$set": {"updated_at": now_iso()}},
                    upsert=True
                )
                product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
                if product and product.get("is_repack") and product.get("parent_id"):
                    pd = item["quantity"] / product.get("units_per_parent", 1)
                    await db.inventory.update_one(
                        {"product_id": product["parent_id"], "branch_id": branch_id},
                        {"$inc": {"quantity": -pd}, "$set": {"updated_at": now_iso()}}, upsert=True
                    )
                await log_movement(item["product_id"], branch_id, "sale", -item["quantity"],
                                   invoice["id"], inv_number, item["rate"], user["id"],
                                   user.get("full_name", user["username"]))
    else:
        invoice["status"] = "reserved" if balance > 0 else "paid"
    # Record initial payment if any
    if amount_paid > 0:
        invoice["payments"].append({
            "id": new_id(), "amount": amount_paid, "date": order_date,
            "method": data.get("payment_method", "Cash"), "fund_source": data.get("fund_source", "cashier"),
            "reference": "", "applied_to_interest": 0, "applied_to_principal": amount_paid,
            "recorded_by": user.get("full_name", user["username"]), "recorded_at": now_iso(),
        })
    await db.invoices.insert_one(invoice)
    del invoice["_id"]
    return invoice

@api_router.get("/invoices/{inv_id}")
async def get_invoice(inv_id: str, user=Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    return inv

@api_router.post("/invoices/{inv_id}/compute-interest")
async def compute_interest(inv_id: str, user=Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    if inv["balance"] <= 0 or inv["interest_rate"] <= 0: return {"interest": 0, "message": "No interest applicable"}
    due = datetime.strptime(inv["due_date"], "%Y-%m-%d")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now <= due: return {"interest": 0, "message": "Not yet overdue"}
    last_date = datetime.strptime(inv["last_interest_date"], "%Y-%m-%d") if inv.get("last_interest_date") else due
    days_overdue = (now - last_date).days
    if days_overdue <= 0: return {"interest": 0, "message": "Already computed today"}
    monthly_rate = inv["interest_rate"] / 100
    daily_rate = monthly_rate / 30
    principal_balance = inv["balance"] - inv.get("interest_accrued", 0) - inv.get("penalties", 0)
    new_interest = round(max(0, principal_balance) * daily_rate * days_overdue, 2)
    total_interest = round(inv.get("interest_accrued", 0) + new_interest, 2)
    new_balance = round(inv["balance"] + new_interest, 2)
    await db.invoices.update_one({"id": inv_id}, {"$set": {
        "interest_accrued": total_interest, "balance": new_balance,
        "last_interest_date": now.strftime("%Y-%m-%d"), "status": "overdue"
    }})
    return {"interest_added": new_interest, "total_interest": total_interest, "new_balance": new_balance, "days": days_overdue}

@api_router.post("/invoices/{inv_id}/payment")
async def record_invoice_payment(inv_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    amount = float(data["amount"])
    fund_source = data.get("fund_source", "cashier")
    branch_id = inv.get("branch_id", "")
    # Deduct from fund source
    if fund_source == "safe":
        lots = await db.safe_lots.find({"branch_id": branch_id, "remaining_amount": {"$gt": 0}}, {"_id": 0}).sort("remaining_amount", -1).to_list(100)
        # For receiving payment, we ADD to the fund, not deduct. Skip lot allocation for income.
    # Interest & penalties first, then principal
    interest_owed = inv.get("interest_accrued", 0) + inv.get("penalties", 0)
    applied_interest = min(amount, interest_owed)
    applied_principal = amount - applied_interest
    new_interest = max(0, round(inv.get("interest_accrued", 0) - applied_interest, 2))
    new_balance = round(inv["balance"] - amount, 2)
    new_paid = round(inv["amount_paid"] + amount, 2)
    new_status = "paid" if new_balance <= 0 else "partial"
    payment = {
        "id": new_id(), "amount": amount, "date": data.get("date", now_iso()[:10]),
        "method": data.get("method", "Cash"), "fund_source": fund_source,
        "reference": data.get("reference", ""),
        "applied_to_interest": applied_interest, "applied_to_principal": applied_principal,
        "recorded_by": user.get("full_name", user["username"]), "recorded_at": now_iso(),
    }
    await db.invoices.update_one({"id": inv_id}, {
        "$set": {"balance": max(0, new_balance), "amount_paid": new_paid,
                 "interest_accrued": new_interest, "status": new_status},
        "$push": {"payments": payment}
    })
    # Add to wallet
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": fund_source}, {"_id": 0})
    if wallet:
        if fund_source == "safe":
            await db.safe_lots.insert_one({
                "id": new_id(), "branch_id": branch_id, "wallet_id": wallet["id"],
                "date_received": data.get("date", now_iso()[:10]),
                "original_amount": amount, "remaining_amount": amount,
                "source_reference": f"Payment from {inv.get('customer_name', '')} - {inv['invoice_number']}",
                "created_by": user["id"], "created_at": now_iso()
            })
        else:
            await db.fund_wallets.update_one({"id": wallet["id"]}, {"$inc": {"balance": amount}})
    # Update customer balance
    if inv.get("customer_id"):
        await db.customers.update_one({"id": inv["customer_id"]}, {"$inc": {"balance": -amount}})
    return {"message": "Payment recorded", "new_balance": max(0, new_balance), "status": new_status, "payment": payment}

@api_router.get("/customers/{customer_id}/invoices")
async def get_customer_invoices(customer_id: str, user=Depends(get_current_user)):
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return invoices

# ==================== FUND WALLET SYSTEM ====================
@api_router.get("/fund-wallets")
async def list_fund_wallets(user=Depends(get_current_user), branch_id: Optional[str] = None):
    query = {"active": True}
    if branch_id: query["branch_id"] = branch_id
    wallets = await db.fund_wallets.find(query, {"_id": 0}).to_list(50)
    for w in wallets:
        if w["type"] == "safe":
            lots = await db.safe_lots.find({"wallet_id": w["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}).to_list(500)
            w["balance"] = sum(l["remaining_amount"] for l in lots)
            w["lots"] = lots
    return wallets

@api_router.post("/fund-wallets")
async def create_fund_wallet(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    wallet = {
        "id": new_id(), "branch_id": data["branch_id"], "type": data["type"],
        "name": data["name"], "balance": float(data.get("balance", 0)),
        "bank_name": data.get("bank_name", ""), "account_number": data.get("account_number", ""),
        "active": True, "created_at": now_iso(),
    }
    await db.fund_wallets.insert_one(wallet)
    del wallet["_id"]
    return wallet

@api_router.post("/fund-wallets/{wallet_id}/deposit")
async def deposit_to_wallet(wallet_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    wallet = await db.fund_wallets.find_one({"id": wallet_id}, {"_id": 0})
    if not wallet: raise HTTPException(status_code=404, detail="Wallet not found")
    amount = float(data["amount"])
    if wallet["type"] == "safe":
        await db.safe_lots.insert_one({
            "id": new_id(), "branch_id": wallet["branch_id"], "wallet_id": wallet_id,
            "date_received": data.get("date", now_iso()[:10]),
            "original_amount": amount, "remaining_amount": amount,
            "source_reference": data.get("reference", "Manual deposit"),
            "created_by": user["id"], "created_at": now_iso()
        })
    else:
        await db.fund_wallets.update_one({"id": wallet_id}, {"$inc": {"balance": amount}})
    await db.wallet_movements.insert_one({
        "id": new_id(), "wallet_id": wallet_id, "branch_id": wallet["branch_id"],
        "type": "deposit", "amount": amount, "reference": data.get("reference", ""),
        "user_id": user["id"], "user_name": user.get("full_name", user["username"]),
        "created_at": now_iso()
    })
    return {"message": "Deposited", "amount": amount}

@api_router.post("/fund-wallets/pay")
async def pay_from_wallet(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    wallet_id = data["wallet_id"]
    amount = float(data["amount"])
    wallet = await db.fund_wallets.find_one({"id": wallet_id}, {"_id": 0})
    if not wallet: raise HTTPException(status_code=404, detail="Wallet not found")
    if wallet["type"] == "safe":
        lots = await db.safe_lots.find(
            {"wallet_id": wallet_id, "remaining_amount": {"$gt": 0}}, {"_id": 0}
        ).sort("remaining_amount", -1).to_list(500)
        total_available = sum(l["remaining_amount"] for l in lots)
        if total_available < amount:
            raise HTTPException(status_code=400, detail="Insufficient Safe balance")
        remaining = amount
        usages = []
        for lot in lots:
            if remaining <= 0: break
            take = min(lot["remaining_amount"], remaining)
            await db.safe_lots.update_one({"id": lot["id"]}, {"$inc": {"remaining_amount": -take}})
            usages.append({"lot_id": lot["id"], "lot_date": lot["date_received"], "amount_used": take})
            await db.safe_lot_usages.insert_one({
                "id": new_id(), "lot_id": lot["id"], "payment_id": data.get("reference_id", ""),
                "branch_id": wallet["branch_id"], "amount_used": take,
                "used_by_user_id": user["id"], "used_at": now_iso()
            })
            remaining -= take
        summary = ", ".join([f"{u['lot_date']} lot: ₱{u['amount_used']:.2f}" for u in usages])
    else:
        if wallet["balance"] < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient {wallet['type']} balance")
        await db.fund_wallets.update_one({"id": wallet_id}, {"$inc": {"balance": -amount}})
        summary = f"Deducted ₱{amount:.2f} from {wallet['name']}"
    await db.wallet_movements.insert_one({
        "id": new_id(), "wallet_id": wallet_id, "branch_id": wallet["branch_id"],
        "type": "payment", "amount": -amount, "reference": data.get("reference", ""),
        "description": data.get("description", ""), "user_id": user["id"],
        "user_name": user.get("full_name", user["username"]), "created_at": now_iso()
    })
    return {"message": "Payment processed", "summary": summary}

@api_router.get("/safe-lots")
async def list_safe_lots(user=Depends(get_current_user), branch_id: Optional[str] = None):
    query = {"remaining_amount": {"$gt": 0}}
    if branch_id: query["branch_id"] = branch_id
    lots = await db.safe_lots.find(query, {"_id": 0}).sort("date_received", 1).to_list(500)
    return lots

# ==================== INVOICE SETTINGS ====================
@api_router.get("/settings/invoice-prefixes")
async def get_invoice_prefixes(user=Depends(get_current_user)):
    s = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    if not s:
        defaults = {"sales_invoice": "SI", "delivery": "DR", "transfer": "TR", "purchase_order": "PO"}
        await db.settings.insert_one({"key": "invoice_prefixes", "value": defaults})
        return defaults
    return s.get("value", {})

@api_router.put("/settings/invoice-prefixes")
async def update_invoice_prefixes(data: dict, user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    await db.settings.update_one({"key": "invoice_prefixes"}, {"$set": {"value": data}}, upsert=True)
    return data

@api_router.get("/settings/terms-options")
async def get_terms_options(user=Depends(get_current_user)):
    s = await db.settings.find_one({"key": "terms_options"}, {"_id": 0})
    if not s:
        defaults = [
            {"label": "COD", "days": 0}, {"label": "Net 7", "days": 7},
            {"label": "Net 15", "days": 15}, {"label": "Net 30", "days": 30},
            {"label": "Net 60", "days": 60},
        ]
        await db.settings.insert_one({"key": "terms_options", "value": defaults})
        return defaults
    return s.get("value", [])

# ==================== PRODUCT DETAIL & SUB-ROUTES ====================
@api_router.get("/products/{product_id}/detail")
async def get_product_detail(product_id: str, user=Depends(get_current_user)):
    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    inv_records = await db.inventory.find({"product_id": product_id}, {"_id": 0}).to_list(100)
    on_hand = {}
    total_on_hand = 0
    for inv in inv_records:
        on_hand[inv["branch_id"]] = inv["quantity"]
        total_on_hand += inv["quantity"]
    coming_pipeline = [
        {"$match": {"status": {"$in": ["ordered", "draft"]}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None, "total": {"$sum": "$items.quantity"}}}
    ]
    coming_result = await db.purchase_orders.aggregate(coming_pipeline).to_list(1)
    coming = coming_result[0]["total"] if coming_result else 0
    reserved_pipeline = [
        {"$match": {"status": "reserved"}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None, "total": {"$sum": "$items.quantity"}}}
    ]
    reserved_result = await db.sales.aggregate(reserved_pipeline).to_list(1)
    reserved = reserved_result[0]["total"] if reserved_result else 0
    purchase_movements = await db.movements.find(
        {"product_id": product_id, "type": "purchase", "quantity_change": {"$gt": 0}}, {"_id": 0}
    ).to_list(10000)
    total_pqty = sum(m["quantity_change"] for m in purchase_movements)
    total_pcost = sum(m["quantity_change"] * m.get("price_at_time", 0) for m in purchase_movements)
    moving_avg = round(total_pcost / total_pqty, 2) if total_pqty > 0 else product.get("cost_price", 0)
    last_purchase = await db.movements.find_one(
        {"product_id": product_id, "type": "purchase"}, {"_id": 0}, sort=[("created_at", -1)]
    )
    lp_price = last_purchase.get("price_at_time", 0) if last_purchase else 0
    lp_warning = lp_price < moving_avg if last_purchase and moving_avg > 0 and lp_price > 0 else False
    repacks = await db.products.find({"parent_id": product_id, "active": True}, {"_id": 0}).to_list(100)
    vendors = await db.product_vendors.find({"product_id": product_id}, {"_id": 0}).to_list(50)
    all_branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)
    return {
        "product": product,
        "inventory": {"on_hand": on_hand, "total": total_on_hand, "coming": coming, "reserved": reserved},
        "cost": {"moving_average": moving_avg, "last_purchase": lp_price,
                 "last_purchase_date": last_purchase.get("created_at", "") if last_purchase else "",
                 "last_purchase_warning": lp_warning, "method": product.get("capital_method", "manual")},
        "repacks": repacks, "vendors": vendors, "branches": all_branches,
    }

@api_router.get("/products/{product_id}/movements")
async def get_product_movements(product_id: str, user=Depends(get_current_user), skip: int = 0, limit: int = 50):
    total = await db.movements.count_documents({"product_id": product_id})
    items = await db.movements.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"movements": items, "total": total}

@api_router.get("/products/{product_id}/orders")
async def get_product_orders(product_id: str, user=Depends(get_current_user), skip: int = 0, limit: int = 50):
    sale_pipeline = [
        {"$match": {"status": {"$ne": "voided"}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$project": {"_id": 0, "type": {"$literal": "sale"}, "date": "$created_at",
                       "reference": "$sale_number", "quantity": "$items.quantity",
                       "price": "$items.price", "total": "$items.total",
                       "party": "$customer_name", "status": "$status"}},
        {"$sort": {"date": -1}}, {"$skip": skip}, {"$limit": limit}
    ]
    po_pipeline = [
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$project": {"_id": 0, "type": {"$literal": "purchase"}, "date": "$created_at",
                       "reference": "$po_number", "quantity": "$items.quantity",
                       "price": "$items.unit_price", "total": "$items.total",
                       "party": "$vendor", "status": "$status"}},
        {"$sort": {"date": -1}}, {"$skip": skip}, {"$limit": limit}
    ]
    sales = await db.sales.aggregate(sale_pipeline).to_list(limit)
    purchases = await db.purchase_orders.aggregate(po_pipeline).to_list(limit)
    combined = sorted(sales + purchases, key=lambda x: x.get("date", ""), reverse=True)[:limit]
    return {"orders": combined, "total": len(combined)}

@api_router.get("/products/{product_id}/vendors")
async def get_product_vendors(product_id: str, user=Depends(get_current_user)):
    return await db.product_vendors.find({"product_id": product_id}, {"_id": 0}).to_list(50)

@api_router.post("/products/{product_id}/vendors")
async def add_product_vendor(product_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "products", "edit")
    vendor = {
        "id": new_id(), "product_id": product_id,
        "vendor_name": data["vendor_name"], "vendor_contact": data.get("vendor_contact", ""),
        "last_price": float(data.get("last_price", 0)),
        "last_order_date": data.get("last_order_date", ""),
        "is_preferred": data.get("is_preferred", False), "created_at": now_iso(),
    }
    await db.product_vendors.insert_one(vendor)
    del vendor["_id"]
    return vendor

@api_router.delete("/products/{product_id}/vendors/{vendor_id}")
async def remove_product_vendor(product_id: str, vendor_id: str, user=Depends(get_current_user)):
    check_perm(user, "products", "edit")
    await db.product_vendors.delete_one({"id": vendor_id, "product_id": product_id})
    return {"message": "Vendor removed"}

# ==================== PURCHASE ORDER ROUTES ====================
@api_router.get("/purchase-orders")
async def list_purchase_orders(user=Depends(get_current_user), status: Optional[str] = None, skip: int = 0, limit: int = 50):
    query = {}
    if status:
        query["status"] = status
    total = await db.purchase_orders.count_documents(query)
    items = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"purchase_orders": items, "total": total}

@api_router.post("/purchase-orders")
async def create_purchase_order(data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    items = data.get("items", [])
    subtotal = sum(float(i.get("quantity", 0)) * float(i.get("unit_price", 0)) for i in items)
    po = {
        "id": new_id(),
        "po_number": f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}",
        "vendor": data["vendor"], "branch_id": data.get("branch_id", ""),
        "items": [{"product_id": i["product_id"], "product_name": i.get("product_name", ""),
                    "quantity": float(i["quantity"]), "unit_price": float(i.get("unit_price", 0)),
                    "total": float(i["quantity"]) * float(i.get("unit_price", 0))} for i in items],
        "subtotal": subtotal, "status": data.get("status", "ordered"),
        "expected_date": data.get("expected_date", ""), "received_date": None,
        "notes": data.get("notes", ""),
        "created_by": user["id"], "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.purchase_orders.insert_one(po)
    del po["_id"]
    return po

@api_router.put("/purchase-orders/{po_id}")
async def update_purchase_order(po_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    allowed = ["vendor", "items", "expected_date", "notes", "status", "branch_id"]
    update = {k: v for k, v in data.items() if k in allowed}
    if "items" in update:
        update["subtotal"] = sum(float(i.get("quantity", 0)) * float(i.get("unit_price", 0)) for i in update["items"])
    update["updated_at"] = now_iso()
    await db.purchase_orders.update_one({"id": po_id}, {"$set": update})
    return await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})

@api_router.post("/purchase-orders/{po_id}/receive")
async def receive_purchase_order(po_id: str, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    if po["status"] == "received":
        raise HTTPException(status_code=400, detail="PO already received")
    branch_id = po.get("branch_id", "")
    for item in po.get("items", []):
        pid = item["product_id"]
        qty = float(item["quantity"])
        price = float(item.get("unit_price", 0))
        existing = await db.inventory.find_one({"product_id": pid, "branch_id": branch_id})
        if existing:
            await db.inventory.update_one({"product_id": pid, "branch_id": branch_id},
                                          {"$inc": {"quantity": qty}, "$set": {"updated_at": now_iso()}})
        else:
            await db.inventory.insert_one({"id": new_id(), "product_id": pid, "branch_id": branch_id,
                                           "quantity": qty, "updated_at": now_iso()})
        await log_movement(pid, branch_id, "purchase", qty, po["id"], po["po_number"],
                           price, user["id"], user.get("full_name", user["username"]), f"PO received from {po['vendor']}")
        await db.products.update_one({"id": pid}, {"$set": {"last_vendor": po["vendor"]}})
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "received", "received_date": now_iso()}})
    return {"message": "PO received, inventory updated"}

@api_router.delete("/purchase-orders/{po_id}")
async def cancel_purchase_order(po_id: str, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "cancelled"}})
    return {"message": "PO cancelled"}

# ==================== INVENTORY ROUTES ====================
@api_router.get("/inventory")
async def list_inventory(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    search: Optional[str] = None,
    low_stock: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
):
    pipeline = [
        {"$match": {"active": True}},
        {"$lookup": {"from": "inventory", "localField": "id", "foreignField": "product_id", "as": "stock_records"}},
    ]
    if branch_id:
        pipeline.append({"$addFields": {
            "stock_records": {"$filter": {"input": "$stock_records", "as": "s", "cond": {"$eq": ["$$s.branch_id", branch_id]}}}
        }})
    pipeline.append({"$addFields": {
        "total_stock": {"$sum": "$stock_records.quantity"},
        "branch_stock": {"$arrayToObject": {"$map": {"input": "$stock_records", "as": "s", "in": {"k": "$$s.branch_id", "v": "$$s.quantity"}}}}
    }})
    if search:
        pipeline.insert(1, {"$match": {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}}
        ]}})
    if low_stock:
        pipeline.append({"$match": {"total_stock": {"$lte": 10}}})
    pipeline.append({"$project": {"_id": 0, "stock_records": 0}})
    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db.products.aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0
    pipeline.extend([{"$skip": skip}, {"$limit": limit}])
    items = await db.products.aggregate(pipeline).to_list(limit)
    return {"items": items, "total": total}

@api_router.post("/inventory/adjust")
async def adjust_inventory(data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    quantity = float(data["quantity"])
    reason = data.get("reason", "Manual adjustment")
    existing = await db.inventory.find_one({"product_id": product_id, "branch_id": branch_id}, {"_id": 0})
    if existing:
        new_qty = existing["quantity"] + quantity
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": {"quantity": new_qty, "updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(), "product_id": product_id, "branch_id": branch_id,
            "quantity": quantity, "updated_at": now_iso()
        })
    log = {
        "id": new_id(), "product_id": product_id, "branch_id": branch_id,
        "quantity_change": quantity, "reason": reason, "user_id": user["id"],
        "created_at": now_iso()
    }
    await db.inventory_logs.insert_one(log)
    await log_movement(product_id, branch_id, "adjustment", quantity, log["id"], "ADJ",
                       0, user["id"], user.get("full_name", user["username"]), reason)
    return {"message": "Inventory adjusted", "new_quantity": (existing["quantity"] + quantity) if existing else quantity}

@api_router.post("/inventory/transfer")
async def transfer_inventory(data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "transfer")
    product_id = data["product_id"]
    from_branch = data["from_branch_id"]
    to_branch = data["to_branch_id"]
    quantity = float(data["quantity"])
    source = await db.inventory.find_one({"product_id": product_id, "branch_id": from_branch}, {"_id": 0})
    if not source or source["quantity"] < quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock in source branch")
    await db.inventory.update_one(
        {"product_id": product_id, "branch_id": from_branch},
        {"$inc": {"quantity": -quantity}, "$set": {"updated_at": now_iso()}}
    )
    dest = await db.inventory.find_one({"product_id": product_id, "branch_id": to_branch}, {"_id": 0})
    if dest:
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": to_branch},
            {"$inc": {"quantity": quantity}, "$set": {"updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(), "product_id": product_id, "branch_id": to_branch,
            "quantity": quantity, "updated_at": now_iso()
        })
    log = {
        "id": new_id(), "type": "transfer", "product_id": product_id,
        "from_branch_id": from_branch, "to_branch_id": to_branch,
        "quantity": quantity, "user_id": user["id"], "created_at": now_iso()
    }
    await db.inventory_logs.insert_one(log)
    return {"message": "Transfer complete"}

@api_router.post("/inventory/set")
async def set_inventory(data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    quantity = float(data["quantity"])
    existing = await db.inventory.find_one({"product_id": product_id, "branch_id": branch_id})
    if existing:
        await db.inventory.update_one(
            {"product_id": product_id, "branch_id": branch_id},
            {"$set": {"quantity": quantity, "updated_at": now_iso()}}
        )
    else:
        await db.inventory.insert_one({
            "id": new_id(), "product_id": product_id, "branch_id": branch_id,
            "quantity": quantity, "updated_at": now_iso()
        })
    return {"message": "Inventory set", "quantity": quantity}

# ==================== CUSTOMER ROUTES ====================
@api_router.get("/customers")
async def list_customers(user=Depends(get_current_user), search: Optional[str] = None, skip: int = 0, limit: int = 50):
    query = {"active": True}
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"phone": {"$regex": search, "$options": "i"}}]
    total = await db.customers.count_documents(query)
    customers = await db.customers.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    return {"customers": customers, "total": total}

@api_router.post("/customers")
async def create_customer(data: dict, user=Depends(get_current_user)):
    check_perm(user, "customers", "create")
    customer = {
        "id": new_id(), "name": data["name"], "phone": data.get("phone", ""),
        "email": data.get("email", ""), "address": data.get("address", ""),
        "price_scheme": data.get("price_scheme", "retail"),
        "credit_limit": float(data.get("credit_limit", 0)),
        "balance": 0.0, "active": True, "created_at": now_iso(),
    }
    await db.customers.insert_one(customer)
    del customer["_id"]
    return customer

@api_router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "customers", "edit")
    allowed = ["name", "phone", "email", "address", "price_scheme", "credit_limit"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    await db.customers.update_one({"id": customer_id}, {"$set": update})
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    return customer

@api_router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, user=Depends(get_current_user)):
    check_perm(user, "customers", "delete")
    await db.customers.update_one({"id": customer_id}, {"$set": {"active": False}})
    return {"message": "Customer deleted"}

# ==================== PRICE SCHEME ROUTES ====================
@api_router.get("/price-schemes")
async def list_price_schemes(user=Depends(get_current_user)):
    schemes = await db.price_schemes.find({"active": True}, {"_id": 0}).to_list(50)
    return schemes

@api_router.post("/price-schemes")
async def create_price_scheme(data: dict, user=Depends(get_current_user)):
    check_perm(user, "price_schemes", "create")
    scheme = {
        "id": new_id(), "name": data["name"], "key": data.get("key", data["name"].lower().replace(" ", "_")),
        "description": data.get("description", ""),
        "calculation_method": data.get("calculation_method", "fixed"),
        "calculation_value": float(data.get("calculation_value", 0)),
        "base_scheme": data.get("base_scheme", "cost_price"),
        "active": True, "created_at": now_iso(),
    }
    await db.price_schemes.insert_one(scheme)
    del scheme["_id"]
    return scheme

@api_router.put("/price-schemes/{scheme_id}")
async def update_price_scheme(scheme_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "price_schemes", "edit")
    allowed = ["name", "description", "calculation_method", "calculation_value", "base_scheme"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    await db.price_schemes.update_one({"id": scheme_id}, {"$set": update})
    scheme = await db.price_schemes.find_one({"id": scheme_id}, {"_id": 0})
    return scheme

@api_router.delete("/price-schemes/{scheme_id}")
async def delete_price_scheme(scheme_id: str, user=Depends(get_current_user)):
    check_perm(user, "price_schemes", "delete")
    await db.price_schemes.update_one({"id": scheme_id}, {"$set": {"active": False}})
    return {"message": "Price scheme deleted"}

# ==================== SALES / POS ROUTES ====================
@api_router.post("/sales")
async def create_sale(data: dict, user=Depends(get_current_user)):
    check_perm(user, "pos", "sell")
    branch_id = data["branch_id"]
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="No items in sale")

    sale_items = []
    total = 0.0

    for item in items:
        product = await db.products.find_one({"id": item["product_id"], "active": True}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=400, detail=f"Product not found: {item['product_id']}")
        qty = float(item["quantity"])
        price = float(item.get("price", 0))
        line_total = qty * price

        # Check stock
        inv = await db.inventory.find_one({"product_id": item["product_id"], "branch_id": branch_id}, {"_id": 0})
        current_stock = inv["quantity"] if inv else 0
        if current_stock < qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product['name']}: have {current_stock}, need {qty}")

        # Deduct from product inventory
        await db.inventory.update_one(
            {"product_id": item["product_id"], "branch_id": branch_id},
            {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}}
        )

        # If repack, also deduct from parent
        if product.get("is_repack") and product.get("parent_id"):
            units_per_parent = product.get("units_per_parent", 1)
            parent_deduction = qty / units_per_parent
            parent_inv = await db.inventory.find_one({"product_id": product["parent_id"], "branch_id": branch_id})
            if parent_inv:
                await db.inventory.update_one(
                    {"product_id": product["parent_id"], "branch_id": branch_id},
                    {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}}
                )
            else:
                await db.inventory.insert_one({
                    "id": new_id(), "product_id": product["parent_id"],
                    "branch_id": branch_id, "quantity": -parent_deduction, "updated_at": now_iso()
                })

        sale_items.append({
            "product_id": item["product_id"], "product_name": product["name"],
            "sku": product["sku"], "quantity": qty, "price": price,
            "total": line_total, "is_repack": product.get("is_repack", False),
        })
        total += line_total

    discount = float(data.get("discount", 0))
    sale = {
        "id": new_id(), "sale_number": f"SL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}",
        "branch_id": branch_id, "customer_id": data.get("customer_id"),
        "customer_name": data.get("customer_name", "Walk-in"),
        "items": sale_items, "subtotal": total, "discount": discount,
        "total": total - discount,
        "payment_method": data.get("payment_method", "Cash"),
        "payment_details": data.get("payment_details", {}),
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]),
        "status": "completed", "created_at": now_iso(),
    }

    # Handle credit sales
    if data.get("payment_method") == "Credit" and data.get("customer_id"):
        await db.customers.update_one({"id": data["customer_id"]}, {"$inc": {"balance": sale["total"]}})
        receivable = {
            "id": new_id(), "customer_id": data["customer_id"],
            "customer_name": data.get("customer_name", ""), "sale_id": sale["id"],
            "branch_id": branch_id, "amount": sale["total"], "paid": 0,
            "balance": sale["total"], "due_date": data.get("due_date", ""),
            "status": "pending", "created_at": now_iso(),
        }
        await db.receivables.insert_one(receivable)

    # Check if this is a reserved (delivery) sale
    if data.get("sale_type") == "delivery":
        sale["status"] = "reserved"
        sale["sale_type"] = "delivery"
    else:
        sale["sale_type"] = "walk_in"
        # Log movements for completed walk-in sales
        for si in sale_items:
            await log_movement(si["product_id"], branch_id, "sale", -si["quantity"],
                               sale["id"], sale["sale_number"], si["price"],
                               user["id"], user.get("full_name", user["username"]))

    await db.sales.insert_one(sale)
    del sale["_id"]
    return sale

@api_router.get("/sales")
async def list_sales(
    user=Depends(get_current_user), branch_id: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    skip: int = 0, limit: int = 50
):
    query = {"status": {"$ne": "voided"}}
    if branch_id:
        query["branch_id"] = branch_id
    if date_from:
        query["created_at"] = {"$gte": date_from}
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to
    total = await db.sales.count_documents(query)
    sales = await db.sales.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"sales": sales, "total": total}

@api_router.get("/sales/{sale_id}")
async def get_sale(sale_id: str, user=Depends(get_current_user)):
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale

@api_router.post("/sales/{sale_id}/void")
async def void_sale(sale_id: str, user=Depends(get_current_user)):
    check_perm(user, "pos", "void")
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    # Restore inventory
    for item in sale.get("items", []):
        await db.inventory.update_one(
            {"product_id": item["product_id"], "branch_id": sale["branch_id"]},
            {"$inc": {"quantity": item["quantity"]}, "$set": {"updated_at": now_iso()}}
        )
    await db.sales.update_one({"id": sale_id}, {"$set": {"status": "voided", "voided_at": now_iso(), "voided_by": user["id"]}})
    return {"message": "Sale voided"}

@api_router.post("/sales/{sale_id}/release")
async def release_sale(sale_id: str, user=Depends(get_current_user)):
    """Release a reserved/delivery sale - deducts inventory"""
    check_perm(user, "pos", "sell")
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.get("status") != "reserved":
        raise HTTPException(status_code=400, detail="Sale is not in reserved status")
    branch_id = sale["branch_id"]
    for item in sale.get("items", []):
        qty = float(item["quantity"])
        # Deduct inventory
        await db.inventory.update_one(
            {"product_id": item["product_id"], "branch_id": branch_id},
            {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}}
        )
        # Handle repack parent deduction
        if item.get("is_repack"):
            product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
            if product and product.get("parent_id"):
                parent_deduction = qty / product.get("units_per_parent", 1)
                await db.inventory.update_one(
                    {"product_id": product["parent_id"], "branch_id": branch_id},
                    {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}}
                )
        await log_movement(item["product_id"], branch_id, "sale", -qty,
                           sale["id"], sale.get("sale_number", ""), item.get("price", 0),
                           user["id"], user.get("full_name", user["username"]), "Released delivery")
    await db.sales.update_one({"id": sale_id}, {"$set": {"status": "completed", "released_at": now_iso(), "released_by": user["id"]}})
    return {"message": "Sale released, inventory deducted"}

# ==================== ACCOUNTING ROUTES ====================
@api_router.get("/expenses")
async def list_expenses(user=Depends(get_current_user), branch_id: Optional[str] = None, skip: int = 0, limit: int = 50):
    check_perm(user, "accounting", "view")
    query = {}
    if branch_id:
        query["branch_id"] = branch_id
    total = await db.expenses.count_documents(query)
    expenses = await db.expenses.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"expenses": expenses, "total": total}

@api_router.post("/expenses")
async def create_expense(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    expense = {
        "id": new_id(), "branch_id": data["branch_id"], "category": data.get("category", "General"),
        "description": data.get("description", ""), "amount": float(data["amount"]),
        "date": data.get("date", now_iso()[:10]), "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]), "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)
    del expense["_id"]
    return expense

@api_router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, user=Depends(get_current_user)):
    check_perm(user, "accounting", "delete")
    await db.expenses.delete_one({"id": expense_id})
    return {"message": "Expense deleted"}

@api_router.get("/receivables")
async def list_receivables(user=Depends(get_current_user), status: Optional[str] = None, skip: int = 0, limit: int = 50):
    check_perm(user, "accounting", "view")
    query = {}
    if status:
        query["status"] = status
    total = await db.receivables.count_documents(query)
    items = await db.receivables.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"receivables": items, "total": total}

@api_router.post("/receivables/{rec_id}/payment")
async def record_receivable_payment(rec_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "edit")
    rec = await db.receivables.find_one({"id": rec_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Receivable not found")
    amount = float(data["amount"])
    new_paid = rec["paid"] + amount
    new_balance = rec["amount"] - new_paid
    status = "paid" if new_balance <= 0 else "partial"
    await db.receivables.update_one({"id": rec_id}, {"$set": {"paid": new_paid, "balance": max(0, new_balance), "status": status, "updated_at": now_iso()}})
    if rec.get("customer_id"):
        await db.customers.update_one({"id": rec["customer_id"]}, {"$inc": {"balance": -amount}})
    return {"message": "Payment recorded", "new_balance": max(0, new_balance)}

@api_router.get("/payables")
async def list_payables(user=Depends(get_current_user), status: Optional[str] = None, skip: int = 0, limit: int = 50):
    check_perm(user, "accounting", "view")
    query = {}
    if status:
        query["status"] = status
    total = await db.payables.count_documents(query)
    items = await db.payables.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"payables": items, "total": total}

@api_router.post("/payables")
async def create_payable(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    payable = {
        "id": new_id(), "supplier": data["supplier"], "branch_id": data.get("branch_id", ""),
        "description": data.get("description", ""), "amount": float(data["amount"]),
        "paid": 0, "balance": float(data["amount"]),
        "due_date": data.get("due_date", ""), "status": "pending",
        "created_by": user["id"], "created_at": now_iso(),
    }
    await db.payables.insert_one(payable)
    del payable["_id"]
    return payable

@api_router.post("/payables/{pay_id}/payment")
async def record_payable_payment(pay_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "edit")
    pay = await db.payables.find_one({"id": pay_id}, {"_id": 0})
    if not pay:
        raise HTTPException(status_code=404, detail="Payable not found")
    amount = float(data["amount"])
    new_paid = pay["paid"] + amount
    new_balance = pay["amount"] - new_paid
    status = "paid" if new_balance <= 0 else "partial"
    await db.payables.update_one({"id": pay_id}, {"$set": {"paid": new_paid, "balance": max(0, new_balance), "status": status, "updated_at": now_iso()}})
    return {"message": "Payment recorded", "new_balance": max(0, new_balance)}

# ==================== SYNC ENDPOINTS (Offline POS) ====================
@api_router.get("/sync/pos-data")
async def get_pos_data(user=Depends(get_current_user)):
    """Return all data needed for offline POS in one call"""
    products = await db.products.find({"active": True}, {"_id": 0}).to_list(5000)
    customers = await db.customers.find({"active": True}, {"_id": 0}).to_list(5000)
    schemes = await db.price_schemes.find({"active": True}, {"_id": 0}).to_list(50)
    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)
    return {
        "products": products, "customers": customers,
        "price_schemes": schemes, "branches": branches,
        "timestamp": now_iso()
    }

@api_router.post("/sales/sync")
async def sync_offline_sales(data: dict, user=Depends(get_current_user)):
    """Sync batch of offline sales with duplicate detection"""
    check_perm(user, "pos", "sell")
    results = []
    for sale_data in data.get("sales", []):
        sale_id = sale_data.get("id")
        # Duplicate check
        existing = await db.sales.find_one({"id": sale_id}, {"_id": 0})
        if existing:
            results.append({"id": sale_id, "status": "duplicate", "message": "Already synced"})
            continue
        try:
            sale_doc = {**sale_data, "synced_at": now_iso(), "sync_source": "offline"}
            branch_id = sale_doc.get("branch_id")
            # Process inventory for each item
            for item in sale_doc.get("items", []):
                product_id = item.get("product_id")
                qty = float(item.get("quantity", 0))
                # Deduct from product inventory
                await db.inventory.update_one(
                    {"product_id": product_id, "branch_id": branch_id},
                    {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}},
                    upsert=True
                )
                # Handle repack parent deduction
                if item.get("is_repack"):
                    product = await db.products.find_one({"id": product_id, "is_repack": True}, {"_id": 0})
                    if product and product.get("parent_id"):
                        units_per_parent = product.get("units_per_parent", 1)
                        parent_deduction = qty / units_per_parent
                        await db.inventory.update_one(
                            {"product_id": product["parent_id"], "branch_id": branch_id},
                            {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                            upsert=True
                        )
            # Handle credit sales
            if sale_doc.get("payment_method") == "Credit" and sale_doc.get("customer_id"):
                await db.customers.update_one(
                    {"id": sale_doc["customer_id"]},
                    {"$inc": {"balance": sale_doc.get("total", 0)}}
                )
                receivable = {
                    "id": new_id(), "customer_id": sale_doc["customer_id"],
                    "customer_name": sale_doc.get("customer_name", ""),
                    "sale_id": sale_id, "branch_id": branch_id,
                    "amount": sale_doc.get("total", 0), "paid": 0,
                    "balance": sale_doc.get("total", 0),
                    "status": "pending", "created_at": now_iso(),
                }
                await db.receivables.insert_one(receivable)
            await db.sales.insert_one(sale_doc)
            results.append({"id": sale_id, "status": "synced"})
        except Exception as e:
            logger.error(f"Sync error for sale {sale_id}: {e}")
            results.append({"id": sale_id, "status": "error", "message": str(e)})
    synced = len([r for r in results if r["status"] == "synced"])
    return {"results": results, "synced": synced, "total": len(data.get("sales", []))}

# ==================== DASHBOARD ROUTES ====================
@api_router.get("/dashboard/stats")
async def dashboard_stats(user=Depends(get_current_user), branch_id: Optional[str] = None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sales_query = {"status": "completed"}
    if branch_id:
        sales_query["branch_id"] = branch_id

    # Today's sales
    today_sales = await db.sales.find(
        {**sales_query, "created_at": {"$gte": today}}, {"_id": 0}
    ).to_list(10000)
    today_revenue = sum(s.get("total", 0) for s in today_sales)
    today_count = len(today_sales)

    # Total products & low stock
    total_products = await db.products.count_documents({"active": True})
    low_stock_pipeline = [
        {"$match": {"active": True}},
        {"$lookup": {"from": "inventory", "localField": "id", "foreignField": "product_id", "as": "inv"}},
        {"$addFields": {"total_stock": {"$sum": "$inv.quantity"}}},
        {"$match": {"total_stock": {"$lte": 10}}},
        {"$count": "total"}
    ]
    low_stock_result = await db.products.aggregate(low_stock_pipeline).to_list(1)
    low_stock_count = low_stock_result[0]["total"] if low_stock_result else 0

    # Total customers
    total_customers = await db.customers.count_documents({"active": True})

    # Receivables
    receivables_pipeline = [{"$match": {"status": {"$ne": "paid"}}}, {"$group": {"_id": None, "total": {"$sum": "$balance"}}}]
    rec_result = await db.receivables.aggregate(receivables_pipeline).to_list(1)
    total_receivables = rec_result[0]["total"] if rec_result else 0

    # Expenses today
    today_expenses = await db.expenses.find({"date": today}, {"_id": 0}).to_list(1000)
    today_expense_total = sum(e.get("amount", 0) for e in today_expenses)

    # Recent sales
    recent_sales = await db.sales.find(sales_query, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)

    # Top products (last 30 days)
    top_products_pipeline = [
        {"$match": {"status": "completed"}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "total_qty": {"$sum": "$items.quantity"}, "total_revenue": {"$sum": "$items.total"}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products = await db.sales.aggregate(top_products_pipeline).to_list(5)

    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)

    return {
        "today_revenue": today_revenue, "today_sales_count": today_count,
        "today_expenses": today_expense_total, "total_products": total_products,
        "low_stock_count": low_stock_count, "total_customers": total_customers,
        "total_receivables": total_receivables, "recent_sales": recent_sales,
        "top_products": [{"name": p["_id"], "quantity": p["total_qty"], "revenue": p["total_revenue"]} for p in top_products],
        "branches": branches,
    }

# ==================== USER MANAGEMENT ROUTES ====================
@api_router.get("/users")
async def list_users(user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    users = await db.users.find({"active": True}, {"_id": 0, "password_hash": 0}).to_list(100)
    return users

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    allowed = ["full_name", "email", "role", "branch_id", "active"]
    update = {k: v for k, v in data.items() if k in allowed}
    if "role" in update:
        update["permissions"] = data.get("permissions", DEFAULT_PERMISSIONS.get(update["role"], DEFAULT_PERMISSIONS["cashier"]))
    update["updated_at"] = now_iso()
    await db.users.update_one({"id": user_id}, {"$set": update})
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

@api_router.put("/users/{user_id}/permissions")
async def update_user_permissions(user_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    await db.users.update_one({"id": user_id}, {"$set": {"permissions": data["permissions"], "updated_at": now_iso()}})
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

@api_router.put("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "settings", "manage_users")
    await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(data["new_password"])}})
    return {"message": "Password reset"}

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    admin = await db.users.find_one({"username": "admin"}, {"_id": 0})
    if not admin:
        admin_user = {
            "id": new_id(), "username": "admin", "full_name": "Administrator",
            "email": "admin@agripos.com", "password_hash": hash_password("admin123"),
            "role": "admin", "branch_id": None,
            "permissions": DEFAULT_PERMISSIONS["admin"], "active": True, "created_at": now_iso(),
        }
        await db.users.insert_one(admin_user)
        logger.info("Default admin user created (admin/admin123)")

    branch = await db.branches.find_one({"active": True}, {"_id": 0})
    if not branch:
        main_branch = {"id": new_id(), "name": "Main Branch", "address": "", "phone": "", "active": True, "created_at": now_iso()}
        await db.branches.insert_one(main_branch)
        logger.info("Default branch created")

    schemes = await db.price_schemes.count_documents({})
    if schemes == 0:
        default_schemes = [
            {"id": new_id(), "name": "Retail", "key": "retail", "description": "Standard retail price", "calculation_method": "percent_plus_capital", "calculation_value": 30, "base_scheme": "cost_price", "active": True, "created_at": now_iso()},
            {"id": new_id(), "name": "Wholesale", "key": "wholesale", "description": "Wholesale / bulk price", "calculation_method": "percent_plus_capital", "calculation_value": 15, "base_scheme": "cost_price", "active": True, "created_at": now_iso()},
            {"id": new_id(), "name": "Special", "key": "special", "description": "Special customer price", "calculation_method": "percent_minus_retail", "calculation_value": 10, "base_scheme": "retail", "active": True, "created_at": now_iso()},
            {"id": new_id(), "name": "Government", "key": "government", "description": "Government rate", "calculation_method": "fixed", "calculation_value": 0, "base_scheme": "cost_price", "active": True, "created_at": now_iso()},
        ]
        await db.price_schemes.insert_many(default_schemes)
        logger.info("Default price schemes created")

    # Create indexes
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("sku")
    await db.products.create_index("id", unique=True)
    await db.products.create_index("parent_id")
    await db.inventory.create_index([("product_id", 1), ("branch_id", 1)], unique=True)
    await db.sales.create_index("branch_id")
    await db.sales.create_index("created_at")
    await db.customers.create_index("id", unique=True)
    await db.branches.create_index("id", unique=True)
    logger.info("Database indexes created")

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','), allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
