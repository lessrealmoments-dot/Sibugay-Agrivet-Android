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
- [x] Bug Fix: Safe Wallet Movement History Empty (Feb 2026):
  - **Problem**: Paying a PO from the safe deducted the balance correctly, but the movement history was empty.
  - **Root cause**: Systemic — safe wallet operations modified `safe_lots` but never created `wallet_movements` entries. The `update_cashier_wallet()` helper always logged movements, but no equivalent existed for the safe.
  - **Fix**: Created `record_safe_movement(branch_id, amount, reference)` helper in `utils/helpers.py`. Applied at all 7 code paths: PO payment from safe, PO adjust-payment (deduction + refund), cashier→safe, safe→cashier, safe→bank, capital injection to safe.
- [x] Repack Products in Price-Below-Capital Scan (Feb 2026):
  - **Problem**: The PriceScanManager background scan (every 5 min) excluded repack products, so repacks priced below their derived cost were never flagged.
  - **Fix**: Backend `pricing-scan` endpoint now loads repacks, derives their cost from `parent_cost / units_per_parent`, and includes them in the scan. Moving average and last purchase also derived from parent history. Frontend shows purple "REPACK" badge with parent info and "(derived)" cost indicator.
- [x] Interactive Dashboard Redesign with Draggable Widgets (Feb 2026):
  - **Drag-and-drop layout**: All dashboard widgets are draggable using `react-grid-layout`. Per-user layout persistence via localStorage. "Reset Layout" button restores optimized default.
  - **Sales Trends Widget**: Interactive period selector (This Month, Last Month, Quarter, Year) with area chart showing daily revenue. Summary cards for Revenue, Cash, Digital, Credit breakdown.
  - **Branch Comparison Widget**: Bar chart comparing branch revenue with leaderboard ranking. Period-synced with Sales Trends.
  - **Accounts Payable Widget**: Total outstanding, overdue (red), due this week (amber), upcoming. Shows individual overdue/due-soon POs with vendor and amount. Available on both owner and branch dashboards.
  - **Backend**: New endpoints `GET /api/dashboard/sales-analytics` (daily aggregation with split payment handling, branch breakdown) and `GET /api/dashboard/accounts-payable` (AP summary with overdue/due-soon/upcoming).
  - Existing KPI cards, cash position, AR overview, pending reviews, branch cards all preserved and improved.
- [x] Pending Receipt Reviews Dashboard Widget (Feb 2026):
  - New `GET /api/dashboard/pending-reviews` endpoint — returns unreviewed records (POs, branch transfers, expenses) with upload sessions, grouped by branch
  - New `POST /api/uploads/mark-reviewed/{record_type}/{record_id}` — generic review endpoint for branch_transfers and expenses (POs had existing one)
  - `PendingReviewsWidget` React component — branch-grouped view for owner/admin, single-branch view for branch users
  - Owner Dashboard: "Pending Receipt Reviews" card with expandable branch sections, inline review dialog with PIN/TOTP, receipt photo preview
  - Branch Dashboard: "Receipts Awaiting Review" card showing only that branch's pending items (branch users see "Pending" badge, admins get "Review" button)
  - Review dialog: shows record details, receipt photo thumbnails, review notes field, PIN/TOTP verification, "View Full Record" link
- [x] Branch-to-Branch Stock Request Workflow Fix (Feb 2026):
  - **Problem**: When a branch creates a stock request (branch_request PO), the supply branch gets a notification but has no clear way to find or process the request.
  - **Fix**: Added notification navigation in NotificationBell.js — clicking transfer-related notifications (branch_stock_request, transfer_incoming, transfer_variance_review, transfer_accepted, transfer_disputed) navigates directly to the Branch Transfers page with the correct tab/subtab selected.
  - Added proper icons for all transfer notification types (Package, ArrowLeftRight, AlertTriangle, ClipboardCheck, XCircle) with color-coded backgrounds.
  - Added URL deep-linking via `useSearchParams` in BranchTransferPage.js — supports `?tab=history&subtab=requests` to open directly to Stock Requests tab.
  - Added "View →" indicator on navigable notifications so users know they can click to navigate.
  - Full workflow: Notification → Click → Branch Transfers → Stock Requests tab → Generate Transfer → Pre-filled New Transfer form.
