"""
================================================================================
AgriPOS API Server - Modular Architecture
================================================================================
Multi-branch Inventory, POS & Accounting System for Agricultural Retail

This is the production entry point that imports all modular routes from /routes.

Version: 3.0 (Dec 2025) - Complete Modular Refactor
================================================================================
"""

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timezone, timedelta

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
    returns_router, audit_router, uploads_router, verify_router,
    organizations_router, superadmin_router, admin_auth_router,
)
from routes.backups import router as backups_router
from routes.internal_invoices import router as internal_invoices_router

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

# Reports
api_router.include_router(reports_router)

# Returns & Refunds
api_router.include_router(returns_router)

# Audit Center
api_router.include_router(audit_router)

# Receipt Uploads
api_router.include_router(uploads_router)

# Transaction Verification
api_router.include_router(verify_router)

# Organizations & Subscriptions
api_router.include_router(organizations_router)

# Super Admin (platform management)
api_router.include_router(superadmin_router)

# Internal Invoices (branch-to-branch billing)
api_router.include_router(internal_invoices_router)

# Admin Portal Auth (separate login)
api_router.include_router(admin_auth_router)

# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================
@app.on_event("startup")
async def startup():
    """Initialize database indexes and run multi-tenancy migration."""
    from config import _raw_db, TENANT_COLLECTIONS

    # ── Security check ────────────────────────────────────────────────────────
    if len(JWT_SECRET) < 32:
        logger.warning(
            "⚠️  JWT_SECRET is too short (%d chars). "
            "Generate a strong key with: openssl rand -hex 32",
            len(JWT_SECRET)
        )

    # ── Multi-tenancy migration ───────────────────────────────────────────────
    # If existing data has no organization_id, migrate it to a default org
    default_org = await _raw_db.organizations.find_one({"is_default": True}, {"_id": 0})
    if not default_org:
        user_count = await _raw_db.users.count_documents({"is_super_admin": {"$ne": True}})
        if user_count > 0:
            default_org_id = new_id()
            default_org_doc = {
                "id": default_org_id,
                "name": "AgriBooks (Default)",
                "owner_email": "",
                "plan": "pro",
                "subscription_status": "active",
                "trial_ends_at": None,
                "max_branches": 999,
                "max_users": 0,
                "extra_branches": 0,
                "annual_billing": False,
                "is_demo": False,
                "is_default": True,
                "created_at": now_iso(),
            }
            await _raw_db.organizations.insert_one(default_org_doc)
            # Tag all existing data with this org_id
            migrated = 0
            for col_name in TENANT_COLLECTIONS:
                result = await _raw_db[col_name].update_many(
                    {"organization_id": {"$exists": False}},
                    {"$set": {"organization_id": default_org_id}}
                )
                migrated += result.modified_count
            logger.info("Multi-tenancy migration: %d documents tagged with default org", migrated)

    # ── Super Admin creation ──────────────────────────────────────────────────
    SUPER_ADMIN_EMAIL = "janmarkeahig@gmail.com"
    SUPER_ADMIN_PASS = "Aa@58798546521325"
    existing_super = await _raw_db.users.find_one({"is_super_admin": True}, {"_id": 0})
    if not existing_super:
        await _raw_db.users.insert_one({
            "id": new_id(),
            "username": "superadmin",
            "full_name": "Platform Admin",
            "email": SUPER_ADMIN_EMAIL,
            "password_hash": hash_password(SUPER_ADMIN_PASS),
            "role": "admin",
            "is_super_admin": True,
            "organization_id": None,
            "active": True,
            "created_at": now_iso(),
        })
        logger.info("Super admin created: %s", SUPER_ADMIN_EMAIL)

    # Check if setup is needed (no auto-creation of users)
    user_count = await db.users.count_documents({})
    if user_count == 0:
        logger.info("No users found - system needs setup via /api/setup/initialize")

    # Create default price schemes if none exist (for fresh installs only)
    schemes = await _raw_db.price_schemes.count_documents({})
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
        await _raw_db.price_schemes.insert_many(default_schemes)
        logger.info("Default price schemes created")

    # Create indexes
    try:
        await _raw_db.users.create_index("username", unique=True, sparse=True)
    except Exception:
        pass
    try:
        await _raw_db.users.create_index("email", sparse=True)
    except Exception:
        pass
    await _raw_db.users.create_index("id", unique=True)
    await _raw_db.products.create_index("sku")
    await _raw_db.products.create_index("id", unique=True)
    await _raw_db.products.create_index("parent_id")
    # Text index for fast product search (name + sku + barcode)
    try:
        await _raw_db.products.create_index(
            [("name", "text"), ("sku", "text"), ("barcode", "text")],
            name="product_text_search", default_language="none"
        )
    except Exception:
        pass  # Index may already exist with different options
    await _raw_db.inventory.create_index([("product_id", 1), ("branch_id", 1)], unique=True)
    await _raw_db.sales.create_index("branch_id")
    await _raw_db.sales.create_index("created_at")
    await _raw_db.invoices.create_index("branch_id")
    await _raw_db.invoices.create_index("customer_id")
    await _raw_db.invoices.create_index("created_at")
    await _raw_db.customers.create_index("id", unique=True)
    await _raw_db.customers.create_index("branch_id")
    await _raw_db.branches.create_index("id", unique=True)
    await _raw_db.movements.create_index([("product_id", 1), ("branch_id", 1)])
    await _raw_db.movements.create_index("created_at")
    await _raw_db.branch_prices.create_index([("product_id", 1), ("branch_id", 1)], unique=True)
    await _raw_db.notifications.create_index("created_at")
    await _raw_db.notifications.create_index("target_user_ids")
    logger.info("Database indexes created")

    # ── Provision 4-wallet system for all existing branches ──────────────────
    from utils import provision_branch_wallets
    branches = await _raw_db.branches.find({"active": True}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    provisioned = 0
    for branch in branches:
        await provision_branch_wallets(branch["id"], branch.get("name", ""))
        provisioned += 1
    if provisioned:
        logger.info("Wallet provisioning complete — %d branches checked", provisioned)

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
    # ── Update owner email ────────────────────────────────────────────────────
    await _raw_db.users.update_one(
        {"username": "owner", "is_super_admin": {"$ne": True}},
        {"$set": {"email": "sibugayagrivetsupply@gmail.com"}}
    )

    # ── Daily subscription notification job ───────────────────────────────────
    async def _daily_subscription_check():
        """Check all orgs, send expiry warnings and lock expired accounts."""
        from routes.organizations import get_effective_plan, GRACE_PERIOD_DAYS
        from services.email_service import (
            send_trial_warning, send_grace_period_warning,
            send_account_locked
        )
        now = datetime.now(timezone.utc)
        orgs = await _raw_db.organizations.find(
            {"is_default": {"$ne": True}, "plan": {"$ne": "suspended"}},
            {"_id": 0}
        ).to_list(500)

        for org in orgs:
            if not org.get("owner_email"):
                continue
            email = org["owner_email"]
            name = org["name"]
            plan = org.get("plan", "basic")
            effective = get_effective_plan(org)

            # Determine reference date (trial_ends_at or subscription_expires_at)
            ref_date_str = org.get("trial_ends_at") if plan == "trial" else org.get("subscription_expires_at")
            if not ref_date_str:
                continue
            try:
                ref_dt = datetime.fromisoformat(ref_date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            days_until_expiry = (ref_dt - now).days

            # Expiry warnings (7, 3, 1 days before)
            if effective in ("trial", "basic", "standard", "pro") and days_until_expiry in (7, 3, 1):
                await send_trial_warning(email, name, days_until_expiry, ref_dt.strftime("%B %d, %Y"))

            # Grace period warnings
            elif effective == "grace_period":
                grace_ends = ref_dt + timedelta(days=GRACE_PERIOD_DAYS)
                grace_days_left = max(0, (grace_ends - now).days)
                await send_grace_period_warning(email, name, grace_days_left, grace_ends.strftime("%B %d, %Y"))

            # Lock expired accounts
            elif effective == "expired":
                current_status = org.get("subscription_status")
                if current_status != "expired":
                    await _raw_db.organizations.update_one(
                        {"id": org["id"]},
                        {"$set": {"subscription_status": "expired", "plan": "suspended"}}
                    )
                    await send_account_locked(email, name)

        logger.info("Subscription check complete — %d orgs checked", len(orgs))

    _scheduler.add_job(
        _daily_subscription_check,
        CronTrigger(hour=9, minute=0),  # 9 AM daily
        id="daily_subscription_check",
        replace_existing=True,
    )

    # ── Internal invoice due date checker ─────────────────────────────────
    async def _daily_invoice_check():
        from routes.internal_invoices import check_due_invoices
        try:
            await check_due_invoices()
            logger.info("Internal invoice due date check completed")
        except Exception as e:
            logger.error(f"Invoice check failed: {e}")

    _scheduler.add_job(
        _daily_invoice_check,
        CronTrigger(hour=8, minute=0),  # 8 AM daily
        id="daily_invoice_check",
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


@app.get("/api/reports/test-report-v2")
async def download_test_report_v2():
    """Download the AgriBooks SaaS Platform Test Report v2.0 PDF."""
    path = "/app/AgriBooks_SaaS_Test_Report_v2.pdf"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Test report not found. Run generate_test_report.py first.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="AgriBooks_SaaS_Test_Report_v2.pdf",
        headers={"Content-Disposition": "attachment; filename=AgriBooks_SaaS_Test_Report_v2.pdf"}
    )
