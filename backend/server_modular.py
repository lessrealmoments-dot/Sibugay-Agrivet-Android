"""
================================================================================
AgriPOS API Server (Modular Architecture)
================================================================================
Multi-branch Inventory, POS & Accounting System for Agricultural Retail

This is the refactored modular version that imports from:
- config.py: Database and environment configuration
- utils/: Authentication, helpers, and common utilities
- models/: Permission definitions and data models
- routes/: Separated route modules

Version: 3.0 (Feb 2026) - Modular Refactor
================================================================================
"""

from fastapi import FastAPI, APIRouter, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

# Import from local modules
from config import db, client, logger, MONGO_URL, DB_NAME, JWT_SECRET
from utils import (
    hash_password, verify_password, create_token, 
    get_current_user, check_perm, has_perm,
    now_iso, new_id, log_movement, log_sale_items,
    get_active_date, update_cashier_wallet
)
from models import PERMISSION_MODULES, ROLE_PRESETS, DEFAULT_PERMISSIONS

# Import route modules
from routes import (
    auth_router,
    branches_router,
    users_router,
    products_router,
    customers_router,
    inventory_router,
    price_schemes_router,
)

# =============================================================================
# APP SETUP
# =============================================================================
app = FastAPI(
    title="AgriPOS API",
    description="Multi-branch Inventory, POS & Accounting System",
    version="3.0"
)

# Main API router (remaining complex routes that need gradual extraction)
api_router = APIRouter(prefix="/api")

# =============================================================================
# INCLUDE MODULAR ROUTES
# =============================================================================
api_router.include_router(auth_router)
api_router.include_router(branches_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(customers_router)
api_router.include_router(inventory_router)
api_router.include_router(price_schemes_router)

# =============================================================================
# REMAINING ROUTES (to be extracted in future phases)
# These routes are more complex and interdependent, requiring careful extraction
# =============================================================================

# TODO: Extract to routes/invoices.py
# TODO: Extract to routes/sales.py
# TODO: Extract to routes/purchase_orders.py
# TODO: Extract to routes/accounting.py
# TODO: Extract to routes/fund_management.py
# TODO: Extract to routes/dashboard.py
# TODO: Extract to routes/daily_operations.py
# TODO: Extract to routes/employees.py
# TODO: Extract to routes/sync.py

# For now, these remain in the original server.py
# This file serves as the target architecture template

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
