# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business (originally single-tenant). Now converting to a **subscription-based, multi-tenant SaaS platform** — similar to QuickBooks for Philippine retail businesses.

**Tagline:** Audit-Grade Retail Intelligence  
**Sub-tagline:** Serious control for serious businesses  
**Built for:** Growing businesses

---

## CRITICAL AGENT NOTE — VPS DEPLOYMENT
**EVERY TIME code is ready to deploy to agri-books.com, ALWAYS include these 3 commands:**

```bash
cd /var/www/agribooks && git pull origin main
supervisorctl restart agribooks-backend
cd frontend && yarn build
```

**Steps before running the above:**
1. User must click **"Save to Github"** in Emergent first to push the code
2. SSH into VPS: `ssh root@76.13.215.32`
3. Run the 3 commands above in order

**VPS Details:**
- Domain: `agri-books.com`
- IP: `76.13.215.32`
- User: `root`
- Backend managed by: `supervisorctl` (process name: `agribooks-backend`)
- Frontend: static build served by Nginx from `/var/www/agribooks/frontend/build/`
- No hot reload on VPS — backend needs supervisorctl restart, frontend needs yarn build

---

## Core Requirements
- Offline Functionality with auto-sync
- Product Management (3000+ SKUs, parent/repack system)
- Multi-Branch Management (branch-specific data, owner overview, Branch Transfers)
- Advanced Accounting (expenses, receivables, fund management)
- Complex Pricing & Credit (tiers, interest/penalty system)
- Sales & Purchasing Workflow (unified interfaces)
- Daily Operations (Close Wizard, Z-Report, archive)
- Granular Permissions & Security (Inflow-Cloud-style, TOTP 2FA)
- Editable Invoices & POs (audit trail, Reopen PO)
- Inventory Management (count sheets, corrections, audit log)
- Employee & User Management (PINs, cash advances)
- Data Import (QuickBooks products)
- **[SaaS] Multi-tenancy: organization_id isolation on all data**
- **[SaaS] Subscription plans: Basic/Standard/Pro with branch/user limits**
- **[SaaS] Public landing page + self-registration**
- **[SaaS] Super Admin platform management panel**

## Tech Stack
- Frontend: React (Create React App), Tailwind CSS, Shadcn/UI, Lucide icons
- Backend: FastAPI (Python), MongoDB
- Auth: JWT (with org_id + is_super_admin), TOTP (pyotp), Manager PINs
- Multi-tenancy: ContextVar-based TenantDB wrapper (transparent org isolation)
- File uploads: Local disk (/app/uploads), QR-based upload + view system
- Offline: IndexedDB (idb pattern), syncManager

## Subscription Plans (Pricing)
| Plan | PHP/mo | USD/mo | Branches | Users |
|------|--------|--------|----------|-------|
| Basic | ₱1,500 | $30 | 1 | 5 |
| Standard | ₱4,000 | $80 | 2 | 15 |
| Pro | ₱7,500 | $150 | 5 | Unlimited |
| Extra Branch | ₱1,500 | $30 | +1 per addon | - |
| Trial | Free | Free | 5 (Pro features) | Unlimited |

Annual billing: 2 months free (pay 10 months, get 12).

## Architecture
```
/app
├── backend/
│   ├── config.py           # TenantDB wrapper + ContextVar org isolation
│   ├── routes/
│   │   ├── auth.py         # Email/username login, org subscription in /me
│   │   ├── organizations.py # Registration, plans, /my org info
│   │   ├── superadmin.py   # Platform admin (orgs, stats, subscription mgmt)
│   │   └── ... (all existing routes - unchanged, tenant isolation is transparent)
│   └── main.py             # Startup migration + super admin creation
└── frontend/
    └── src/
        ├── App.js          # New routes: /, /register, /upgrade, /superadmin
        ├── pages/
        │   ├── LandingPage.js    # NEW: Public marketing page
        │   ├── RegisterPage.js   # NEW: Company self-registration
        │   ├── LoginPage.js      # UPDATED: Email/username login
        │   ├── UpgradePage.js    # NEW: Subscription upgrade with QR payment
        │   ├── SuperAdminPage.js # NEW: Platform admin panel
        │   └── ... (all existing pages unchanged)
        ├── components/
        │   └── Layout.js         # UPDATED: Trial expiry banner, upgrade link
        └── contexts/
            └── AuthContext.js    # UPDATED: Email login, subscription state
```

## Key API Endpoints

### SaaS (NEW)
- `POST /api/organizations/register` — Self-registration (public)
- `GET /api/organizations/plans` — Plan definitions (public)
- `GET /api/organizations/my` — Current org info + subscription
- `GET /api/superadmin/organizations` — All orgs (super admin only)
- `PUT /api/superadmin/organizations/{id}/subscription` — Update plan
- `GET /api/superadmin/stats` — Platform stats

