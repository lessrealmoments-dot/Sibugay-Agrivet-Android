"""
================================================================================
AgriPOS API Server
================================================================================
Multi-branch Inventory, POS & Accounting System for Agricultural Retail

ROUTE SECTIONS (search by section name):
- AUTH HELPERS & ROUTES      (Line ~50)   - Login, register, permissions
- BRANCH ROUTES              (Line ~210)  - Branch CRUD
- PRODUCT ROUTES             (Line ~240)  - Products, repacks, pricing
- PRODUCT SEARCH             (Line ~380)  - Enhanced search with stock info
- INVOICE / SALES ORDER      (Line ~420)  - Sales orders, invoices
- CUSTOMER PAYMENTS          (Line ~630)  - Receive payments, interest
- FUND WALLET SYSTEM         (Line ~840)  - Cashier, Safe, Bank wallets
- INVOICE SETTINGS           (Line ~950)  - Prefixes, terms
- PRODUCT DETAIL             (Line ~1000) - Full product info, vendors
- PURCHASE ORDER ROUTES      (Line ~1080) - PO CRUD, receiving, payments
- INVENTORY ROUTES           (Line ~1240) - Stock levels, adjustments
- CUSTOMER ROUTES            (Line ~1360) - Customer CRUD
- PRICE SCHEME ROUTES        (Line ~1400) - Price tier management
- SALES / POS ROUTES         (Line ~1440) - POS sales, void, release
- ACCOUNTING ROUTES          (Line ~1620) - Expenses, receivables, payables
- SYNC ENDPOINTS             (Line ~1720) - Offline POS sync
- DASHBOARD ROUTES           (Line ~1810) - Stats, KPIs
- USER MANAGEMENT            (Line ~1880) - User CRUD, permissions
- DAILY OPERATIONS           (Line ~1920) - Daily log, close accounts
- EMPLOYEES                  (Line ~2100) - Employee management, advances
- STARTUP                    (Line ~2200) - DB seeding, indexes

Author: AgriPOS Team
Version: 2.0 (Feb 2026)
================================================================================
"""

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
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

# =============================================================================
# CONFIGURATION & DATABASE
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
# =============================================================================
# PERMISSION SYSTEM - Inflow Cloud Style
# =============================================================================
# Permission structure: { module: { action: true/false } }
# Modules: dashboard, branches, products, inventory, sales, purchase_orders,
#          suppliers, customers, accounting, reports, settings
# Actions vary by module but typically include: view, create, edit, delete
# Special permissions: view_cost, sell_below_cost, adjust_inventory, void_invoices, etc.

PERMISSION_MODULES = {
    "dashboard": {
        "label": "Dashboard",
        "actions": {
            "view": "View Dashboard",
        }
    },
    "branches": {
        "label": "Branches",
        "actions": {
            "view": "View Branches",
            "create": "Create Branch",
            "edit": "Edit Branch",
            "delete": "Delete Branch",
        }
    },
    "products": {
        "label": "Products",
        "actions": {
            "view": "View Products",
            "create": "Create Product",
            "edit": "Edit Product",
            "delete": "Delete Product",
            "view_cost": "View Cost Price",
        }
    },
    "inventory": {
        "label": "Inventory",
        "actions": {
            "view": "View Inventory",
            "adjust": "Adjust Stock",
            "transfer": "Transfer Stock",
        }
    },
    "sales": {
        "label": "Sales / POS",
        "actions": {
            "view": "View Sales",
            "create": "Create Sale",
            "edit": "Edit Invoice",
            "void": "Void Invoice",
            "sell_below_cost": "Sell Below Cost",
            "give_discount": "Apply Discount",
        }
    },
    "purchase_orders": {
        "label": "Purchase Orders",
        "actions": {
            "view": "View POs",
            "create": "Create PO",
            "edit": "Edit PO",
            "receive": "Receive Stock",
            "delete": "Delete PO",
        }
    },
    "suppliers": {
        "label": "Suppliers",
        "actions": {
            "view": "View Suppliers",
            "create": "Create Supplier",
            "edit": "Edit Supplier",
            "delete": "Delete Supplier",
        }
    },
    "customers": {
        "label": "Customers",
        "actions": {
            "view": "View Customers",
            "create": "Create Customer",
            "edit": "Edit Customer",
            "delete": "Delete Customer",
            "view_balance": "View Balance",
            "manage_credit": "Manage Credit Limit",
        }
    },
    "accounting": {
        "label": "Accounting",
        "actions": {
            "view": "View Accounting",
            "receive_payment": "Receive Payments",
            "create_expense": "Create Expense",
            "edit_expense": "Edit Expense",
            "generate_interest": "Generate Interest",
            "generate_penalty": "Generate Penalty",
            "manage_funds": "Manage Funds",
        }
    },
    "price_schemes": {
        "label": "Price Schemes",
        "actions": {
            "view": "View Schemes",
            "create": "Create Scheme",
            "edit": "Edit Scheme",
            "delete": "Delete Scheme",
        }
    },
    "reports": {
        "label": "Reports",
        "actions": {
            "view": "View Reports",
            "view_profit": "View Profit Reports",
            "export": "Export Reports",
            "close_day": "Close Day",
        }
    },
    "settings": {
        "label": "Settings",
        "actions": {
            "view": "View Settings",
            "edit": "Edit Settings",
            "manage_users": "Manage Users",
            "manage_permissions": "Manage Permissions",
        }
    },
}

# Preset role templates
ROLE_PRESETS = {
    "admin": {
        "label": "Administrator",
        "description": "Full access to all features",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True, "create": True, "edit": True, "delete": True},
            "products": {"view": True, "create": True, "edit": True, "delete": True, "view_cost": True},
            "inventory": {"view": True, "adjust": True, "transfer": True},
            "sales": {"view": True, "create": True, "edit": True, "void": True, "sell_below_cost": True, "give_discount": True},
            "purchase_orders": {"view": True, "create": True, "edit": True, "receive": True, "delete": True},
            "suppliers": {"view": True, "create": True, "edit": True, "delete": True},
            "customers": {"view": True, "create": True, "edit": True, "delete": True, "view_balance": True, "manage_credit": True},
            "accounting": {"view": True, "receive_payment": True, "create_expense": True, "edit_expense": True, "generate_interest": True, "generate_penalty": True, "manage_funds": True},
            "price_schemes": {"view": True, "create": True, "edit": True, "delete": True},
            "reports": {"view": True, "view_profit": True, "export": True, "close_day": True},
            "settings": {"view": True, "edit": True, "manage_users": True, "manage_permissions": True},
        }
    },
    "manager": {
        "label": "Branch Manager",
        "description": "Manage branch operations, limited admin access",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True, "create": False, "edit": True, "delete": False},
            "products": {"view": True, "create": True, "edit": True, "delete": False, "view_cost": True},
            "inventory": {"view": True, "adjust": True, "transfer": True},
            "sales": {"view": True, "create": True, "edit": True, "void": True, "sell_below_cost": False, "give_discount": True},
            "purchase_orders": {"view": True, "create": True, "edit": True, "receive": True, "delete": False},
            "suppliers": {"view": True, "create": True, "edit": True, "delete": False},
            "customers": {"view": True, "create": True, "edit": True, "delete": False, "view_balance": True, "manage_credit": True},
            "accounting": {"view": True, "receive_payment": True, "create_expense": True, "edit_expense": True, "generate_interest": True, "generate_penalty": True, "manage_funds": True},
            "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
            "reports": {"view": True, "view_profit": True, "export": True, "close_day": True},
            "settings": {"view": True, "edit": False, "manage_users": False, "manage_permissions": False},
        }
    },
    "cashier": {
        "label": "Cashier",
        "description": "POS operations and basic customer service",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True, "create": False, "edit": False, "delete": False},
            "products": {"view": True, "create": False, "edit": False, "delete": False, "view_cost": False},
            "inventory": {"view": True, "adjust": False, "transfer": False},
            "sales": {"view": True, "create": True, "edit": False, "void": False, "sell_below_cost": False, "give_discount": False},
            "purchase_orders": {"view": False, "create": False, "edit": False, "receive": False, "delete": False},
            "suppliers": {"view": False, "create": False, "edit": False, "delete": False},
            "customers": {"view": True, "create": True, "edit": False, "delete": False, "view_balance": False, "manage_credit": False},
            "accounting": {"view": False, "receive_payment": False, "create_expense": False, "edit_expense": False, "generate_interest": False, "generate_penalty": False, "manage_funds": False},
            "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
            "reports": {"view": False, "view_profit": False, "export": False, "close_day": False},
            "settings": {"view": False, "edit": False, "manage_users": False, "manage_permissions": False},
        }
    },
    "inventory_clerk": {
        "label": "Inventory Clerk",
        "description": "Manage inventory and stock operations",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True, "create": False, "edit": False, "delete": False},
            "products": {"view": True, "create": True, "edit": True, "delete": False, "view_cost": True},
            "inventory": {"view": True, "adjust": True, "transfer": True},
            "sales": {"view": True, "create": False, "edit": False, "void": False, "sell_below_cost": False, "give_discount": False},
            "purchase_orders": {"view": True, "create": True, "edit": True, "receive": True, "delete": False},
            "suppliers": {"view": True, "create": True, "edit": True, "delete": False},
            "customers": {"view": False, "create": False, "edit": False, "delete": False, "view_balance": False, "manage_credit": False},
            "accounting": {"view": False, "receive_payment": False, "create_expense": False, "edit_expense": False, "generate_interest": False, "generate_penalty": False, "manage_funds": False},
            "price_schemes": {"view": True, "create": False, "edit": False, "delete": False},
            "reports": {"view": True, "view_profit": False, "export": False, "close_day": False},
            "settings": {"view": False, "edit": False, "manage_users": False, "manage_permissions": False},
        }
    },
}

