# AgriBooks — Changelog

## 2026-02-25: Phase 4 — Feature Gate Upgrade Prompts & PDF Test Report

### Added
- **FeatureGate component** (`/app/frontend/src/components/FeatureGate.js`) — Branded upgrade prompt card shown when a user navigates to a page their subscription plan doesn't include. Shows: feature icon, plan badge (Standard/Pro), feature name, description, "What you'll unlock" list, plan upgrade CTA, back to dashboard CTA
- **9 gated routes in App.js** — FeatureGate wraps: `/purchase-orders`, `/pay-supplier`, `/suppliers`, `/employees`, `/fund-management`, `/branch-transfers`, `/audit`, `/reports`, `/user-permissions`
- **PDF Test Report v2.0** — `AgriBooks_SaaS_Test_Report_v2.pdf` (211KB) — comprehensive documentation of all 17 modules, subscription plan matrix, Phase 1/2/3 test results (83 tests total), bug reports, credentials, security checklist

### Test Results: 14/14 frontend scenarios — 100% pass rate

---

## 2026-02-25: Phase 3 — Subscription Plan Enforcement & Feature Flag Testing

### Added
- **Branch Limit Enforcement (Backend)** — `POST /api/branches` now checks org's `max_branches` and returns a clear 400 error when at limit (with plan name and upgrade suggestion)
- **Branch Limit UI (BranchesPage)** — Shows `(X/max used)` counter in red when at limit, amber warning banner explaining the limit, `Add Branch` button disabled and shows upgrade tooltip
- **Unlimited indicator** — Founders/Trial plans show `(Unlimited)` in green on BranchesPage
- **Feature Flag Nav Enforcement (Layout.js)** — Navigation items are now hidden based on subscription feature flags. Items gated: Purchase Orders, Pay Supplier, Suppliers, Employees, Fund Mgmt, Branch Transfers, Audit Center, Reports, Permissions

### Fixed  
- **Critical: Multi-tenancy branch count isolation** — Branch limit check was using a global count across all organizations instead of per-org count. Fixed to scope by `organization_id`.
- **`/auth/me` now uses live feature flags** — Was using static `PLAN_FEATURES` dict. Fixed to call `get_live_feature_flags()` so admin panel changes take effect immediately.

### Test Results: 46/46 backend, 17/17 frontend — 100% pass rate

---

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