- [x] Enhanced Stock Request → Transfer Workflow (Phase 1, Feb 2026):
  - **Requested vs Available vs Send columns**: When generating a transfer from a stock request, shows Requested Qty (what branch wants), Available Stock (from source inventory), and Send Qty (auto-defaults to min of both). Amber "low" indicator when available < requested, "partial" indicator on send qty.
  - **Role-based pricing**: Admin can set both Transfer Capital and Branch Retail. Managers can only set Transfer Capital — Branch Retail is disabled with "Admin sets retail" hint.
  - **Request status tracking**: Stock request PO updates to "fulfilled" or "partially_fulfilled" when the generated transfer is received. Status badges shown on Stock Requests tab.
  - **Transfer-to-request linking**: Transfers store `request_po_id` and `request_po_number`. History list shows "from PO-xxx" reference. Detail dialog shows blue request reference badge.
  - **Status Timeline**: Transfer detail dialog shows a visual timeline: Requested → Transfer Created → Sent → Received → Settled. Each step shows date and completion status.
  - **Form pre-fill fix**: Added `skipResetRef` to prevent useEffect from clearing pre-filled form data when branch selectors trigger reset effects.
- [x] Internal Invoicing System (Phase 2, Feb 2026):
  - **Auto-created invoices**: When a branch transfer is created, an internal invoice (INV-YYYYMMDD-XXXX) is auto-generated in the `internal_invoices` collection. Linked to the transfer via `invoice_id`/`invoice_number`.
  - **Invoice status syncs with transfer**: prepared → sent → received. Timestamps (sent_at, received_at) set on each transition.
  - **Printable invoice**: Enhanced print function generates a professional internal invoice with: From/To branches, product table with "Actual Rcvd" column (blank for manual corrections), corrections/discrepancy notes box, payment terms (Net 15, due date), signature lines (Prepared By, Driver, Received By).
  - **API endpoints**: `GET /internal-invoices` (list with branch enrichment), `GET /internal-invoices/summary` (payable/receivable totals with overdue/due-soon), `GET /internal-invoices/{id}`, `GET /internal-invoices/by-transfer/{transfer_id}`.
  - **Frontend**: Transfer detail dialog shows invoice badge (INV-xxx, Terms: Net 15) with "Print Invoice" button. History list shows invoice reference.
  - **Physical workflow**: Invoice printed (2 copies) → driver carries copy → Branch 1 counts actual vs invoice → writes corrections on paper → uploads photo (QR phone or PC) → confirms receipt in system.
- [x] Auto-Settlement via Branch Bank (Phase 3, Feb 2026):
  - **Pay Now endpoint**: `POST /internal-invoices/{id}/pay` — admin-only, deducts from receiving branch's bank wallet, credits supplier branch's bank wallet. Validates balance, creates wallet_movements for both branches.
  - **Internal Invoices page**: New `/internal-invoices` page with summary cards (Total Payable, Overdue, Due This Week, Total Receivable), invoice list with All/Unpaid/Paid tabs, and "Pay Now" button with confirmation dialog showing bank-to-bank transfer details.
  - **Auto-pay scheduler**: Daily at 8AM, checks for overdue invoices. If bank has sufficient balance, auto-deducts and notifies admin. If insufficient, sends overdue notification.
  - **Due-soon notifications**: 3 days before due date, sends notification to admin.
  - **Sidebar navigation**: "Internal Invoices" added under Branches section.
  - **Notification types**: Added icons for internal_invoice_paid, auto_paid, due, overdue.
- [x] Internal Profitability Dashboard Widget (Feb 2026):
  - **Dashboard widget**: Added to Owner Dashboard showing per-branch internal revenue (supplied goods), cost (received goods), and profit/loss.
  - **Bar chart**: Green bars for profit centers, red for cost centers using recharts.
  - **Period selector**: This Month, Last Month, Quarter, Year with live data refresh.
  - **Branch ranking**: Shows top branches by internal profit with revenue - cost = profit breakdown.
  - **Backend**: `GET /internal-invoices/profitability` endpoint with period filter, per-branch aggregation, sorted by profit.
  - **Navigation**: "View all invoices" link to Internal Invoices page.