# Legacy mapping for backward compatibility
DEFAULT_PERMISSIONS = {
    "admin": ROLE_PRESETS["admin"]["permissions"],
    "manager": ROLE_PRESETS["manager"]["permissions"],
    "cashier": ROLE_PRESETS["cashier"]["permissions"],
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
    """Check if user has permission for a specific action on a module.
    Admin role always has full access.
    Maps legacy module names to new structure for backward compatibility.
    """
    if user.get("role") == "admin":
        return
    
    # Legacy module name mapping
    module_map = {
        "pos": "sales",  # pos.sell -> sales.create, pos.void -> sales.void
    }
    actual_module = module_map.get(module, module)
    
    # Legacy action mapping
    action_map = {
        ("pos", "sell"): ("sales", "create"),
        ("accounting", "create"): ("accounting", "receive_payment"),  # general accounting permission
    }
    if (module, action) in action_map:
        actual_module, action = action_map[(module, action)]
    
    perms = user.get("permissions", {})
    module_perms = perms.get(actual_module, {})
    
    if not module_perms.get(action, False):
        raise HTTPException(status_code=403, detail=f"No permission: {actual_module}.{action}")

def has_perm(user: dict, module: str, action: str) -> bool:
    """Check permission without raising exception - returns boolean."""
    if user.get("role") == "admin":
        return True
    
    module_map = {"pos": "sales"}
    actual_module = module_map.get(module, module)
    
    perms = user.get("permissions", {})
    return perms.get(actual_module, {}).get(action, False)

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

async def log_sale_items(branch_id, date, items, invoice_number, customer_name, payment_method, cashier_name):
    """Record each sold item to sequential sales log"""
    last = await db.sales_log.find_one({"branch_id": branch_id, "date": date}, {"_id": 0}, sort=[("sequence", -1)])
    seq = last["sequence"] if last else 0
    running = last["running_total"] if last else 0
    for item in items:
        seq += 1
        lt = float(item.get("total", item.get("quantity", 0) * item.get("rate", item.get("price", 0))))
        running = round(running + lt, 2)
        entry = {
            "id": new_id(), "branch_id": branch_id, "date": date, "sequence": seq,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"), "timestamp": now_iso(),
            "product_name": item.get("product_name", ""), "product_id": item.get("product_id", ""),
            "quantity": float(item.get("quantity", 0)),
            "unit_price": float(item.get("rate", item.get("price", 0))),
            "discount": float(item.get("discount_amount", 0)),
            "line_total": lt, "running_total": running,
            "category": item.get("category", ""),
            "invoice_number": invoice_number, "customer_name": customer_name,
            "payment_method": payment_method, "cashier_name": cashier_name,
        }
        await db.sales_log.insert_one(entry)

async def get_active_date(branch_id):
    """Return today's date unless closed, then return next day"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closed = await db.daily_closings.find_one({"branch_id": branch_id, "date": today, "status": "closed"}, {"_id": 0})
    if closed:
        from datetime import timedelta
        next_day = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        return next_day
    return today

async def update_cashier_wallet(branch_id, amount, reference=""):
    """Update cashier drawer wallet balance in real-time. Positive = cash in, negative = cash out."""
    wallet = await db.fund_wallets.find_one({"branch_id": branch_id, "type": "cashier", "active": True}, {"_id": 0})
    if not wallet:
        wallet = {"id": new_id(), "branch_id": branch_id, "type": "cashier",
                  "name": "Cashier Drawer", "balance": 0, "active": True, "created_at": now_iso()}
        await db.fund_wallets.insert_one(wallet)
        del wallet["_id"]
    await db.fund_wallets.update_one({"id": wallet["id"]}, {"$inc": {"balance": round(amount, 2)}})
    await db.wallet_movements.insert_one({
        "id": new_id(), "wallet_id": wallet["id"], "branch_id": branch_id,
        "type": "cash_in" if amount >= 0 else "cash_out", "amount": round(amount, 2),
        "reference": reference, "created_at": now_iso()
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

@api_router.post("/auth/verify-manager-pin")
async def verify_manager_pin(data: dict, user=Depends(get_current_user)):
    """Verify manager/admin PIN for credit sale approval"""
    pin = data.get("pin", "")
    if not pin:
        raise HTTPException(status_code=400, detail="PIN required")
    
    # Find managers/admins with matching PIN
    managers = await db.users.find(
        {"role": {"$in": ["admin", "manager"]}, "active": True},
        {"_id": 0}
    ).to_list(100)
    
    for mgr in managers:
        # Check if PIN matches (stored in user record or password last 4 digits)
        mgr_pin = mgr.get("manager_pin", "")
        if not mgr_pin:
            # Fallback: use last 4 chars of password hash as PIN for demo
            mgr_pin = mgr.get("password_hash", "")[-4:]
        if mgr_pin and pin == mgr_pin:
            return {"valid": True, "manager_id": mgr["id"], "manager_name": mgr.get("full_name", mgr["username"])}
    
    return {"valid": False}

@api_router.put("/auth/set-manager-pin")
async def set_manager_pin(data: dict, user=Depends(get_current_user)):
    """Set manager PIN for credit approvals"""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only managers/admins can set PINs")
    pin = data.get("pin", "")
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    await db.users.update_one({"id": user["id"]}, {"$set": {"manager_pin": pin}})
    return {"message": "PIN set successfully"}

# ==================== UNIFIED SALES ENDPOINT ====================
@api_router.post("/unified-sale")
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
        
        # Check capital rule
        if rate > 0 and rate < product.get("cost_price", 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell '{product['name']}' at ₱{rate:.2f} — below capital ₱{product['cost_price']:.2f}"
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
            parent_inv = await db.inventory.find_one({"product_id": product["parent_id"], "branch_id": branch_id}, {"_id": 0})
            parent_stock = parent_inv["quantity"] if parent_inv else 0
            available = parent_stock * units_per_parent
            
            if available < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product['name']}: have {available:.0f}, need {qty:.0f}")
            
            await db.inventory.update_one(
                {"product_id": product["parent_id"], "branch_id": branch_id},
                {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                upsert=True
            )
            await log_movement(product["parent_id"], branch_id, "sale", -parent_deduction, "", inv_number,
                              rate * units_per_parent, user["id"], user.get("full_name", user["username"]),
                              f"Sold as repack: {product['name']} x {qty}")
        else:
            # Regular product
            inv = await db.inventory.find_one({"product_id": item["product_id"], "branch_id": branch_id}, {"_id": 0})
            current_stock = inv["quantity"] if inv else 0
            
            if current_stock < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product['name']}: have {current_stock:.0f}, need {qty:.0f}")
            
            await db.inventory.update_one(
                {"product_id": item["product_id"], "branch_id": branch_id},
                {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}},
                upsert=True
            )
            await log_movement(item["product_id"], branch_id, "sale", -qty, "", inv_number,
                              rate, user["id"], user.get("full_name", user["username"]))
        
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
        from datetime import timedelta
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
    
    await log_sale_items(branch_id, active_date, sale_items, inv_number,
                         customer_name, data.get("payment_method", "Cash" if payment_type == "cash" else "Credit"),
                         user.get("full_name", user["username"]))
    
    return invoice

@api_router.get("/customers/{customer_id}/transactions")
async def get_customer_transactions(customer_id: str, user=Depends(get_current_user)):
    """Get all transactions for a customer (invoices + payments + receivables)"""
    # Get all invoices for customer
    invoices = await db.invoices.find(
        {"customer_id": customer_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    # Get all receivables (from old POS system)
    receivables = await db.receivables.find(
        {"customer_id": customer_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    # Get customer info
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    
    # Calculate totals
    total_invoiced = sum(inv.get("grand_total", 0) for inv in invoices)
    total_paid = sum(inv.get("amount_paid", 0) for inv in invoices)
    total_balance = sum(inv.get("balance", 0) for inv in invoices if inv.get("status") != "paid")
    
    # Add receivables totals
    total_receivables = sum(r.get("balance", 0) for r in receivables if r.get("status") != "paid")
    
    return {
        "customer": customer,
        "invoices": invoices,
        "receivables": receivables,
        "summary": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_balance": total_balance + total_receivables,
            "invoice_count": len(invoices),
            "open_invoices": len([i for i in invoices if i.get("status") not in ["paid", "voided"]]),
        }
    }

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

@api_router.put("/products/{product_id}/update-price")
async def update_product_price(product_id: str, data: dict, user=Depends(get_current_user)):
    """Update a specific price scheme for a product"""
    check_perm(user, "products", "edit")
    scheme = data.get("scheme")
    new_price = float(data.get("price", 0))
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Hard rule: cannot set price below cost
    if new_price < product.get("cost_price", 0) and new_price > 0:
        raise HTTPException(status_code=400, detail=f"Price ₱{new_price:.2f} is below capital ₱{product['cost_price']:.2f}")
    prices = product.get("prices", {})
    prices[scheme] = new_price
    await db.products.update_one({"id": product_id}, {"$set": {"prices": prices, "updated_at": now_iso()}})
    return {"message": f"{scheme} price updated to ₱{new_price:.2f}", "prices": prices}

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
        # For repacks: calculate available from parent stock
        if p.get("is_repack") and p.get("parent_id"):
            parent = await db.products.find_one({"id": p["parent_id"]}, {"_id": 0})
            pinv = await db.inventory.find_one({"product_id": p["parent_id"], "branch_id": branch_id}, {"_id": 0}) if branch_id else None
            parent_stock = pinv["quantity"] if pinv else 0
            units_per_parent = p.get("units_per_parent", 1)
            # Repack available = parent stock × units_per_parent
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
        # HARD RULE: Never sell below capital
        if item.get("product_id"):
            prod_check = await db.products.find_one({"id": item["product_id"]}, {"_id": 0, "cost_price": 1, "name": 1})
            if prod_check and rate < prod_check.get("cost_price", 0) and rate > 0:
                raise HTTPException(status_code=400,
                    detail=f"Cannot sell '{prod_check.get('name', '')}' at ₱{rate:.2f} — below capital ₱{prod_check['cost_price']:.2f}")
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
                product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
                
                # For repacks: only deduct from parent
                if product and product.get("is_repack") and product.get("parent_id"):
                    units_per_parent = product.get("units_per_parent", 1)
                    parent_deduction = item["quantity"] / units_per_parent
                    await db.inventory.update_one(
                        {"product_id": product["parent_id"], "branch_id": branch_id},
                        {"$inc": {"quantity": -parent_deduction}, "$set": {"updated_at": now_iso()}},
                        upsert=True
                    )
                    await log_movement(product["parent_id"], branch_id, "sale", -parent_deduction,
                                       invoice["id"], inv_number, item["rate"] * units_per_parent, user["id"],
                                       user.get("full_name", user["username"]),
                                       f"Sold as repack: {product['name']} x {item['quantity']}")
                else:
                    # Regular product: deduct from its own inventory
                    await db.inventory.update_one(
                        {"product_id": item["product_id"], "branch_id": branch_id},
                        {"$inc": {"quantity": -item["quantity"]}, "$set": {"updated_at": now_iso()}},
                        upsert=True
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
        # Update cashier wallet with initial payment
        fund_source = data.get("fund_source", "cashier")
        if fund_source == "cashier":
            await update_cashier_wallet(branch_id, amount_paid, f"Invoice payment {inv_number}")
    await db.invoices.insert_one(invoice)
    del invoice["_id"]
    # Log to sequential sales log
    active_date = await get_active_date(branch_id)
    # Enrich items with category for log
    for item in items:
        if item["product_id"]:
            prod = await db.products.find_one({"id": item["product_id"]}, {"_id": 0, "category": 1})
            item["category"] = prod.get("category", "General") if prod else "General"
    await log_sale_items(branch_id, active_date, items, inv_number,
                         data.get("customer_name", "Walk-in"),
                         data.get("payment_method", "Cash"),
                         user.get("full_name", user["username"]))
    return invoice

@api_router.get("/invoices/{inv_id}")
async def get_invoice(inv_id: str, user=Depends(get_current_user)):
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        # Try sales collection
        inv = await db.sales.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        # Try purchase orders
        inv = await db.purchase_orders.find_one({"id": inv_id}, {"_id": 0})
    if not inv: raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Include edit history and count
    edit_history = await db.invoice_edits.find(
        {"invoice_id": inv_id}, {"_id": 0}
    ).sort("edited_at", -1).to_list(100)
    inv["edit_history"] = edit_history
    inv["edit_count"] = len(edit_history)
    
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

@api_router.get("/customers/{customer_id}/payment-history")
async def get_customer_payment_history(customer_id: str, user=Depends(get_current_user)):
    """Get all payment transactions for a customer across all invoices."""
    pipeline = [
        {"$match": {"customer_id": customer_id, "payments": {"$ne": []}}},
        {"$unwind": "$payments"},
        {"$project": {
            "_id": 0, "invoice_number": 1, "customer_name": 1,
            "grand_total": 1, "sale_type": 1,
            "date": "$payments.date", "amount": "$payments.amount",
            "method": "$payments.method", "reference": "$payments.reference",
            "applied_to_interest": "$payments.applied_to_interest",
            "applied_to_principal": "$payments.applied_to_principal",
            "recorded_by": "$payments.recorded_by", "recorded_at": "$payments.recorded_at",
        }},
        {"$sort": {"date": -1, "recorded_at": -1}},
    ]
    payments = await db.invoices.aggregate(pipeline).to_list(500)
    return payments

@api_router.get("/customers/{customer_id}/charges-preview")
async def preview_customer_charges(customer_id: str, as_of_date: Optional[str] = None, user=Depends(get_current_user)):
    """
    Preview interest and penalty charges for a customer WITHOUT creating invoices.
    Shows breakdown per invoice with days overdue, grace period, and computed amounts.
    Used for auto-preview when receiving payments.
    """
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    comp_date_str = as_of_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d")
    
    # Get customer's grace period (default 7 days)
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
        
        # Use invoice-level interest rate, fallback to customer rate (handle 0 as falsy)
        rate = inv.get("interest_rate") or default_interest_rate
        due_date_str = inv.get("due_date") or inv.get("order_date") or comp_date_str
        if not due_date_str:
            continue  # Skip invoices without any date
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        
        # Grace period: interest starts after due_date + grace_period
        grace_end_date = due_date + timedelta(days=grace_period)
        
        # Days overdue (from due date, not grace end)
        days_overdue = max(0, (comp_date - due_date).days)
        
        # Days for interest calculation (from grace end or last_interest_date)
        if comp_date <= grace_end_date:
            # Still within grace period - no interest
            interest_days = 0
        else:
            # Interest starts from grace_end_date or last_interest_date (whichever is later)
            last_date_str = inv.get("last_interest_date")
            if last_date_str:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                interest_start = max(grace_end_date, last_date)
            else:
                interest_start = grace_end_date
            interest_days = max(0, (comp_date - interest_start).days)
        
        principal = inv.get("balance", 0)  # Use current balance, not grand_total
        total_principal += principal
        
        # Calculate interest (simple daily: rate%/30 per day)
        if rate > 0 and interest_days > 0:
            daily_rate = (rate / 100) / 30
            interest = round(principal * daily_rate * interest_days, 2)
            if interest > 0:
                total_interest += interest
                interest_preview.append({
                    "invoice_number": inv["invoice_number"],
                    "invoice_id": inv["id"],
                    "due_date": due_date_str,
                    "grace_end_date": grace_end_date.strftime("%Y-%m-%d"),
                    "days_overdue": days_overdue,
                    "interest_days": interest_days,
                    "balance": principal,
                    "interest_rate": rate,
                    "computed_interest": interest,
                    "last_interest_date": inv.get("last_interest_date"),
                })
        
        # Track overdue invoices for potential penalty (if not already penalized)
        if days_overdue > grace_period and not inv.get("penalty_applied"):
            penalty_preview.append({
                "invoice_number": inv["invoice_number"],
                "invoice_id": inv["id"],
                "due_date": due_date_str,
                "days_overdue": days_overdue,
                "balance": principal,
            })
    
    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "as_of_date": comp_date_str,
        "grace_period": grace_period,
        "default_interest_rate": default_interest_rate,
        "total_principal": total_principal,
        "total_interest_preview": total_interest,
        "total_penalty_eligible_invoices": len(penalty_preview),
        "interest_breakdown": interest_preview,
        "penalty_eligible": penalty_preview,
        "summary": {
            "principal": total_principal,
            "interest": total_interest,
            "grand_total": round(total_principal + total_interest, 2),
        }
    }

@api_router.post("/customers/{customer_id}/generate-interest")
async def generate_account_interest(customer_id: str, data: dict = {}, user=Depends(get_current_user)):
    """
    Compute interest on all overdue invoices as of a given date and create a single Interest Charge invoice.
    Respects grace period: Interest only accrues after due_date + grace_period days.
    Uses simple daily calculation: Balance × (Rate%/30) × Days Past Grace
    """
    check_perm(user, "accounting", "create")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    comp_date_str = data.get("as_of_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d")
    
    # Get customer's grace period (default 7 days)
    grace_period = customer.get("grace_period", 7)
    default_interest_rate = customer.get("interest_rate", 0)
    
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}}, {"_id": 0}
    ).to_list(500)
    
    total_interest = 0
    interest_details = []
    
    for inv in invoices:
        if inv.get("sale_type") in ("interest_charge", "penalty_charge"):
            continue
        
        # Use invoice-level interest rate, fallback to customer rate (handle 0 as falsy)
        rate = inv.get("interest_rate") or default_interest_rate
        if rate <= 0:
            continue
        
        due_date_str = inv.get("due_date") or inv.get("order_date") or comp_date_str
        if not due_date_str:
            continue
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        
        # Grace period: interest starts after due_date + grace_period
        grace_end_date = due_date + timedelta(days=grace_period)
        
        if comp_date <= grace_end_date:
            # Still within grace period - no interest
            continue
        
        # Interest starts from grace_end_date or last_interest_date (whichever is later)
        last_date_str = inv.get("last_interest_date")
        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
            interest_start = max(grace_end_date, last_date)
        else:
            interest_start = grace_end_date
        
        days = (comp_date - interest_start).days
        if days <= 0:
            continue
        
        principal = inv.get("balance", 0)  # Use current balance
        daily_rate = (rate / 100) / 30
        interest = round(principal * daily_rate * days, 2)
        
        if interest > 0:
            total_interest += interest
            interest_details.append({
                "invoice": inv["invoice_number"],
                "principal": principal,
                "days": days,
                "rate": rate,
                "interest": interest
            })
            await db.invoices.update_one(
                {"id": inv["id"]},
                {"$set": {"last_interest_date": comp_date_str}}
            )
    
    if total_interest <= 0:
        return {"message": "No interest to charge (invoices may still be within grace period)", "total": 0, "grace_period": grace_period}
    # Create interest charge invoice
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("sales_invoice", "SI") if settings else "SI"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{comp_date_str.replace('-','')}-{str(count + 1).zfill(4)}"
    branch_id = invoices[0].get("branch_id", "") if invoices else ""
    desc_lines = "; ".join([f"{d['invoice']}: {d['days']}d = ₱{d['interest']:.2f}" for d in interest_details])
    interest_invoice = {
        "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
        "customer_id": customer_id, "customer_name": customer["name"],
        "customer_contact": "", "customer_phone": "", "customer_address": "",
        "terms": "COD", "terms_days": 0, "customer_po": "",
        "sales_rep_id": "", "sales_rep_name": "", "branch_id": branch_id,
        "order_date": comp_date_str, "invoice_date": comp_date_str,
        "due_date": comp_date_str,
        "items": [{"product_id": "", "product_name": "Interest Charge",
                    "description": desc_lines, "quantity": 1,
                    "rate": total_interest, "discount_type": "amount",
                    "discount_value": 0, "discount_amount": 0,
                    "total": total_interest, "is_repack": False}],
        "subtotal": total_interest, "freight": 0, "overall_discount": 0,
        "grand_total": total_interest, "amount_paid": 0, "balance": total_interest,
        "interest_rate": 0, "interest_accrued": 0, "penalties": 0,
        "last_interest_date": None, "sale_type": "interest_charge",
        "status": "open", "payments": [],
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(interest_invoice)
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": total_interest}})
    return {"message": f"Interest invoice created: {inv_number}", "invoice_number": inv_number,
            "total_interest": total_interest, "details": interest_details}

@api_router.post("/customers/{customer_id}/generate-penalty")
async def generate_account_penalty(customer_id: str, data: dict, user=Depends(get_current_user)):
    """
    Compute one-time penalty on all overdue invoices (past grace period) and create a Penalty Charge invoice.
    Only applies to invoices that haven't been penalized yet.
    """
    check_perm(user, "accounting", "create")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    penalty_rate = float(data.get("penalty_rate", 5))
    comp_date_str = data.get("as_of_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d")
    
    # Get customer's grace period (default 7 days)
    grace_period = customer.get("grace_period", 7)
    
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}}, {"_id": 0}
    ).to_list(500)
    
    total_penalty = 0
    penalty_details = []
    penalized_invoice_ids = []
    
    for inv in invoices:
        if inv.get("sale_type") in ("interest_charge", "penalty_charge"):
            continue
        
        # Skip if already penalized (one-time penalty)
        if inv.get("penalty_applied"):
            continue
        
        due_date_str = inv.get("due_date") or inv.get("order_date") or comp_date_str
        if not due_date_str:
            continue
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        grace_end_date = due_date + timedelta(days=grace_period)
        
        # Only apply penalty if past grace period
        if comp_date <= grace_end_date:
            continue
        
        days_overdue = (comp_date - due_date).days
        principal = inv.get("balance", 0)  # Use current balance
        penalty = round(principal * penalty_rate / 100, 2)
        
        if penalty > 0:
            total_penalty += penalty
            penalty_details.append({
                "invoice": inv["invoice_number"],
                "principal": principal,
                "days_overdue": days_overdue,
                "penalty": penalty
            })
            penalized_invoice_ids.append(inv["id"])
    
    if total_penalty <= 0:
        return {"message": "No penalty to charge (invoices may be within grace period or already penalized)", "total": 0, "grace_period": grace_period}
    
    # Mark invoices as penalized
    for inv_id in penalized_invoice_ids:
        await db.invoices.update_one(
            {"id": inv_id},
            {"$set": {"penalty_applied": True, "penalty_date": comp_date_str}}
        )
    
    settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
    prefix = settings.get("value", {}).get("sales_invoice", "SI") if settings else "SI"
    count = await db.invoices.count_documents({"prefix": prefix})
    inv_number = f"{prefix}-{comp_date_str.replace('-','')}-{str(count + 1).zfill(4)}"
    branch_id = invoices[0].get("branch_id", "") if invoices else ""
    desc_lines = "; ".join([f"{d['invoice']}: {d['days_overdue']}d overdue = ₱{d['penalty']:.2f}" for d in penalty_details])
    
    penalty_invoice = {
        "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
        "customer_id": customer_id, "customer_name": customer["name"],
        "customer_contact": "", "customer_phone": "", "customer_address": "",
        "terms": "COD", "terms_days": 0, "customer_po": "",
        "sales_rep_id": "", "sales_rep_name": "", "branch_id": branch_id,
        "order_date": comp_date_str, "invoice_date": comp_date_str,
        "due_date": comp_date_str,
        "items": [{"product_id": "", "product_name": "Penalty Charge",
                    "description": desc_lines, "quantity": 1,
                    "rate": total_penalty, "discount_type": "amount",
                    "discount_value": 0, "discount_amount": 0,
                    "total": total_penalty, "is_repack": False}],
        "subtotal": total_penalty, "freight": 0, "overall_discount": 0,
        "grand_total": total_penalty, "amount_paid": 0, "balance": total_penalty,
        "interest_rate": 0, "interest_accrued": 0, "penalties": 0,
        "last_interest_date": None, "sale_type": "penalty_charge",
        "status": "open", "payments": [],
        "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(penalty_invoice)
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": total_penalty}})
    return {"message": f"Penalty invoice created: {inv_number}", "invoice_number": inv_number,
            "total_penalty": total_penalty, "penalty_rate": penalty_rate, "details": penalty_details}

@api_router.post("/customers/{customer_id}/receive-payment")
async def receive_customer_payment(customer_id: str, data: dict, user=Depends(get_current_user)):
    """QuickBooks-style payment: auto-allocate to interest first, penalty second, then oldest invoice."""
    check_perm(user, "accounting", "create")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer: raise HTTPException(status_code=404, detail="Customer not found")
    amount = float(data["amount"])
    pay_date = data.get("date", now_iso()[:10])
    method = data.get("method", "Cash")
    reference = data.get("reference", "")
    if amount <= 0: raise HTTPException(status_code=400, detail="Amount must be positive")
    # Get all open invoices, sorted: interest_charge first, penalty_charge second, then by oldest date
    invoices = await db.invoices.find(
        {"customer_id": customer_id, "status": {"$nin": ["voided", "paid"]}, "balance": {"$gt": 0}}, {"_id": 0}
    ).to_list(500)
    def sort_key(inv):
        if inv.get("sale_type") == "interest_charge": return (0, inv.get("order_date", ""))
        if inv.get("sale_type") == "penalty_charge": return (1, inv.get("order_date", ""))
        return (2, inv.get("order_date", ""))
    invoices.sort(key=sort_key)
    remaining = amount
    allocations = []
    for inv in invoices:
        if remaining <= 0: break
        bal = inv["balance"]
        apply = min(remaining, bal)
        # Record payment on this invoice
        interest_owed = inv.get("interest_accrued", 0) + inv.get("penalties", 0)
        applied_interest = min(apply, interest_owed)
        applied_principal = apply - applied_interest
        new_interest = max(0, round(inv.get("interest_accrued", 0) - applied_interest, 2))
        new_balance = round(bal - apply, 2)
        new_paid = round(inv.get("amount_paid", 0) + apply, 2)
        new_status = "paid" if new_balance <= 0 else "partial"
        payment = {
            "id": new_id(), "amount": apply, "date": pay_date,
            "method": method, "fund_source": "cashier", "reference": reference,
            "applied_to_interest": applied_interest, "applied_to_principal": applied_principal,
            "recorded_by": user.get("full_name", user["username"]), "recorded_at": now_iso(),
        }
        await db.invoices.update_one({"id": inv["id"]}, {
            "$set": {"balance": max(0, new_balance), "amount_paid": new_paid,
                     "interest_accrued": new_interest, "status": new_status},
            "$push": {"payments": payment}
        })
        allocations.append({
            "invoice": inv["invoice_number"], "type": inv.get("sale_type", "regular"),
            "applied": apply, "new_balance": max(0, new_balance), "status": new_status
        })
        remaining = round(remaining - apply, 2)
    # Deposit to cashier wallet
    total_applied = round(amount - remaining, 2)
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": -total_applied}})
    branch_id = invoices[0].get("branch_id", "") if invoices else ""
    if total_applied > 0 and branch_id:
        await update_cashier_wallet(branch_id, total_applied, f"Payment from {customer['name']} - {method} {reference}".strip())
    return {"message": "Payment applied", "total_received": amount, "total_applied": total_applied,
            "remaining": remaining, "allocations": allocations, "deposited_to": "Cashier Drawer"}

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

@api_router.get("/fund-wallets/{wallet_id}/movements")
async def get_wallet_movements(wallet_id: str, user=Depends(get_current_user), limit: int = 50):
    movements = await db.wallet_movements.find(
        {"wallet_id": wallet_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return movements

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
    payment_method = data.get("payment_method", "cash")
    branch_id = data.get("branch_id", "")
    po = {
        "id": new_id(),
        "po_number": data.get("po_number", "").strip() or f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}",
        "vendor": data["vendor"], "branch_id": branch_id,
        "items": [{"product_id": i["product_id"], "product_name": i.get("product_name", ""),
                    "quantity": float(i["quantity"]), "unit_price": float(i.get("unit_price", 0)),
                    "total": float(i["quantity"]) * float(i.get("unit_price", 0))} for i in items],
        "subtotal": subtotal, "status": data.get("status", "ordered"),
        "purchase_date": data.get("purchase_date", now_iso()[:10]),
        "payment_method": payment_method,
        "payment_status": "paid" if payment_method == "cash" else "unpaid",
        "amount_paid": subtotal if payment_method == "cash" else 0,
        "balance": 0 if payment_method == "cash" else subtotal,
        "received_date": None,
        "notes": data.get("notes", ""),
        "created_by": user["id"], "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.purchase_orders.insert_one(po)
    del po["_id"]
    # Cash payment: deduct from cashier drawer
    if payment_method == "cash" and subtotal > 0:
        await update_cashier_wallet(branch_id, -subtotal, f"PO Payment {po['po_number']} - {data['vendor']}")
    # Credit: create payable
    if payment_method == "credit" and subtotal > 0:
        await db.payables.insert_one({
            "id": new_id(), "supplier": data["vendor"], "branch_id": branch_id,
            "description": f"Purchase Order {po['po_number']}", "po_id": po["id"],
            "amount": subtotal, "paid": 0, "balance": subtotal,
            "due_date": data.get("due_date", ""), "status": "pending",
            "created_at": now_iso(),
        })
    return po

@api_router.put("/purchase-orders/{po_id}")
async def update_purchase_order(po_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    allowed = ["vendor", "items", "purchase_date", "notes", "status", "branch_id"]
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
        # Update product cost: Last Purchase + Moving Average
        product_update = {"last_vendor": po["vendor"], "cost_price": price}
        # Recalculate moving average from all purchase movements
        all_purchases = await db.movements.find(
            {"product_id": pid, "type": "purchase", "quantity_change": {"$gt": 0}}, {"_id": 0}
        ).to_list(10000)
        total_pqty = sum(m["quantity_change"] for m in all_purchases)
        total_pcost = sum(m["quantity_change"] * m.get("price_at_time", 0) for m in all_purchases)
        if total_pqty > 0:
            product_update["moving_average_cost"] = round(total_pcost / total_pqty, 2)
        await db.products.update_one({"id": pid}, {"$set": product_update})
        # Update vendor last_price
        await db.product_vendors.update_many(
            {"product_id": pid, "vendor_name": po["vendor"]},
            {"$set": {"last_price": price, "last_order_date": now_iso()[:10]}}
        )
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "received", "received_date": now_iso()}})
    return {"message": "PO received, inventory updated"}

@api_router.delete("/purchase-orders/{po_id}")
async def cancel_purchase_order(po_id: str, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "cancelled"}})
    return {"message": "PO cancelled"}

@api_router.post("/purchase-orders/{po_id}/pay")
async def pay_purchase_order(po_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po: raise HTTPException(status_code=404, detail="PO not found")
    if po.get("payment_status") == "paid": raise HTTPException(status_code=400, detail="PO already paid")
    amount = float(data.get("amount", po.get("balance", po["subtotal"])))
    branch_id = po.get("branch_id", "")
    ref_parts = [f"PO Payment {po['po_number']} - {po['vendor']}"]
    if data.get("check_number"): ref_parts.append(f"Check #{data['check_number']}")
    await update_cashier_wallet(branch_id, -amount, " ".join(ref_parts))
    new_paid = po.get("amount_paid", 0) + amount
    new_balance = max(0, round(po["subtotal"] - new_paid, 2))
    new_status = "paid" if new_balance <= 0 else "partial"
    payment_record = {
        "id": new_id(), "amount": amount, "date": data.get("payment_date", now_iso()[:10]),
        "check_number": data.get("check_number", ""), "check_date": data.get("check_date", ""),
        "method": data.get("method", "Cash"),
        "recorded_by": user.get("full_name", user["username"]), "recorded_at": now_iso(),
    }
    await db.purchase_orders.update_one({"id": po_id}, {
        "$set": {"amount_paid": new_paid, "balance": new_balance, "payment_status": new_status},
        "$push": {"payment_history": payment_record}
    })
    payable = await db.payables.find_one({"po_id": po_id}, {"_id": 0})
    if payable:
        pay_new_paid = payable["paid"] + amount
        pay_new_balance = max(0, round(payable["amount"] - pay_new_paid, 2))
        pay_status = "paid" if pay_new_balance <= 0 else "partial"
        await db.payables.update_one({"po_id": po_id}, {"$set": {"paid": pay_new_paid, "balance": pay_new_balance, "status": pay_status}})
    return {"message": "Payment recorded", "new_balance": new_balance, "payment_status": new_status}

@api_router.get("/purchase-orders/vendors")
async def list_po_vendors(user=Depends(get_current_user)):
    """Get unique vendor names from purchase orders."""
    vendors = await db.purchase_orders.distinct("vendor", {"status": {"$ne": "cancelled"}})
    return sorted(vendors)

@api_router.get("/purchase-orders/by-vendor")
async def get_vendor_pos(vendor: str, user=Depends(get_current_user)):
    """Get all POs for a vendor, unpaid ones first."""
    pos = await db.purchase_orders.find(
        {"vendor": vendor, "status": {"$ne": "cancelled"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return pos

# =============================================================================
# INVOICE DETAIL & EDIT ROUTES  
# =============================================================================
# Note: GET /invoices/{inv_id} with edit_history is defined above in INVOICE / SALES ORDER section

@api_router.get("/invoices/by-number/{invoice_number}")
async def get_invoice_by_number(invoice_number: str, user=Depends(get_current_user)):
    """Get invoice by invoice number (searches all collections)."""
    # Search in invoices
    invoice = await db.invoices.find_one({"invoice_number": invoice_number}, {"_id": 0})
    if invoice:
        invoice["_collection"] = "invoices"
        return invoice
    
    # Search in sales
    sale = await db.sales.find_one({"sale_number": invoice_number}, {"_id": 0})
    if sale:
        sale["_collection"] = "sales"
        return sale
    
    # Search in purchase orders
    po = await db.purchase_orders.find_one({"po_number": invoice_number}, {"_id": 0})
    if po:
        po["_collection"] = "purchase_orders"
        return po
    
    raise HTTPException(status_code=404, detail="Invoice not found")

@api_router.put("/invoices/{invoice_id}/edit")
async def edit_invoice(invoice_id: str, data: dict, user=Depends(get_current_user)):
    """
    Edit an invoice with reason and optional proof.
    Handles inventory adjustments when items are changed.
    Updates product cost when PO items are edited.
    """
    check_perm(user, "pos", "edit")
    
    reason = data.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Edit reason is required")
    
    # Find the invoice
    collection_name = data.get("_collection", "invoices")
    if collection_name == "invoices":
        invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        collection = db.invoices
        id_field = "invoice_number"
    elif collection_name == "sales":
        invoice = await db.sales.find_one({"id": invoice_id}, {"_id": 0})
        collection = db.sales
        id_field = "sale_number"
    elif collection_name == "purchase_orders":
        invoice = await db.purchase_orders.find_one({"id": invoice_id}, {"_id": 0})
        collection = db.purchase_orders
        id_field = "po_number"
    else:
        raise HTTPException(status_code=400, detail="Invalid collection type")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Prevent editing voided invoices
    if invoice.get("status") == "voided":
        raise HTTPException(status_code=400, detail="Cannot edit voided invoice")
    
    # Store original state for history
    original_state = {
        "items": invoice.get("items", []),
        "customer_name": invoice.get("customer_name", ""),
        "customer_id": invoice.get("customer_id"),
        "subtotal": invoice.get("subtotal", 0),
        "grand_total": invoice.get("grand_total", 0),
        "notes": invoice.get("notes", ""),
    }
    
    branch_id = invoice.get("branch_id", "")
    changes_made = []
    inventory_adjustments = []
    
    # Handle item changes
    new_items = data.get("items")
    if new_items is not None:
        old_items = {item.get("product_id"): item for item in invoice.get("items", [])}
        new_items_map = {item.get("product_id"): item for item in new_items}
        
        # Check for removed or reduced items (return to inventory)
        for prod_id, old_item in old_items.items():
            new_item = new_items_map.get(prod_id)
            old_qty = old_item.get("quantity", 0)
            new_qty = new_item.get("quantity", 0) if new_item else 0
            qty_diff = old_qty - new_qty
            
            if qty_diff > 0:
                # Return stock (positive adjustment)
                product = await db.products.find_one({"id": prod_id}, {"_id": 0})
                if product:
                    if product.get("is_repack") and product.get("parent_id"):
                        # Repack: return to parent
                        units_per_parent = product.get("units_per_parent", 1)
                        parent_return = qty_diff / units_per_parent
                        await db.inventory.update_one(
                            {"product_id": product["parent_id"], "branch_id": branch_id},
                            {"$inc": {"quantity": parent_return}},
                            upsert=True
                        )
                        inventory_adjustments.append({
                            "product_id": product["parent_id"],
                            "change": parent_return,
                            "reason": f"Edit return from repack {product['name']}"
                        })
                    else:
                        await db.inventory.update_one(
                            {"product_id": prod_id, "branch_id": branch_id},
                            {"$inc": {"quantity": qty_diff}},
                            upsert=True
                        )
                        inventory_adjustments.append({
                            "product_id": prod_id,
                            "change": qty_diff,
                            "reason": f"Edit return"
                        })
                changes_made.append(f"Reduced {old_item.get('product_name', prod_id)} qty: {old_qty} → {new_qty}")
        
        # Check for added or increased items (deduct from inventory)
        for prod_id, new_item in new_items_map.items():
            old_item = old_items.get(prod_id)
            old_qty = old_item.get("quantity", 0) if old_item else 0
            new_qty = new_item.get("quantity", 0)
            qty_diff = new_qty - old_qty
            
            if qty_diff > 0:
                # Deduct stock
                product = await db.products.find_one({"id": prod_id}, {"_id": 0})
                if product:
                    if product.get("is_repack") and product.get("parent_id"):
                        units_per_parent = product.get("units_per_parent", 1)
                        parent_deduction = qty_diff / units_per_parent
                        await db.inventory.update_one(
                            {"product_id": product["parent_id"], "branch_id": branch_id},
                            {"$inc": {"quantity": -parent_deduction}},
                            upsert=True
                        )
                        inventory_adjustments.append({
                            "product_id": product["parent_id"],
                            "change": -parent_deduction,
                            "reason": f"Edit deduction for repack {product['name']}"
                        })
                    else:
                        await db.inventory.update_one(
                            {"product_id": prod_id, "branch_id": branch_id},
                            {"$inc": {"quantity": -qty_diff}},
                            upsert=True
                        )
                        inventory_adjustments.append({
                            "product_id": prod_id,
                            "change": -qty_diff,
                            "reason": f"Edit deduction"
                        })
                
                if old_qty == 0:
                    changes_made.append(f"Added {new_item.get('product_name', prod_id)} qty: {new_qty}")
                else:
                    changes_made.append(f"Increased {new_item.get('product_name', prod_id)} qty: {old_qty} → {new_qty}")
            
            # Check for price changes
            if old_item:
                old_rate = old_item.get("rate", 0)
                new_rate = new_item.get("rate", 0)
                if old_rate != new_rate:
                    changes_made.append(f"Price changed for {new_item.get('product_name', prod_id)}: ₱{old_rate} → ₱{new_rate}")
                    
                    # For POs, update product cost
                    if collection_name == "purchase_orders" and new_rate > 0:
                        await db.products.update_one(
                            {"id": prod_id},
                            {"$set": {"cost_price": new_rate, "updated_at": now_iso()}}
                        )
                        changes_made.append(f"Updated product cost to ₱{new_rate}")
    
    # Prepare update data
    update_data = {}
    
    # Allowed editable fields
    editable_fields = ["customer_name", "customer_id", "notes", "terms", "customer_po", 
                       "sales_rep_name", "sales_rep_id", "freight", "overall_discount"]
    for field in editable_fields:
        if field in data:
            old_val = invoice.get(field)
            new_val = data[field]
            if old_val != new_val:
                update_data[field] = new_val
                changes_made.append(f"{field}: '{old_val}' → '{new_val}'")
    
    # Update items if provided
    if new_items is not None:
        # Recalculate totals
        subtotal = 0
        for item in new_items:
            qty = item.get("quantity", 0)
            rate = item.get("rate", 0)
            disc_type = item.get("discount_type", "amount")
            disc_val = item.get("discount_value", 0)
            disc_amt = disc_val if disc_type == "amount" else round(qty * rate * disc_val / 100, 2)
            item["discount_amount"] = disc_amt
            item["total"] = round(qty * rate - disc_amt, 2)
            subtotal += item["total"]
        
        freight = data.get("freight", invoice.get("freight", 0))
        overall_discount = data.get("overall_discount", invoice.get("overall_discount", 0))
        grand_total = round(subtotal + freight - overall_discount, 2)
        
        # Calculate new balance
        amount_paid = invoice.get("amount_paid", 0)
        new_balance = max(0, grand_total - amount_paid)
        
        update_data["items"] = new_items
        update_data["subtotal"] = subtotal
        update_data["grand_total"] = grand_total
        update_data["balance"] = new_balance
        
        # Update status based on balance
        if new_balance <= 0:
            update_data["status"] = "paid"
        elif amount_paid > 0:
            update_data["status"] = "partial"
        else:
            update_data["status"] = "open"
        
        # Update customer balance if changed
        if invoice.get("customer_id"):
            old_balance = invoice.get("balance", 0)
            balance_diff = new_balance - old_balance
            if balance_diff != 0:
                await db.customers.update_one(
                    {"id": invoice["customer_id"]},
                    {"$inc": {"balance": balance_diff}}
                )
    
    if not update_data and not changes_made:
        return {"message": "No changes made", "invoice": invoice}
    
    # Mark as edited
    update_data["edited"] = True
    update_data["last_edited_at"] = now_iso()
    update_data["last_edited_by"] = user.get("full_name", user["username"])
    update_data["updated_at"] = now_iso()
    
    # Apply update
    await collection.update_one({"id": invoice_id}, {"$set": update_data})
    
    # Create edit history record
    edit_record = {
        "id": new_id(),
        "invoice_id": invoice_id,
        "invoice_number": invoice.get(id_field, ""),
        "collection": collection_name,
        "edited_by_id": user["id"],
        "edited_by_name": user.get("full_name", user["username"]),
        "edited_at": now_iso(),
        "reason": reason,
        "proof_url": data.get("proof_url"),
        "changes": changes_made,
        "original_state": original_state,
        "inventory_adjustments": inventory_adjustments,
    }
    await db.invoice_edits.insert_one(edit_record)
    
    # Get updated invoice
    updated_invoice = await collection.find_one({"id": invoice_id}, {"_id": 0})
    
    return {
        "message": "Invoice updated successfully",
        "changes": changes_made,
        "inventory_adjustments": inventory_adjustments,
        "invoice": updated_invoice
    }

@api_router.get("/invoices/{invoice_id}/edit-history")
async def get_invoice_edit_history(invoice_id: str, user=Depends(get_current_user)):
    """Get edit history for an invoice."""
    history = await db.invoice_edits.find(
        {"invoice_id": invoice_id}, {"_id": 0}
    ).sort("edited_at", -1).to_list(100)
    return history

# =============================================================================
# SUPPLIER ROUTES
# =============================================================================
@api_router.get("/suppliers")
async def list_suppliers(user=Depends(get_current_user)):
    """List all suppliers with their details."""
    suppliers = await db.suppliers.find({"active": True}, {"_id": 0}).sort("name", 1).to_list(500)
    return suppliers

@api_router.post("/suppliers")
async def create_supplier(data: dict, user=Depends(get_current_user)):
    """Create a new supplier."""
    check_perm(user, "inventory", "adjust")
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Supplier name is required")
    existing = await db.suppliers.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}, "active": True})
    if existing:
        raise HTTPException(status_code=400, detail="Supplier already exists")
    supplier = {
        "id": new_id(),
        "name": name,
        "contact_person": data.get("contact_person", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "notes": data.get("notes", ""),
        "active": True,
        "created_at": now_iso(),
        "created_by": user["id"],
    }
    await db.suppliers.insert_one(supplier)
    del supplier["_id"]
    return supplier

@api_router.put("/suppliers/{supplier_id}")
async def update_supplier(supplier_id: str, data: dict, user=Depends(get_current_user)):
    """Update supplier details."""
    check_perm(user, "inventory", "adjust")
    allowed = ["name", "contact_person", "phone", "email", "address", "notes"]
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = now_iso()
    await db.suppliers.update_one({"id": supplier_id}, {"$set": update})
    return await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})

@api_router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: str, user=Depends(get_current_user)):
    """Soft delete a supplier."""
    check_perm(user, "inventory", "adjust")
    await db.suppliers.update_one({"id": supplier_id}, {"$set": {"active": False}})
    return {"message": "Supplier deleted"}

@api_router.get("/suppliers/search")
async def search_suppliers(q: str = "", user=Depends(get_current_user)):
    """Search suppliers by name, includes both from suppliers collection and PO vendors."""
    # Get from suppliers collection
    suppliers = await db.suppliers.find(
        {"name": {"$regex": q, "$options": "i"}, "active": True}, {"_id": 0}
    ).limit(10).to_list(10)
    supplier_names = [s["name"] for s in suppliers]
    
    # Get from PO vendors (legacy)
    po_vendors = await db.purchase_orders.distinct("vendor", {
        "vendor": {"$regex": q, "$options": "i"},
        "status": {"$ne": "cancelled"}
    })
    
    # Combine and deduplicate
    all_names = list(set(supplier_names + po_vendors))
    all_names.sort(key=lambda x: x.lower())
    
    # Return with details if available
    results = []
    for name in all_names[:15]:
        supplier = next((s for s in suppliers if s["name"].lower() == name.lower()), None)
        if supplier:
            results.append(supplier)
        else:
            results.append({"name": name, "id": None, "phone": "", "email": "", "address": ""})
    
    return results

# ==================== INVENTORY ROUTES ====================
@api_router.get("/inventory")
async def list_inventory(
    user=Depends(get_current_user),
    branch_id: Optional[str] = None,
    search: Optional[str] = None,
    low_stock: Optional[bool] = None,
    include_repacks: Optional[bool] = True,
    skip: int = 0,
    limit: int = 50
):
    # Base query - only get non-repack products for direct inventory
    base_match = {"active": True}
    if not include_repacks:
        base_match["is_repack"] = {"$ne": True}
    
    pipeline = [
        {"$match": base_match},
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
    
    # For repacks, calculate derived stock from parent
    enriched_items = []
    for item in items:
        if item.get("is_repack") and item.get("parent_id"):
            # Get parent stock
            parent_inv = await db.inventory.find_one(
                {"product_id": item["parent_id"], "branch_id": branch_id} if branch_id else {"product_id": item["parent_id"]},
                {"_id": 0}
            )
            parent_stock = parent_inv["quantity"] if parent_inv else 0
            units_per_parent = item.get("units_per_parent", 1)
            # Calculate derived stock
            item["total_stock"] = parent_stock * units_per_parent
            item["derived_from_parent"] = True
            item["parent_stock"] = parent_stock
            # Get parent name
            parent = await db.products.find_one({"id": item["parent_id"]}, {"_id": 0, "name": 1, "unit": 1})
            item["parent_name"] = parent["name"] if parent else ""
            item["parent_unit"] = parent["unit"] if parent else ""
        enriched_items.append(item)
    
    return {"items": enriched_items, "total": total}

@api_router.post("/inventory/adjust")
async def adjust_inventory(data: dict, user=Depends(get_current_user)):
    check_perm(user, "inventory", "adjust")
    product_id = data["product_id"]
    branch_id = data["branch_id"]
    quantity = float(data["quantity"])
    reason = data.get("reason", "Manual adjustment")
    
    # Check if this is a repack - cannot adjust repack inventory directly
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if product and product.get("is_repack"):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot adjust repack inventory directly. Adjust the parent product '{product.get('parent_id')}' instead. Repack stock is derived from parent."
        )
    
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
        "interest_rate": float(data.get("interest_rate", 0)),
        "grace_period": int(data.get("grace_period", 7)),
        "balance": 0.0, "active": True, "created_at": now_iso(),
    }
    await db.customers.insert_one(customer)
    del customer["_id"]
    return customer

@api_router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, data: dict, user=Depends(get_current_user)):
    check_perm(user, "customers", "edit")
    allowed = ["name", "phone", "email", "address", "price_scheme", "credit_limit", "interest_rate", "grace_period"]
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

        # For repacks: check and deduct from PARENT inventory only
        if product.get("is_repack") and product.get("parent_id"):
            units_per_parent = product.get("units_per_parent", 1)
            parent_deduction = qty / units_per_parent
            parent_inv = await db.inventory.find_one({"product_id": product["parent_id"], "branch_id": branch_id}, {"_id": 0})
            parent_stock = parent_inv["quantity"] if parent_inv else 0
            # Check if parent has enough stock (converted to repack units)
            available_repack_units = parent_stock * units_per_parent
            if available_repack_units < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product['name']}: have {available_repack_units:.0f}, need {qty:.0f}")
            # Deduct from parent only
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
            # Log movement against parent
            await log_movement(product["parent_id"], branch_id, "sale", -parent_deduction, "", "",
                              price * units_per_parent, user["id"], user.get("full_name", user["username"]),
                              f"Sold as repack: {product['name']} x {qty}")
        else:
            # Regular product: check and deduct from its own inventory
            inv = await db.inventory.find_one({"product_id": item["product_id"], "branch_id": branch_id}, {"_id": 0})
            current_stock = inv["quantity"] if inv else 0
            if current_stock < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product['name']}: have {current_stock}, need {qty}")
            await db.inventory.update_one(
                {"product_id": item["product_id"], "branch_id": branch_id},
                {"$inc": {"quantity": -qty}, "$set": {"updated_at": now_iso()}}
            )

        sale_items.append({
            "product_id": item["product_id"], "product_name": product["name"],
            "sku": product["sku"], "quantity": qty, "price": price,
            "total": line_total, "is_repack": product.get("is_repack", False),
            "parent_id": product.get("parent_id"),
            "units_per_parent": product.get("units_per_parent", 1) if product.get("is_repack") else None,
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
    # Update cashier wallet for cash sales (not credit)
    if data.get("payment_method") != "Credit" and sale["sale_type"] != "delivery":
        await update_cashier_wallet(branch_id, sale["total"], f"POS Sale {sale['sale_number']}")
    # Log to sequential sales log
    active_date = await get_active_date(branch_id)
    for si in sale_items:
        prod = await db.products.find_one({"id": si["product_id"]}, {"_id": 0, "category": 1})
        si["category"] = prod.get("category", "General") if prod else "General"
    await log_sale_items(branch_id, active_date, sale_items, sale["sale_number"],
                         data.get("customer_name", "Walk-in"),
                         data.get("payment_method", "Cash"),
                         user.get("full_name", user["username"]))
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

# Preset expense categories
EXPENSE_CATEGORIES = [
    "Utilities", "Rent", "Supplies", "Transportation", "Fuel/Gas",
    "Employee Advance", "Farm Expense", "Repairs & Maintenance",
    "Marketing", "Salaries & Wages", "Communication", "Insurance",
    "Professional Fees", "Taxes & Licenses", "Office Supplies",
    "Equipment", "Miscellaneous"
]

@api_router.get("/expenses/categories")
async def get_expense_categories(user=Depends(get_current_user)):
    """Get preset expense categories"""
    return EXPENSE_CATEGORIES

@api_router.post("/expenses")
async def create_expense(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
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
    # Deduct from cashier wallet
    ref_text = f"Expense: {data.get('category', 'General')} - {data.get('description', '')}"
    if data.get("reference_number"):
        ref_text += f" (Ref: {data['reference_number']})"
    await update_cashier_wallet(data["branch_id"], -float(data["amount"]), ref_text)
    del expense["_id"]
    return expense

@api_router.put("/expenses/{expense_id}")
async def update_expense(expense_id: str, data: dict, user=Depends(get_current_user)):
    """Update an existing expense"""
    check_perm(user, "accounting", "edit")
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
    
    # Adjust cashier wallet if amount changed
    if amount_diff != 0:
        await update_cashier_wallet(
            expense["branch_id"],
            -amount_diff,
            f"Expense adjusted: {expense.get('description', '')} ({'+' if amount_diff > 0 else ''}{amount_diff:.2f})"
        )
    
    return await db.expenses.find_one({"id": expense_id}, {"_id": 0})

@api_router.post("/expenses/farm")
async def create_farm_expense_with_invoice(data: dict, user=Depends(get_current_user)):
    """
    Create a farm expense and automatically generate an invoice for the linked customer.
    This is used when farm services (tilling, labor, gas) are provided to a customer.
    """
    check_perm(user, "accounting", "create")
    
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer is required for farm expense")
    
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    amount = float(data["amount"])
    branch_id = data["branch_id"]
    
    # Create the expense record
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
        "linked_invoice_id": None,  # Will be updated after invoice creation
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    # Deduct from cashier wallet (we paid for the farm expense)
    await update_cashier_wallet(branch_id, -amount, f"Farm Expense for {customer.get('name', '')}: {data.get('description', '')}")
    
    # Generate invoice number
    prefix_doc = await db.settings.find_one({"type": "invoice_prefixes"}, {"_id": 0})
    inv_prefix = prefix_doc.get("invoice", "INV") if prefix_doc else "INV"
    inv_count = await db.invoices.count_documents({}) + 1
    invoice_number = f"{inv_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{inv_count:04d}"
    
    # Create the invoice for the customer
    invoice = {
        "id": new_id(),
        "invoice_number": invoice_number,
        "branch_id": branch_id,
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "type": "Farm Service",
        "items": [{
            "product_id": None,
            "product_name": f"Farm Service: {data.get('description', 'Service')}",
            "description": data.get("notes", ""),
            "quantity": 1,
            "price": amount,
            "discount": 0,
            "total": amount,
        }],
        "subtotal": amount,
        "discount": 0,
        "total": amount,
        "amount_paid": 0,
        "balance": amount,
        "payment_method": "credit",
        "payment_status": "unpaid",
        "status": "confirmed",
        "terms": data.get("terms", ""),
        "due_date": data.get("due_date", ""),
        "notes": f"Auto-generated from Farm Expense. {data.get('notes', '')}",
        "farm_expense_id": expense["id"],
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(invoice)
    
    # Update expense with linked invoice
    expense["linked_invoice_id"] = invoice["id"]
    expense["linked_invoice_number"] = invoice_number
    await db.expenses.insert_one(expense)
    
    # Update customer balance
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": amount}})
    
    del expense["_id"]
    return {
        "expense": expense,
        "invoice": {
            "id": invoice["id"],
            "invoice_number": invoice_number,
            "customer_name": customer.get("name", ""),
            "total": amount,
        },
        "message": f"Farm expense recorded and Invoice {invoice_number} created for {customer.get('name', '')}"
    }

@api_router.post("/expenses/customer-cashout")
async def create_customer_cashout(data: dict, user=Depends(get_current_user)):
    """
    Create a customer cash out (loan/borrow) and automatically generate an invoice.
    This is used when customers borrow money from the business.
    """
    check_perm(user, "accounting", "create")
    
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer is required for cash out")
    
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    amount = float(data["amount"])
    branch_id = data["branch_id"]
    
    # Create the expense record
    expense = {
        "id": new_id(),
        "branch_id": branch_id,
        "category": "Customer Cash Out",
        "description": data.get("description", "Cash Out / Loan"),
        "notes": data.get("notes", ""),
        "amount": amount,
        "payment_method": data.get("payment_method", "Cash"),
        "reference_number": data.get("reference_number", ""),
        "date": data.get("date", now_iso()[:10]),
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "expense_type": "customer_cashout",
        "linked_invoice_id": None,
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    
    # Deduct from cashier wallet (cash goes out to customer)
    await update_cashier_wallet(branch_id, -amount, f"Customer Cash Out to {customer.get('name', '')}: {data.get('description', 'Loan')}")
    
    # Generate invoice number
    prefix_doc = await db.settings.find_one({"type": "invoice_prefixes"}, {"_id": 0})
    inv_prefix = prefix_doc.get("invoice", "INV") if prefix_doc else "INV"
    inv_count = await db.invoices.count_documents({}) + 1
    invoice_number = f"{inv_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{inv_count:04d}"
    
    # Create the invoice for the customer (they owe us this money)
    invoice = {
        "id": new_id(),
        "invoice_number": invoice_number,
        "branch_id": branch_id,
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "type": "Cash Out",
        "items": [{
            "product_id": None,
            "product_name": f"Cash Out / Loan: {data.get('description', 'Cash Advance')}",
            "description": data.get("notes", ""),
            "quantity": 1,
            "price": amount,
            "discount": 0,
            "total": amount,
        }],
        "subtotal": amount,
        "discount": 0,
        "total": amount,
        "amount_paid": 0,
        "balance": amount,
        "payment_method": "credit",
        "payment_status": "unpaid",
        "status": "confirmed",
        "terms": data.get("terms", ""),
        "due_date": data.get("due_date", ""),
        "notes": f"Customer Cash Out / Loan. {data.get('notes', '')}",
        "expense_type": "customer_cashout",
        "cashout_expense_id": expense["id"],
        "created_by": user["id"],
        "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(invoice)
    
    # Update expense with linked invoice
    expense["linked_invoice_id"] = invoice["id"]
    expense["linked_invoice_number"] = invoice_number
    await db.expenses.insert_one(expense)
    
    # Update customer balance (they owe us)
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": amount}})
    
    del expense["_id"]
    return {
        "expense": expense,
        "invoice": {
            "id": invoice["id"],
            "invoice_number": invoice_number,
            "customer_name": customer.get("name", ""),
            "total": amount,
        },
        "message": f"Cash out recorded and Invoice {invoice_number} created for {customer.get('name', '')}"
    }

@api_router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, user=Depends(get_current_user)):
    check_perm(user, "accounting", "delete")
    expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if expense:
        await update_cashier_wallet(expense["branch_id"], expense["amount"], f"Expense deleted: {expense.get('description', '')}")
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
    # Add to cashier wallet
    await update_cashier_wallet(rec.get("branch_id", ""), amount, f"Receivable payment from {rec.get('customer_name', '')}")
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
            # Update cashier wallet for cash sales
            if sale_doc.get("payment_method") != "Credit":
                await update_cashier_wallet(branch_id, sale_doc.get("total", 0), f"Synced POS Sale {sale_id[:8]}")
            # Log to sales_log
            active_date = await get_active_date(branch_id)
            sale_items_for_log = sale_doc.get("items", [])
            for si in sale_items_for_log:
                if si.get("product_id"):
                    prod = await db.products.find_one({"id": si["product_id"]}, {"_id": 0, "category": 1})
                    si["category"] = prod.get("category", "General") if prod else "General"
            await log_sale_items(branch_id, active_date, sale_items_for_log,
                                 sale_doc.get("sale_number", sale_id[:8]),
                                 sale_doc.get("customer_name", "Walk-in"),
                                 sale_doc.get("payment_method", "Cash"),
                                 sale_doc.get("cashier_name", "System"))
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

    # Receivables - combine from both invoices AND legacy receivables collection
    # From invoices (new unified system)
    invoice_receivables_pipeline = [
        {"$match": {"status": {"$nin": ["paid", "voided"]}, "balance": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]
    inv_rec_result = await db.invoices.aggregate(invoice_receivables_pipeline).to_list(1)
    invoice_receivables = inv_rec_result[0]["total"] if inv_rec_result else 0
    
    # From legacy receivables collection
    receivables_pipeline = [{"$match": {"status": {"$ne": "paid"}}}, {"$group": {"_id": None, "total": {"$sum": "$balance"}}}]
    rec_result = await db.receivables.aggregate(receivables_pipeline).to_list(1)
    legacy_receivables = rec_result[0]["total"] if rec_result else 0
    
    total_receivables = invoice_receivables + legacy_receivables

    # Expenses today
    today_expenses = await db.expenses.find({"date": today}, {"_id": 0}).to_list(1000)
    today_expense_total = sum(e.get("amount", 0) for e in today_expenses)

    # Recent sales - combine from both sales and invoices
    recent_sales_raw = await db.sales.find(sales_query, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    recent_invoices_raw = await db.invoices.find(
        {"status": {"$ne": "voided"}, "branch_id": branch_id} if branch_id else {"status": {"$ne": "voided"}},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    # Normalize invoice format to match sales
    for inv in recent_invoices_raw:
        inv["sale_number"] = inv.get("invoice_number", "")
        inv["total"] = inv.get("grand_total", 0)
    
    # Merge and sort by created_at
    all_recent = recent_sales_raw + recent_invoices_raw
    all_recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    recent_sales = all_recent[:5]

    # Top products (from both sales and invoices)
    top_products_pipeline = [
        {"$match": {"status": "completed"}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "total_qty": {"$sum": "$items.quantity"}, "total_revenue": {"$sum": "$items.total"}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products_sales = await db.sales.aggregate(top_products_pipeline).to_list(5)
    
    # Also get from invoices
    top_products_invoices_pipeline = [
        {"$match": {"status": {"$ne": "voided"}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "total_qty": {"$sum": "$items.quantity"}, "total_revenue": {"$sum": "$items.total"}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    top_products_inv = await db.invoices.aggregate(top_products_invoices_pipeline).to_list(5)
    
    # Merge top products
    product_totals = {}
    for p in top_products_sales + top_products_inv:
        name = p["_id"]
        if name not in product_totals:
            product_totals[name] = {"qty": 0, "revenue": 0}
        product_totals[name]["qty"] += p.get("total_qty", 0)
        product_totals[name]["revenue"] += p.get("total_revenue", 0)
    
    top_products = sorted(
        [{"name": k, "quantity": v["qty"], "revenue": v["revenue"]} for k, v in product_totals.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:5]

    branches = await db.branches.find({"active": True}, {"_id": 0}).to_list(100)

    return {
        "today_revenue": today_revenue, "today_sales_count": today_count,
        "today_expenses": today_expense_total, "total_products": total_products,
        "low_stock_count": low_stock_count, "total_customers": total_customers,
        "total_receivables": total_receivables, "recent_sales": recent_sales,
        "top_products": top_products,
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

@api_router.get("/permissions/modules")
async def get_permission_modules(user=Depends(get_current_user)):
    """Get all available permission modules and their actions."""
    return PERMISSION_MODULES

@api_router.get("/permissions/presets")
async def get_permission_presets(user=Depends(get_current_user)):
    """Get all preset role templates."""
    return ROLE_PRESETS

@api_router.get("/permissions/presets/{preset_key}")
async def get_preset_permissions(preset_key: str, user=Depends(get_current_user)):
    """Get permissions for a specific preset role."""
    if preset_key not in ROLE_PRESETS:
        raise HTTPException(status_code=404, detail="Preset not found")
    return ROLE_PRESETS[preset_key]

@api_router.post("/users/{user_id}/apply-preset")
async def apply_permission_preset(user_id: str, data: dict, user=Depends(get_current_user)):
    """Apply a preset role's permissions to a user."""
    check_perm(user, "settings", "manage_permissions")
    
    preset_key = data.get("preset")
    if preset_key not in ROLE_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid preset")
    
    permissions = ROLE_PRESETS[preset_key]["permissions"]
    await db.users.update_one(
        {"id": user_id}, 
        {"$set": {
            "permissions": permissions, 
            "role": preset_key,
            "permission_preset": preset_key,
            "updated_at": now_iso()
        }}
    )
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

@api_router.put("/users/{user_id}/permissions/module/{module}")
async def update_user_module_permissions(user_id: str, module: str, data: dict, user=Depends(get_current_user)):
    """Update permissions for a specific module for a user."""
    check_perm(user, "settings", "manage_permissions")
    
    if module not in PERMISSION_MODULES:
        raise HTTPException(status_code=400, detail="Invalid module")
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get current permissions or initialize
    permissions = target_user.get("permissions", {})
    permissions[module] = data.get("actions", {})
    
    # Mark as custom (no longer following a preset)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "permissions": permissions,
            "permission_preset": "custom",
            "updated_at": now_iso()
        }}
    )
    
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

