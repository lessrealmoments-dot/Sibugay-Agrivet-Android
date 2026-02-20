"""
================================================================================
AgriPOS API Server - Modular Architecture
================================================================================
Multi-branch Inventory, POS & Accounting System for Agricultural Retail

This is the production entry point that imports all modular routes from /routes.

Version: 3.0 (Dec 2025) - Complete Modular Refactor
================================================================================
"""

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timezone

# Import from local modules
from config import db, client, logger, JWT_SECRET
from utils import hash_password, now_iso, new_id
from models import DEFAULT_PERMISSIONS

# Import all route modules
from routes import (
    auth_router,
    branches_router,
    users_router,
    products_router,
    customers_router,
    inventory_router,
    price_schemes_router,
    invoices_router,
    sales_router,
    purchase_orders_router,
    dashboard_router,
    accounting_router,
    daily_ops_router,
    suppliers_router,
    sync_router,
    employees_router,
    settings_router,
    count_sheets_router,
    setup_router,
)

# =============================================================================
# APP SETUP
# =============================================================================
app = FastAPI(
    title="AgriPOS API",
    description="Multi-branch Inventory, POS & Accounting System",
    version="3.0"
)

# Main API router
api_router = APIRouter(prefix="/api")

# =============================================================================
# INCLUDE ALL MODULAR ROUTES
# =============================================================================
# Auth & Users
api_router.include_router(auth_router)
api_router.include_router(users_router)

# Core Business
api_router.include_router(branches_router)
api_router.include_router(products_router)
api_router.include_router(customers_router)
api_router.include_router(inventory_router)
api_router.include_router(price_schemes_router)

# Sales & Invoicing
api_router.include_router(invoices_router)
api_router.include_router(sales_router)
api_router.include_router(purchase_orders_router)

# Accounting & Finance
api_router.include_router(accounting_router)

# Operations
api_router.include_router(daily_ops_router)
api_router.include_router(suppliers_router)
api_router.include_router(employees_router)

# System
api_router.include_router(sync_router)
api_router.include_router(settings_router)
api_router.include_router(dashboard_router)

# Audit / Count Sheets
api_router.include_router(count_sheets_router)

# Setup Wizard (no auth required)
api_router.include_router(setup_router)


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================
@app.on_event("startup")
async def startup():
    """Initialize database with default data and indexes."""
    # Create default admin user
    admin = await db.users.find_one({"username": "admin"}, {"_id": 0})
    if not admin:
        admin_user = {
            "id": new_id(),
            "username": "admin",
            "full_name": "Administrator",
            "email": "admin@agripos.com",
            "password_hash": hash_password("admin123"),
            "role": "admin",
            "branch_id": None,
            "permissions": DEFAULT_PERMISSIONS["admin"],
            "active": True,
            "created_at": now_iso(),
        }
        await db.users.insert_one(admin_user)
        logger.info("Default admin user created (admin/admin123)")

    # Create default branch
    branch = await db.branches.find_one({"active": True}, {"_id": 0})
    if not branch:
        main_branch = {
            "id": new_id(),
            "name": "Main Branch",
            "address": "",
            "phone": "",
            "active": True,
            "created_at": now_iso()
        }
        await db.branches.insert_one(main_branch)
        logger.info("Default branch created")

    # Create default price schemes
    schemes = await db.price_schemes.count_documents({})
    if schemes == 0:
        default_schemes = [
            {
                "id": new_id(),
                "name": "Retail",
                "key": "retail",
                "description": "Standard retail price",
                "calculation_method": "percent_plus_capital",
                "calculation_value": 30,
                "base_scheme": "cost_price",
                "active": True,
                "created_at": now_iso()
            },
            {
                "id": new_id(),
                "name": "Wholesale",
                "key": "wholesale",
                "description": "Wholesale / bulk price",
                "calculation_method": "percent_plus_capital",
                "calculation_value": 15,
                "base_scheme": "cost_price",
                "active": True,
                "created_at": now_iso()
            },
            {
                "id": new_id(),
                "name": "Special",
                "key": "special",
                "description": "Special customer price",
                "calculation_method": "percent_minus_retail",
                "calculation_value": 10,
                "base_scheme": "retail",
                "active": True,
                "created_at": now_iso()
            },
            {
                "id": new_id(),
                "name": "Government",
                "key": "government",
                "description": "Government rate",
                "calculation_method": "fixed",
                "calculation_value": 0,
                "base_scheme": "cost_price",
                "active": True,
                "created_at": now_iso()
            },
        ]
        await db.price_schemes.insert_many(default_schemes)
        logger.info("Default price schemes created")

    # Create default cashier user for testing
    cashier = await db.users.find_one({"username": "cashier"}, {"_id": 0})
    if not cashier:
        # Get first branch ID
        first_branch = await db.branches.find_one({"active": True}, {"_id": 0, "id": 1})
        cashier_user = {
            "id": new_id(),
            "username": "cashier",
            "full_name": "Test Cashier",
            "email": "cashier@agripos.com",
            "password_hash": hash_password("password"),
            "role": "cashier",
            "branch_id": first_branch["id"] if first_branch else None,
            "permissions": DEFAULT_PERMISSIONS["cashier"],
            "active": True,
            "created_at": now_iso(),
        }
        await db.users.insert_one(cashier_user)
        logger.info("Default cashier user created (cashier/password)")

    # Create indexes
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("sku")
    await db.products.create_index("id", unique=True)
    await db.products.create_index("parent_id")
    await db.inventory.create_index([("product_id", 1), ("branch_id", 1)], unique=True)
    await db.sales.create_index("branch_id")
    await db.sales.create_index("created_at")
    await db.invoices.create_index("branch_id")
    await db.invoices.create_index("customer_id")
    await db.invoices.create_index("created_at")
    await db.customers.create_index("id", unique=True)
    await db.customers.create_index("branch_id")
    await db.branches.create_index("id", unique=True)
    await db.movements.create_index([("product_id", 1), ("branch_id", 1)])
    await db.movements.create_index("created_at")
    logger.info("Database indexes created")


@app.on_event("shutdown")
async def shutdown_db_client():
    """Close database connection on shutdown."""
    client.close()


# =============================================================================
# INCLUDE ROUTER & MIDDLEWARE
# =============================================================================
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"]
)


# =============================================================================
# HEALTH CHECK
# =============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