- [x] Bulletproof Offline Sales — Phase A (Feb 2026):
  - **Local inventory deduction**: After any offline sale, stock is immediately deducted from the local IndexedDB cache (both inventory and product `available` fields). Cashier sees accurate stock even when offline.
  - **Envelope ID for idempotency**: Every sale now includes a UUID `envelope_id`. The sync endpoint (`POST /sales/sync`) checks for duplicate `envelope_id` to prevent double-processing if a sale syncs twice.
  - **Org-scoped IndexedDB**: Database name changed from `agripos_offline` to `agripos_offline_{org_id}`. Set on login/fetchUser via `setOfflineOrg()`. Prevents cross-tenant data leaks in multi-tenant SaaS.
  - **beforeunload warning**: POS page registers a `beforeunload` event that checks for pending sales. If unsynced sales exist, browser prompts "You have unsynced sales" before closing.
  - **Delta sync**: Backend `GET /sync/pos-data?last_sync={timestamp}` now filters products by `updated_at`/`created_at >= last_sync`. Returns `is_delta: true` flag. Frontend merges delta products via `putProduct()` instead of full cache replace.
- [x] Smart Data Caching — Phase B (Feb 2026):
  - **Background refresh every 5 min**: `startAutoSync` now sets up a `cacheRefreshInterval` (5-minute delta sync) in addition to the 30s pending-sales check. Lightweight — only fetches changed records via delta sync.
  - **Org change detection**: When a different company logs in, `setOfflineOrg()` detects the change and calls `clearOrgCache()` to delete the old org's IndexedDB. Pending sales are preserved — old DB only deleted if no pending sales remain.
  - **Proper cleanup**: `stopAutoSync` clears all intervals and removes the `online` event listener reference.
  - **Branch-aware refresh**: `startAutoSync` accepts a branch ID getter function so background refresh targets the correct branch.
  - **UI indicator**: OfflineIndicator shows "Auto-refreshes every 5 min" when cache is ready.
- [x] Enhanced Sync Progress & Status — Phase C (Feb 2026):
  - **Logout warning**: When user logs out with pending offline sales, shows confirmation dialog: "You have unsynced offline sales! They will sync next time you log in." Cancel prevents logout.
  - **Enhanced pending sales indicator**: Shows bold count, sync progress bar ("Syncing sale 3/5..."), "waiting for internet" badge when offline, and "Sales are safely stored" reassurance message.
  - **Prominent Sync Now button**: Full-width amber button replaces old "Push now" link for better visibility.

### P1 — Upcoming
- Employee Cash Advance Summary Report
- User Role Presets (save named permission sets)
- Demo organization with realistic seed data

### Recent Bug Fixes (Feb 27, 2026)
- [x] **Branch-Specific Product Detail**: Capital History, Movement History, Order History, and Vendors now filter by the user's current branch instead of showing all-branches data.
- [x] **Branch-Specific Pricing**: Editing retail prices on a specific branch now saves to `branch_prices` (per-branch override) instead of modifying the global product, preventing cross-branch price contamination.
- [x] **Branch-Specific Vendors**: Vendors can now be scoped to specific branches. Product detail page filters vendors by the current branch.
- [x] **Order History Refactored**: The order history endpoint now returns properly formatted items from both Purchase Orders and Sales (previously only returned raw PO documents).
- [x] **Capital Change Tracking**: Capital changes from POs and branch transfers now include `branch_id` for proper branch-level audit trails.

### P2 — Backlog
- "Pack & Ship" workflow for Branch Transfers
- Resilient Offline Sync improvements
- Annual billing automation
- Stripe/PayMongo integration for automated billing
- Refactor SuperAdminPage.jsx (1000+ lines → smaller components)
- AdminLoginPage.jsx: replace window.location.href with React state update
- Smarter Price Suggestions: Auto-suggest retail price based on capital + margin
- Quick-action user details on Team page (expandable detail card)
- Selective Offline Sync (choose which data categories to sync)