@api_router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str, user=Depends(get_current_user)):
    """Get detailed permissions for a specific user."""
    # Allow users to view their own permissions
    if user_id != user["id"]:
        check_perm(user, "settings", "manage_users")
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user_id,
        "username": target_user.get("username"),
        "role": target_user.get("role"),
        "permission_preset": target_user.get("permission_preset", target_user.get("role")),
        "permissions": target_user.get("permissions", {}),
        "branch_id": target_user.get("branch_id"),
    }

@api_router.put("/users/{user_id}/permissions")
async def update_user_permissions(user_id: str, data: dict, user=Depends(get_current_user)):
    """Update all permissions for a user at once."""
    check_perm(user, "settings", "manage_permissions")
    
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    permissions = data.get("permissions", {})
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "permissions": permissions,
            "permission_preset": "custom",
            "updated_at": now_iso()
        }}
    )
    
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

# ==================== DAILY OPERATIONS ====================
@api_router.get("/daily-log")
async def get_daily_log(date: str, branch_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {"date": date}
    if branch_id: query["branch_id"] = branch_id
    entries = await db.sales_log.find(query, {"_id": 0}).sort("sequence", 1).to_list(10000)
    return {"entries": entries, "total": len(entries), "date": date}

@api_router.get("/daily-report")
async def get_daily_report(date: str, branch_id: Optional[str] = None, user=Depends(get_current_user)):
    check_perm(user, "reports", "view")
    log_query = {"date": date}
    if branch_id: log_query["branch_id"] = branch_id
    # Sales by category
    cat_pipeline = [
        {"$match": log_query},
        {"$group": {"_id": "$category", "total": {"$sum": "$line_total"}, "count": {"$sum": "$quantity"}}}
    ]
    cat_results = await db.sales_log.aggregate(cat_pipeline).to_list(100)
    sales_by_category = {r["_id"] or "Uncategorized": {"total": r["total"], "count": r["count"]} for r in cat_results}
    total_revenue = sum(r["total"] for r in cat_results)
    # COGS - get cost prices for all sold products
    log_entries = await db.sales_log.find(log_query, {"_id": 0}).to_list(10000)
    total_cogs = 0
    for entry in log_entries:
        if entry.get("product_id"):
            prod = await db.products.find_one({"id": entry["product_id"]}, {"_id": 0, "cost_price": 1})
            if prod:
                total_cogs += (prod.get("cost_price", 0) * entry.get("quantity", 0))
    total_cogs = round(total_cogs, 2)
    # Expenses
    exp_query = {"date": date}
    if branch_id: exp_query["branch_id"] = branch_id
    expenses = await db.expenses.find(exp_query, {"_id": 0}).to_list(500)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    # Credit collections: only payments on OLD invoices (not today's new sales)
    pay_pipeline = [
        {"$match": {"status": {"$ne": "voided"}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.date": date}},
    ]
    if branch_id: pay_pipeline[0]["$match"]["branch_id"] = branch_id
    pay_pipeline.append({"$project": {"_id": 0, "invoice_number": 1, "customer_name": 1, "order_date": 1, "payment": "$payments"}})
    all_payments_today = await db.invoices.aggregate(pay_pipeline).to_list(500)
    # Only count payments on older invoices as credit collections (NOT same-day sales)
    credit_collections = [p for p in all_payments_today if p.get("order_date") != date]
    total_credit_collections = sum(p["payment"]["amount"] for p in credit_collections)
    # Total cash from all invoice payments (for cash flow)
    total_cash_from_invoices = sum(p["payment"]["amount"] for p in all_payments_today)
    gross_profit = round(total_revenue - total_cogs, 2)
    net_profit = round(gross_profit - total_expenses, 2)
    # Get real-time cashier wallet balance
    cashier_wallet = await db.fund_wallets.find_one(
        {"branch_id": branch_id, "type": "cashier", "active": True} if branch_id else {"type": "cashier", "active": True}, {"_id": 0})
    cashier_balance = cashier_wallet["balance"] if cashier_wallet else 0
    return {
        "date": date, "new_sales_today": total_revenue, "total_cogs": total_cogs,
        "gross_profit": gross_profit, "total_expenses": total_expenses, "net_profit": net_profit,
        "sales_by_category": sales_by_category, "expenses": expenses,
        "credit_collections": credit_collections, "total_credit_collections": total_credit_collections,
        "total_cash_from_invoices": total_cash_from_invoices,
        "cashier_wallet_balance": round(cashier_balance, 2),
        "transaction_count": len(log_entries),
    }

@api_router.get("/daily-close/{date}")
async def get_daily_close(date: str, branch_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {"date": date}
    if branch_id: query["branch_id"] = branch_id
    closing = await db.daily_closings.find_one(query, {"_id": 0})
    return closing or {"status": "open", "date": date}

@api_router.post("/daily-close")
async def close_day(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    date = data["date"]
    branch_id = data["branch_id"]
    # Check if already closed
    existing = await db.daily_closings.find_one({"date": date, "branch_id": branch_id, "status": "closed"}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Day already closed")
    # Get report data
    report_query = {"date": date, "branch_id": branch_id}
    log_entries = await db.sales_log.find(report_query, {"_id": 0}).to_list(10000)
    new_sales_today = sum(e.get("line_total", 0) for e in log_entries)
    # Sales by category
    cat_map = {}
    for e in log_entries:
        cat = e.get("category", "Uncategorized")
        cat_map[cat] = cat_map.get(cat, 0) + e.get("line_total", 0)
    # Expenses
    expenses = await db.expenses.find(report_query, {"_id": 0}).to_list(500)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    employee_advances = [e for e in expenses if e.get("category") == "Employee Cash Advance"]
    farm_expenses = [e for e in expenses if e.get("category") == "Farm Expense"]
    other_expenses = [e for e in expenses if e.get("category") not in ("Employee Cash Advance", "Farm Expense")]
    # Credit collections (payments on existing receivables) - NOT new revenue
    # Split into: payments on TODAY's invoices (cash from new sales) vs OLD invoices (credit collections)
    all_payments_pipeline = [
        {"$match": {"branch_id": branch_id, "status": {"$ne": "voided"}}},
        {"$unwind": "$payments"}, {"$match": {"payments.date": date}},
        {"$project": {"_id": 0, "invoice_number": 1, "customer_name": 1, "balance": 1,
                       "interest_accrued": 1, "order_date": 1, "payment": "$payments"}}
    ]
    all_payments_today = await db.invoices.aggregate(all_payments_pipeline).to_list(500)
    # Separate: credit collections = payments on invoices NOT created today
    credit_collections = [p for p in all_payments_today if p.get("order_date") != date]
    total_credit_collections = sum(p["payment"]["amount"] for p in credit_collections)
    # Cash from invoice payments today (includes initial payments on new invoices + old collections)
    total_invoice_cash = sum(p["payment"]["amount"] for p in all_payments_today)
    # POS cash sales (direct POS sales not in invoices)
    pos_cash_sales = await db.sales.find(
        {"branch_id": branch_id, "created_at": {"$regex": f"^{date}"}, "status": "completed",
         "payment_method": {"$ne": "Credit"}}, {"_id": 0, "total": 1}
    ).to_list(10000)
    total_pos_cash = sum(s.get("total", 0) for s in pos_cash_sales)
    # Total cash received = invoice payments + POS cash (no double-counting)
    total_cash_received = round(total_invoice_cash + total_pos_cash, 2)
    # Fund balances (real-time from wallet updates)
    wallets = await db.fund_wallets.find({"branch_id": branch_id, "active": True}, {"_id": 0}).to_list(10)
    safe_wallet = next((w for w in wallets if w["type"] == "safe"), None)
    bank_wallet = next((w for w in wallets if w["type"] == "bank"), None)
    cashier_wallet = next((w for w in wallets if w["type"] == "cashier"), None)
    safe_balance = 0
    if safe_wallet:
        lots = await db.safe_lots.find({"wallet_id": safe_wallet["id"], "remaining_amount": {"$gt": 0}}, {"_id": 0}).to_list(500)
        safe_balance = sum(l["remaining_amount"] for l in lots)
    bank_balance = bank_wallet["balance"] if bank_wallet else 0
    # Expected cash = cashier wallet balance (real-time, already updated by all transactions)
    expected_cash = round(cashier_wallet["balance"], 2) if cashier_wallet else 0
    actual_cash = float(data.get("actual_cash", 0))
    bank_checks = float(data.get("bank_checks", 0))
    other_payment_forms = float(data.get("other_payment_forms", 0))
    cash_to_drawer = float(data.get("cash_to_drawer", 0))
    cash_to_safe = float(data.get("cash_to_safe", 0))
    cash_deposited_today = cash_to_safe
    extra_cash = round(actual_cash - (expected_cash - bank_checks - other_payment_forms), 2)
    closing = {
        "id": new_id(), "branch_id": branch_id, "date": date, "status": "closed",
        "closed_by": user["id"], "closed_by_name": user.get("full_name", user["username"]),
        "closed_at": now_iso(),
        "safe_balance": safe_balance, "bank_balance": bank_balance,
        "cash_deposited_to_safe": cash_deposited_today,
        "new_sales_today": new_sales_today, "sales_by_category": cat_map,
        "credit_collections": [{"invoice": p["invoice_number"], "customer": p["customer_name"],
                               "balance": p.get("balance", 0), "interest": p.get("interest_accrued", 0),
                               "principal_paid": p["payment"].get("applied_to_principal", 0),
                               "interest_paid": p["payment"].get("applied_to_interest", 0),
                               "total_paid": p["payment"]["amount"]} for p in credit_collections],
        "total_credit_collections": total_credit_collections,
        "total_cash_received": total_cash_received,
        "expenses": [{"category": e["category"], "description": e.get("description", ""),
                      "amount": e["amount"]} for e in expenses],
        "employee_advances": [{"description": e.get("description", ""), "amount": e["amount"]} for e in employee_advances],
        "farm_expenses": [{"description": e.get("description", ""), "amount": e["amount"]} for e in farm_expenses],
        "total_expenses": total_expenses,
        "expected_cash": expected_cash, "actual_cash": actual_cash,
        "bank_checks": bank_checks, "other_payment_forms": other_payment_forms,
        "cash_to_drawer": cash_to_drawer, "cash_to_safe": cash_to_safe,
        "extra_cash": extra_cash,
    }
    await db.daily_closings.insert_one(closing)
    # Update cashier wallet balance
    if cashier_wallet:
        await db.fund_wallets.update_one({"id": cashier_wallet["id"]}, {"$set": {"balance": cash_to_drawer}})
    # Deposit to safe
    if cash_to_safe > 0 and safe_wallet:
        await db.safe_lots.insert_one({
            "id": new_id(), "branch_id": branch_id, "wallet_id": safe_wallet["id"],
            "date_received": date, "original_amount": cash_to_safe, "remaining_amount": cash_to_safe,
            "source_reference": f"Daily close deposit - {date}",
            "created_by": user["id"], "created_at": now_iso()
        })
    del closing["_id"]
    return closing

# ==================== EMPLOYEES ====================
@api_router.get("/employees")
async def list_employees(user=Depends(get_current_user), branch_id: Optional[str] = None):
    query = {"active": True}
    if branch_id: query["branch_id"] = branch_id
    employees = await db.employees.find(query, {"_id": 0}).to_list(200)
    # Get monthly advances for each
    now = datetime.now(timezone.utc)
    month_start = now.strftime("%Y-%m-01")
    for emp in employees:
        advances = await db.expenses.find({
            "category": "Employee Cash Advance",
            "employee_id": emp["id"],
            "date": {"$gte": month_start}
        }, {"_id": 0}).to_list(100)
        emp["monthly_advance_total"] = sum(a.get("amount", 0) for a in advances)
    return employees

@api_router.post("/employees")
async def create_employee(data: dict, user=Depends(get_current_user)):
    emp = {
        "id": new_id(), "name": data["name"], "branch_id": data.get("branch_id", ""),
        "position": data.get("position", ""), "phone": data.get("phone", ""),
        "opening_balance": float(data.get("opening_balance", 0)),
        "active": True, "created_at": now_iso(),
    }
    await db.employees.insert_one(emp)
    del emp["_id"]
    return emp

@api_router.put("/employees/{emp_id}")
async def update_employee(emp_id: str, data: dict, user=Depends(get_current_user)):
    allowed = ["name", "position", "phone", "branch_id", "opening_balance", "active"]
    update = {k: v for k, v in data.items() if k in allowed}
    await db.employees.update_one({"id": emp_id}, {"$set": update})
    return await db.employees.find_one({"id": emp_id}, {"_id": 0})

@api_router.post("/expenses/farm")
async def create_farm_expense(data: dict, user=Depends(get_current_user)):
    """Create farm expense and auto-add to customer's receivable"""
    check_perm(user, "accounting", "create")
    customer_id = data.get("customer_id")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0}) if customer_id else None
    tag = data.get("tag", "Farm Expense")
    expense = {
        "id": new_id(), "branch_id": data.get("branch_id", ""), "category": "Farm Expense",
        "description": f"Farm Cash Out - {tag} ({customer['name'] if customer else 'Unknown'})",
        "amount": float(data["amount"]), "date": data.get("date", now_iso()[:10]),
        "customer_id": customer_id, "tag": tag,
        "created_by": user["id"], "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)
    # Create receivable for the customer
    if customer_id:
        settings = await db.settings.find_one({"key": "invoice_prefixes"}, {"_id": 0})
        prefix = settings.get("value", {}).get("sales_invoice", "SI") if settings else "SI"
        count = await db.invoices.count_documents({"prefix": prefix})
        inv_number = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(count + 1).zfill(4)}"
        farm_invoice = {
            "id": new_id(), "invoice_number": inv_number, "prefix": prefix,
            "customer_id": customer_id, "customer_name": customer["name"] if customer else "",
            "customer_contact": "", "customer_phone": "", "customer_address": "",
            "terms": "Net 30", "terms_days": 30, "customer_po": "",
            "sales_rep_id": "", "sales_rep_name": "",
            "branch_id": data.get("branch_id", ""),
            "order_date": data.get("date", now_iso()[:10]),
            "invoice_date": data.get("date", now_iso()[:10]),
            "due_date": data.get("date", now_iso()[:10]),
            "items": [{"product_id": "", "product_name": f"Farm Cash Out - {tag}",
                        "description": data.get("description", ""), "quantity": 1,
                        "rate": float(data["amount"]), "discount_type": "amount",
                        "discount_value": 0, "discount_amount": 0,
                        "total": float(data["amount"]), "is_repack": False}],
            "subtotal": float(data["amount"]), "freight": 0, "overall_discount": 0,
            "grand_total": float(data["amount"]), "amount_paid": 0,
            "balance": float(data["amount"]),
            "interest_rate": 0, "interest_accrued": 0, "penalties": 0,
            "last_interest_date": None, "sale_type": "farm_expense",
            "status": "open", "payments": [],
            "cashier_id": user["id"], "cashier_name": user.get("full_name", user["username"]),
            "created_at": now_iso(),
        }
        await db.invoices.insert_one(farm_invoice)
        await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": float(data["amount"])}})
    # Deduct from cashier wallet
    await update_cashier_wallet(data.get("branch_id", ""), -float(data["amount"]), f"Farm Expense: {tag}")
    del expense["_id"]
    return expense

@api_router.post("/expenses/employee-advance")
async def create_employee_advance(data: dict, user=Depends(get_current_user)):
    check_perm(user, "accounting", "create")
    emp = await db.employees.find_one({"id": data["employee_id"]}, {"_id": 0}) if data.get("employee_id") else None
    expense = {
        "id": new_id(), "branch_id": data.get("branch_id", ""), "category": "Employee Cash Advance",
        "description": f"Cash Advance - {emp['name'] if emp else data.get('employee_name', 'Unknown')}",
        "amount": float(data["amount"]), "date": data.get("date", now_iso()[:10]),
        "employee_id": data.get("employee_id", ""),
        "employee_name": emp["name"] if emp else data.get("employee_name", ""),
        "created_by": user["id"], "created_by_name": user.get("full_name", user["username"]),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(expense)
    # Deduct from cashier wallet
    await update_cashier_wallet(data.get("branch_id", ""), -float(data["amount"]), f"Employee Advance: {emp['name'] if emp else 'Unknown'}")
    del expense["_id"]
    return expense

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
