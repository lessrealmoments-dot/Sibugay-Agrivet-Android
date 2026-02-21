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

# APScheduler for daily backup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import from local modules
from config import db, client, logger, JWT_SECRET
from utils import hash_password, now_iso, new_id
from models import DEFAULT_PERMISSIONS

_scheduler = AsyncIOScheduler()
# Import all route modules
from routes import (
    auth_router, branches_router, users_router, products_router,
    customers_router, inventory_router, price_schemes_router, invoices_router,
    sales_router, purchase_orders_router, dashboard_router, accounting_router,
    daily_ops_router, suppliers_router, sync_router, employees_router,
    settings_router, count_sheets_router, setup_router, branch_prices_router,
    import_router, notifications_router, branch_transfers_router, reports_router,
)
from routes.backups import router as backups_router

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

# Branch-specific Pricing
api_router.include_router(branch_prices_router)

# Branch Transfers (inter-branch supply orders)
api_router.include_router(branch_transfers_router)

# Import Center
api_router.include_router(import_router)

# Notifications
api_router.include_router(notifications_router)

# Setup Wizard (no auth required)
api_router.include_router(setup_router)

# Backups
api_router.include_router(backups_router)


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================
@app.on_event("startup")
async def startup():
    """Initialize database indexes. User/branch creation moved to setup wizard."""
    # ── Security check ────────────────────────────────────────────────────────
    if len(JWT_SECRET) < 32:
        logger.warning(
            "⚠️  JWT_SECRET is too short (%d chars). "
            "Generate a strong key with: openssl rand -hex 32",
            len(JWT_SECRET)
        )

    # Check if setup is needed (no auto-creation of users)
    user_count = await db.users.count_documents({})
    if user_count == 0:
        logger.info("No users found - system needs setup via /api/setup/initialize")
    
    # Create default price schemes if none exist
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
    # Text index for fast product search (name + sku + barcode)
    try:
        await db.products.create_index(
            [("name", "text"), ("sku", "text"), ("barcode", "text")],
            name="product_text_search", default_language="none"
        )
    except Exception:
        pass  # Index may already exist with different options
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
    await db.branch_prices.create_index([("product_id", 1), ("branch_id", 1)], unique=True)
    await db.notifications.create_index("created_at")
    await db.notifications.create_index("target_user_ids")
    logger.info("Database indexes created")

    # ── Daily backup scheduler ────────────────────────────────────────────────
    from services.backup_service import create_backup, delete_old_local_backups
    db_name = os.environ.get("DB_NAME", "agripos_production")
    backup_hour = int(os.environ.get("BACKUP_SCHEDULE_HOUR", "1"))
    retain_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))

    async def _daily_backup_job():
        logger.info("Running scheduled daily backup...")
        result = await create_backup(db_name)
        delete_old_local_backups(db_name, retain_days)
        if result["success"]:
            logger.info("Scheduled backup complete: %s (%.2f MB)", result["filename"], result["size_mb"])
        else:
            logger.error("Scheduled backup FAILED: %s", result.get("error"))

    _scheduler.add_job(
        _daily_backup_job,
        CronTrigger(hour=backup_hour, minute=0),
        id="daily_backup",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Backup scheduler started — daily at %02d:00", backup_hour)


@app.on_event("shutdown")
async def shutdown_db_client():
    """Close database connection on shutdown."""
    _scheduler.shutdown(wait=False)
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