### Auth (UPDATED)
- `POST /api/auth/login` — Now accepts `email` or `username`, returns subscription info
- `GET /api/auth/me` — Now includes subscription info

## DB Schema (Key)
### organizations (NEW collection)
```json
{
  "id": "uuid",
  "name": "Company Name",
  "owner_email": "admin@co.com",
  "plan": "trial|basic|standard|pro|suspended",
  "subscription_status": "trial|active|expired|suspended",
  "trial_ends_at": "ISO date",
  "max_branches": 1,
  "max_users": 5,
  "extra_branches": 0,
  "is_default": false,
  "is_demo": false
}
```
### All existing collections
Added `organization_id` field to all 20+ collections via TenantDB migration.

## Super Admin Access
- Portal: `/admin` (NOT linked from any public page — security by obscurity)
- Email: janmarkeahig@gmail.com
- Password: Aa@58798546521325
- TOTP: Google Authenticator (setup required on first login at /admin)
- Recovery: 8 backup codes generated on TOTP setup (emailed + shown once)

## Regular Admin (Default Org)
- Email: sibugayagrivetsupply@gmail.com
- Password: 521325

## Prioritized Backlog

### P0 — Critical SaaS (COMPLETED ✅)
- [x] Multi-tenancy foundation (TenantDB wrapper)
- [x] Email-only login (removed username)
- [x] Self-registration + 14-day trial
- [x] Landing page with dynamic pricing + feature table (live from backend)
- [x] Super Admin panel (v3: 4-tab Overview/Organizations/Feature Flags/Payment Settings)
  - [x] Feature Flags tab — toggle per-plan per-feature with All On/Off, Save & Publish
  - [x] Dynamic feature matrix stored in DB, fetched by landing page
  - [x] Pricing cards show live top features from DB
