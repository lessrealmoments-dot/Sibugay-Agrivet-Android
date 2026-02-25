# AgriBooks — Changelog

## 2026-02-25: SaaS Multi-Tenancy Phase 1

### Added
- **Landing Page** (`/`) — Public marketing page with "Audit-Grade Retail Intelligence" headline, feature comparison vs QuickBooks/inFlow, 3-tier pricing cards, full feature table, annual billing toggle
- **Company Registration** (`/register`) — Self-registration creates new organization + admin user with 14-day Pro trial
- **Upgrade Page** (`/upgrade`) — Plan comparison, extra branches add-on, payment methods (Maya/GCash/Bank/PayPal placeholder)
- **Super Admin Panel** (`/superadmin`) — Platform admin: list all orgs, view stats, update subscriptions, extend trials
- **TenantDB Wrapper** — `config.py` now has a ContextVar-based transparent proxy that auto-injects `organization_id` into all DB operations
- **Organization Model** — New `organizations` MongoDB collection tracking plan, trial, limits
- **Email Login** — Login now accepts email OR username (backward compatible)
- **Subscription Info in JWT** — Login and /auth/me return subscription plan, features, limits
- **Trial Expiry Banner** — Layout shows banner when trial < 5 days remaining
- **Upgrade Link** in user dropdown for regular users
- **Platform Admin link** in user dropdown for super admin

### Changed
- `config.py` — Complete rewrite to add TenantDB wrapper + ContextVar
- `utils/auth.py` — `create_token` now accepts `org_id` + `is_super_admin`; `get_current_user` sets org context
- `routes/auth.py` — Login accepts email/username, returns subscription; /me returns subscription
- `routes/__init__.py` — Added organizations_router, superadmin_router exports
- `main.py` — Startup migration tags all existing data with default org_id; creates super admin if not exists
- `App.js` — New routes for landing, register, upgrade, superadmin pages
- `AuthContext.js` — Login now sends `email` field; logout clears subscription storage
- `LoginPage.js` — New dark design with email/username field, link to register
- `Layout.js` — Trial expiry banner, upgrade/superadmin links in user menu

### Fixed
- Deployment: JWT_SECRET now fails fast (no insecure fallback)
- Deployment: nginx `client_max_body_size 20M` for phone photo uploads
- Deployment: `upload_data` Docker volume for persistent file storage

### Data Migration
- All existing data (branches, products, users, etc.) automatically tagged with `organization_id = default_org_id`
- Default organization created: "AgriBooks (Default)" on Pro plan
- Super admin created: janmarkeahig@gmail.com

### Test Results
- Backend: 35/35 tests pass (100%)
- Frontend: 14/14 feature scenarios pass (100%)