- [x] Separate admin portal at /admin with Google Authenticator TOTP + backup codes
- [x] Email notifications via Resend (welcome, trial warning, grace, locked, activated)
- [x] 3-day grace period + daily subscription check scheduler - sends warnings + locks expired accounts
- [x] Founders plan (unlimited branches, all features, never expires)
- [x] Auto 30-day expiry for paid plans (Basic/Standard/Pro) when admin activates
- [x] Branch limit enforcement (backend 400 + frontend disabled button + warning banner)
- [x] Feature flag enforcement in navigation (nav items hidden based on plan's feature flags)
- [x] /auth/me uses live feature flags from DB (not static defaults)
- [x] FeatureGate component — upgrade prompt cards on all locked pages (9 routes gated)
- [x] PDF Test Report v2.0 generated (AgriBooks_SaaS_Test_Report_v2.pdf, 211KB)

### P0 — Bug Fixes & Authorization Improvements (COMPLETED ✅)
- [x] Invalid PIN/TOTP returns 400 instead of 401 — fixed in verify.py, accounting.py (was causing logout/redirect to login on wrong PIN)
- [x] Inventory Correction: admin path fixed — pendingCorrection state not set before submitCorrection (now passes data directly)
- [x] Capital Injection (capital_add) now accepts Owner PIN or TOTP — any employee can execute with admin authorization (no longer admin-role-only)
- [x] Safe → Bank now visible to all users (was hidden, TOTP still required)
- [x] Inventory /set endpoint repack guard added (was missing)
- [x] Inventory value verified: repacks correctly excluded from all value calculations
- [x] /login not accessible in setup mode fixed (added to setup-mode routes, default redirect to /login)
- [x] setup_completed false positive fixed (setup.py checks super admin/org existence)
- [x] "Error Saving Products" when changing type fixed (missing has_perm import in products.py)
- [x] Branch not created on registration fixed (auto-creates first branch + fund wallets, branch_name field added to register form)

### P0 — Smart Capital Pricing (COMPLETED ✅)
- [x] Default capital_method changed to "last_purchase" for new products
- [x] GET /purchase-orders/{po_id}/capital-preview endpoint — returns per-item: current_capital, new_price, projected_moving_avg, needs_warning, price_drop_pct
- [x] POST /purchase-orders/{po_id}/receive accepts capital_choices per product
- [x] SmartCapitalDialog in PurchaseOrderPage — shows per-item table with price drop indicators, New Price vs Moving Avg toggle buttons, bulk actions, Confirm Receive
- [x] GET /branch-transfers/{id}/capital-preview — compares transfer_capital vs destination branch capital
- [x] SmartCapitalDialog in BranchTransferPage — same pattern, intercepts receive flow
- [x] capital_changes MongoDB collection (tenant-isolated) — logged on PO receive, transfer receive, manual edit
- [x] GET /products/{id}/capital-history endpoint
- [x] Capital History accordion section in ProductDetailPage — timeline with source badges (PO/Transfer/Manual), price delta arrows, method labels, by whom
- [x] Inventory Correction bug fixed — admin path silently returned due to pendingCorrection not being set (now passes data directly)
- [x] Owner PIN + TOTP 3-mode verification dialog — TotpVerifyDialog now has 3 tabs: Owner PIN (in-person), TOTP/Authenticator (remote), Password (fallback)
- [x] verify-admin-action endpoint now supports mode='pin' — checks system_settings.admin_pin (the existing "Admin Verification PIN" in Audit Setup tab)
- [x] Settings labels updated: Security tab clarifies TOTP is for remote approvals; Audit Setup tab renamed "Owner PIN — For In-Person Approvals"

### Bug Fixes — Feb 2026
- [x] Fixed Quick Sales inventory race condition: Used `effectiveBranchId` (from localStorage/user data, immediately available) instead of `currentBranch?.id` (async, requires branches API). Added backend fallback to aggregate all-branch inventory when no branch_id sent.
- [x] Fixed Dashboard data inconsistencies:
  - Added `today_digital_sales` tracking (digital/split payments were invisible on both dashboards)
  - Fixed Net Cash Flow formula: now = cash sales + digital sales + AR collected − expenses (was missing digital)
  - Made branch-summary and stats formulas consistent (both now use same cash-flow logic)
  - Updated frontend KPIs: "Walk-in Sales" → "Total Sales" (shows all revenue), "Cash Sales" shows cash-only with digital sub-text
  - Owner branch cards now show 6 metrics: Total Sales, Cash Sales, New Credit, Digital Sales, Cashier+Safe, AR Outstanding
- [x] Fixed Employee Advance: Backend now enforces monthly_ca_limit and requires manager_approved_by when exceeded (was frontend-only check)
- [x] Fixed Customer Cashout Reversal: Now correctly returns funds to cashier (+amount) instead of double-deducting (-amount)
- [x] Full System Audit: 24/24 backend tests passing — covers registration, setup, products, POs, sales, all expense types, CA limits, reversals, fund wallets, uploads/QR, dashboard, returns, POS sync, and multi-tenant isolation
- [x] Gap Audit: 26/26 additional tests — covers branch transfers, digital/split sales, invoice void, repack products (sell & derived stock), inventory correction, count sheets, daily close, interest/penalty generation, invoice edit with audit trail, AR/sales/expense reports, cashier role restrictions, branch pricing overrides, actual file upload (multipart), supplier CRUD, notifications, payment void, daily log/report, product movement history, customer statement
- [x] PO Receipt Workflow:
  - Mandatory receipt upload before PO can be received (backend enforced)
  - Receipt count shown on PO list with badge (No receipts / X photos)
  - Review status shown: "Pending review" / "Reviewed by [name]"
  - "Mark as Reviewed" button with admin PIN/TOTP verification
  - Auto-notification sent to owner/admin when PO is received with receipts
  - Upload page (phone) has "Take Photo" and "Choose from Gallery" options
- [x] Inline Receipt Upload During Creation (Feb 2026):
  - New `POST /api/uploads/direct` endpoint for authenticated inline file uploads
  - New `DELETE /api/uploads/direct/{session_id}/{file_id}` endpoint to remove files
  - New `POST /api/uploads/reassign` endpoint to link pending upload sessions to actual records
  - `ReceiptUploadInline` reusable React component (compact + full modes, drag & drop, multi-file)
  - PO Creation: Receipt upload REQUIRED before Cash/Terms submission (integrated into form)
  - Branch Transfer Receive: Receipt upload REQUIRED before confirming receipt (integrated into dialog)
  - Expense Creation: Receipt upload OPTIONAL (compact mode in expense form)
  - Backward compatible: old POs/records can still upload via edit/view QR flow
  - QR Code Phone Upload: "Use Phone" button generates QR code, phone scans to open upload page with record details, camera/gallery options, auto-polls for uploads
- [x] Bug Fix: QR Dialog Close Button (Feb 2026):
  - ViewQRDialog and UploadQRDialog now use createPortal to render to document.body
  - Added stopPropagation, higher z-index (99999), pointer-events: auto to prevent Shadcn Dialog overlay interference
- [x] Bug Fix: TOTP Unauthorized on Phone Verify (Feb 2026):
  - New public endpoint POST /api/verify/public/{doc_type}/{doc_id} — doesn't require auth
  - ViewReceiptsPage now calls public endpoint for phone-based verification
  - Security maintained via PIN/TOTP validation itself
- [x] Unified PIN Verification System (Feb 2026):
  - Root cause: 3+ independent PIN check implementations across codebase (verify.py, purchase_orders.py, uploads.py) each checking different PIN types
  - Fix: `_resolve_pin()` in verify.py now checks ALL 4 PIN types: system admin PIN (bcrypt), manager_pin/owner_pin (plain text), TOTP, auditor PIN
  - `mark_po_reviewed()` and `mark_record_reviewed()` now import and use `_resolve_pin` instead of custom logic
  - Both phone (public) and desktop (authenticated) verify endpoints now also update `receipt_review_status` field when record has uploaded receipts
  - Result: Manager PIN works on phone AND desktop. Phone verification updates desktop PO status.
- [x] Unified PIN Management UI (Feb 2026):
  - Settings tab renamed from "Audit Setup" to "PIN Management"
  - Overview card explaining 3 PIN types: Admin PIN, Manager PIN, TOTP
  - Admin PIN section: system-wide PIN, only admin can set/change
  - My PIN section: managers/admins change their own PIN (requires current PIN)
  - Staff Manager PINs table: admin sets/resets any user's PIN with audit trail
  - Auditor Access section: toggle auditor role + set auditor PIN
  - Backend: PUT /auth/change-my-pin — validates current PIN before allowing change
- [x] Bug Fix: Wrong PIN Logout (Feb 2026):
  - Root cause: PUT /auth/change-my-pin returned HTTP 401 on wrong PIN, which triggered the global axios interceptor to log the user out
  - Fix: Changed to HTTP 400 so it shows an error toast without destroying the session
- [x] Unified Team & Settings Consolidation (Feb 2026):
  - **Problem**: Settings, Accounts, and Permissions pages were redundant — all managed users/roles/PINs
  - **Solution**: Merged into two clean pages:
    - **Team page** (`/team`): Members tab (user CRUD, PIN mgmt, disable/delete, expandable row details) + Permissions tab (granular per-user permissions, presets)
    - **Settings page** (`/settings`): My Account tab (profile, password, PIN — all roles) + Security tab (Admin PIN, TOTP, Auditor Access — admin only)
  - Sidebar: Removed "Accounts" and "Permissions" nav items, replaced with "Team"
  - Backend: Added `DELETE /api/users/{id}/permanent` (hard delete), `PUT /api/users/{id}/reactivate`, `GET /api/users?include_inactive=true`
  - "Show disabled" toggle on Team page to reveal deactivated users
  - Expandable user rows with quick-action buttons (Edit, Set PIN, Reset PW)
- [x] Bug Fix: Sales History Miscategorization (Feb 2026):
  - **Problem**: Sales paid via GCash/digital/split were showing as "Credit Sales" in the Sales History board. Cash sales showed zero for digital payments.
  - **Root cause**: Backend `invoices/history/by-date` categorized everything not "cash" as credit. Frontend only had Cash/Credit binary classification.
  - **Fix**: Backend now returns separate `digital` total for `payment_type in ("digital", "split")`. Frontend board now shows 5 stat cards: Cash Sales, Digital Sales, Credit Sales, Grand Total, Transactions. Row badges show actual platform (e.g., "GCash") with blue badge instead of binary Cash/Credit.
  - **Split payment fix**: Split invoices now properly allocate `cash_amount` → Cash Sales and `digital_amount` → Digital Sales (previously entire grand_total went to Digital). Row badges for split show "Split · GCash" (indigo) to distinguish from pure digital (blue). Fix applied to `/api/invoices/history/by-date`, `/api/dashboard` (owner stats), and `/api/dashboard` (branch cards).
- [x] Pending Receipt Reviews Dashboard Widget (Feb 2026):
  - New `GET /api/dashboard/pending-reviews` endpoint — returns unreviewed records (POs, branch transfers, expenses) with upload sessions, grouped by branch
  - New `POST /api/uploads/mark-reviewed/{record_type}/{record_id}` — generic review endpoint for branch_transfers and expenses (POs had existing one)
  - `PendingReviewsWidget` React component — branch-grouped view for owner/admin, single-branch view for branch users
  - Owner Dashboard: "Pending Receipt Reviews" card with expandable branch sections, inline review dialog with PIN/TOTP, receipt photo preview
  - Branch Dashboard: "Receipts Awaiting Review" card showing only that branch's pending items (branch users see "Pending" badge, admins get "Review" button)
  - Review dialog: shows record details, receipt photo thumbnails, review notes field, PIN/TOTP verification, "View Full Record" link

### P1 — Upcoming
- Employee Cash Advance Summary Report
- User Role Presets (save named permission sets)
- Demo organization with realistic seed data
- Payment QR codes (actual Maya/GCash/Bank/PayPal QR codes)
- Smart capital pricing for branch transfers (same logic as PO) ✅ DONE

### P2 — Backlog
- "Pack & Ship" workflow for Branch Transfers
- Resilient Offline Sync improvements
- Annual billing automation
- Stripe/PayMongo integration for automated billing
- Refactor SuperAdminPage.jsx (1000+ lines → smaller components)
- AdminLoginPage.jsx: replace window.location.href with React state update
- Smarter Price Suggestions: Auto-suggest retail price based on capital + margin
