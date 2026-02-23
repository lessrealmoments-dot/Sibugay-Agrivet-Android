# AgriPOS - Multi-Branch Inventory, POS & Accounting System

## Original Problem Statement
Build an Accounting, Inventory, and POS website for multibranch management, similar to QuickBooks Online and Inflow Inventory Online, with unique features including:
- Parent Product & Repack system with auto stock deduction
- Offline POS with auto-sync capability
- 3000+ SKU support with preset product setup
- Multiple price schemes (Retail, Wholesale, Special, Government)
- Granular role-based permissions (Inflow Cloud style)
- Advanced accounting (expenses, receivables, payables)
- QuickBooks-style editable invoices with audit trail

## User Personas
1. **Admin/Owner** - Full system access, manages all branches, users, and financial data
2. **Branch Manager** - Manages branch operations, inventory, sales, with configurable permissions
3. **Cashier** - POS operations, customer service, limited system access
4. **Inventory Clerk** - Stock management, purchase orders, receiving

## Architecture
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui components
- **Backend**: FastAPI (Python) with JWT authentication
- **Database**: MongoDB with Motor async driver
- **Design**: Manrope + IBM Plex Sans fonts, Forest Green (#1A4D2E) primary, dark sidebar layout

## Latest Updates (Feb 2026)

### Dashboard Configuration + Reconcile Now Button - COMPLETE ✅ (Feb 2026)

**"Reconcile Now" button in Audit Center:**
- Cash section of the Audit Center now has a `Reconcile Now` button (amber)  
- Clicking it navigates directly to `/close-wizard` for immediate cash reconciliation
- Button appears inline with the actual cash count input for natural workflow

**Dashboard — Audit Health + Operations widgets (branch view):**
New row of 4 action cards below the Inventory Value section:
- **Audit Health**: Shows last audit score (0–100) with color coding (green/amber/red). If no audit, shows "No Audit · Run your first audit →". "Overdue (>30d)" warning. Clicking navigates to `/audit`
- **Price Issues**: Count of products with retail/wholesale below cost. Green if 0. Links to `/products` to fix. Computed from branch_prices + global prices
- **Low Stock**: Count of products ≤10 units. Red if >0. Links to `/inventory`
- **Days Since Close**: Color-coded (green if today, red if >1d). "Run Close Wizard →" quick link

**Dashboard — Owner consolidated view:**
- 5th KPI card added: **Audit Health** (was 4 cards, now 5) — shows last audit score across all branches with "No Audit · Run your first audit →" CTA and price issue count badge

**Backend — `dashboard.py` `/stats` endpoint additions:**
- `last_audit`: last completed audit session (score, type, dates)
- `days_since_audit`: days since last audit
- `price_issue_count`: count of products where retail or wholesale < cost (branch-specific)

### Audit Center + Legacy Cleanup - COMPLETE ✅ (Feb 2026)

**Audit Center (`/audit` — in sidebar under Reports):**
- Two audit types: **Partial** (financial only, manager can run) | **Full** (includes inventory, admin only)
- 8-section dashboard with traffic lights: Cash · Sales · AR · Payables · Transfers · Returns · Activity · Inventory
- **Overall Audit Score** (0–100) shown prominently
- **Section 1 (Inventory)** — Full audit only: uses two count sheets (auto-detected last 2 completed). Formula: `Baseline Count + All Movements = Expected · Physical - Expected = Variance`. Shows per-product breakdown with severity
- **Section 2 (Cash)** — Formula: `Starting Float + Cash Sales + AR Collected − All Expenses = Expected Cash`. Cashier can enter actual count, shows real-time discrepancy
- **Sections 3–8** — Sales (voided/edited flags), AR aging, Payables, Transfers (shortage/pending), Returns (pullout losses), User Activity (corrections, edits, off-hours)
- **Print Report** — professional printable audit report with all sections
- **Finalize Audit** — saves with score to audit history
- **Audit History** tab — all past audits with scores, comparable over time
- Severity: 🟢 ≤1% variance | 🟡 1–5% | 🔴 >5% (cash: >₱100 = critical)
- Backend: `routes/audit.py` with `GET /audit/compute`, `POST/GET/PUT /audit/sessions`

**Count Sheet — Audit Mode:**
- New "Audit Mode" toggle when creating a count sheet
- When enabled: system quantities are **hidden** during counting (auditor counts blind, no bias)
- Quantities revealed after completion for comparison
- Backend: `audit_mode: bool` field, masked response for `in_progress` + `audit_mode=True`

**Legacy Cleanup:**
- Removed `/sales` "Sales History" from sidebar nav (covered by Reports → Sales Report)
- `POSPage.js` (`/pos`) and `SalesOrderPage.js` (`/sales-order`) kept as fallback routes but removed from nav (replaced by `UnifiedSalesPage`)
- Route cleanup documented in `App.js`

**Backend: `routes/audit.py`**
- `GET /audit/compute?branch_id=&period_from=&period_to=&audit_type=` — full 8-section computation
- `POST /audit/sessions` — create and save audit session  
- `GET /audit/sessions` — list with branch filter
- `PUT /audit/sessions/{id}` — save section notes, finalize

**Tested:** Audit compute returns real data (Main Branch, Feb 2026): Cash Critical, Sales Good, AR ₱23k, Payables ₱30k, Activity Critical (8 inventory corrections). Score: 60/100.

### Branch-to-Branch PO Request + Return & Refund Wizard - COMPLETE ✅ (Feb 2026)

**Branch-to-Branch Stock Request:**
- New "Source" toggle in New PO form: External Supplier ↔ Branch Stock Request
- "Show Retail Price to Supply Branch" toggle — ON by default for admin/owner, OFF for managers (configurable)
- Selecting "Branch Stock Request" replaces the supplier field with a branch selector
- Submit creates `po_type: 'branch_request'` PO, notifies the supply branch users + admins
- Supply branch sees pending requests in Branch Transfers → History → **Requests tab** (blue badge count)
- Requests tab shows product list with qty from each requesting branch
- "Generate Transfer" button pre-fills the New Transfer form with all requested items (prices need to be set)
- `GET /purchase-orders/incoming-requests?branch_id=` — new endpoint for supply branch
- `POST /purchase-orders/{id}/generate-branch-transfer` — converts request → pre-filled transfer data

**Return & Refund Wizard (`/returns`):**
- 6-step guided wizard accessible from sidebar under Sales
- **Step 1** — Customer name (optional), customer type (walk-in/credit), return reason (7 options), original invoice #, notes
- **Step 2** — Product search with arrow-key navigation; add multiple items with quantity; Veterinary items auto-flagged
- **Step 3** — Condition assessment: Sellable | Damaged | Expired | Defective — manager decides (except Veterinary = always Pull Out)
- **Step 4** — Inventory decision: Return to Shelf (inventory +qty) OR Pull Out (loss, NOT added back)
- **Step 5** — Refund: per-item price selector (Retail or Wholesale), Full/Partial/No Refund, fund source (Cashier/Safe with live balances)
- **Step 6** — Confirmation + printable receipt
- **On completion:** expense record "Customer Return Refund" created, owner notified of pull-out losses with value, audit logged in `inventory_corrections`
- RMA numbers: RTN-YYYYMMDD-0001 format
- **Collections:** `returns`, uses existing `expenses`, `inventory_corrections`, `notifications`

**Backend: `routes/returns.py`**
- `GET /returns` — list with date/branch filters
- `GET /returns/{id}` — single return detail
- `POST /returns` — complete return processing (validates fund balance, updates inventory, creates expense, sends notifications)

### Purchase Order System Redesign - COMPLETE ✅ (Feb 2026)

**Replaced the old cash/credit payment dropdown with 3 clear action buttons:**
- **Save as Draft** — saves PO without inventory or fund changes (for orders not yet arrived)
- **Receive on Terms** → dialog: choose payment terms (COD/Net 7/15/30/45/60), creates Accounts Payable immediately, updates inventory immediately
- **Pay in Cash** → dialog: shows live Safe + Cashier balances, pick fund source, payment method (Cash/Check/GCash/Maya), creates expense, deducts fund, updates inventory immediately

**New PO fields added:**
- DR / Reference # — supplier's delivery receipt number
- Unit column in line items (Box, Sack, etc.)
- Per-line discount (₱ or % toggle per row)
- Overall PO discount (₱ or %)
- Freight / Shipping Cost (optional toggle)
- VAT (optional toggle, configurable rate e.g. 12%)
- Grand Total computed from: subtotal → line discounts → overall discount → freight → VAT

**PO List improvements:**
- Filter chips: All | Draft | Ordered | Received | Unpaid
- Split badges: Receive status + Payment status separately
- DR# column, Grand Total column
- Draft POs show "Draft — pending" in payment column (no confusing badge)
- Quick Receive button for draft/ordered POs inline

**Pay Supplier tab:**
- Live Safe + Cashier balance cards (click to select fund source)
- Payment method selector: Cash/Check/GCash/Maya/Bank Transfer
- Check number field appears when Check is selected
- Balance shortfall warning per payment amount entered

**Backend changes (purchase_orders.py):**
- `_apply_po_inventory()` helper — shared receive logic (both create and receive endpoint)
- `_get_fund_balances()` helper — returns cashier + safe balances
- `GET /fund-balances?branch_id=` — new endpoint for live balance display
- `create_purchase_order`: handles `po_type: draft|cash|terms`, all new fields, validates fund balance before deducting
- `receive_purchase_order`: simplified to use shared helper
- `pay_purchase_order`: updated to use `grand_total` (not just subtotal)

**Connections (what this affects):**
- Expenses: cash PO creates expense "Purchase Payment" → shows in daily expenses/Z-report
- Payables: terms PO creates payable → visible in Pay Supplier + Accounting page
- Inventory: both cash and terms update stock immediately on creation
- Product cost: receiving updates cost_price and moving_average_cost
- Movement log: "purchase" type movement logged
- Dashboard: supplier payables widget shows due dates

**Testing: 53/53 backend tests pass · 95% frontend flows verified**

### P0 Reports (AR Aging, Sales, Expense) - COMPLETE ✅ (Feb 2026)

**3 new report endpoints in `backend/routes/reports.py`:**
- `GET /api/reports/ar-aging` — Open invoices bucketed by age (0-30, 31-60, 61-90, 90+ days), grouped per customer with expandable invoice detail. Branch filter. Returns as_of_date, totals, rows.
- `GET /api/reports/sales` — Sales totals by category, daily breakdown, per-transaction list. Filters: date_from, date_to, branch_id. Returns grand_total, categories (with by_payment breakdown), daily array, transactions.
- `GET /api/reports/expenses` — Expenses by category with progress bars, daily breakdown, per-transaction detail. Filters: date_from, date_to, branch_id, category. Returns grand_total, categories, daily, expenses.

**Frontend `ReportsPage.js` at `/reports`:**
- Tabbed UI (AR Aging / Sales Report / Expense Report)
- AR Aging: KPI cards per bucket, Customer Aging Detail table, expandable rows per customer showing invoice-level detail (invoice#, date, days old, balance, due date), print-friendly output
- Sales Report: KPI cards (Total, Cash, Credit, Category count), Summary view (by-category table with cash/credit split + % of total), Daily Sales table, Transactions view (per-invoice list with status badges), date range filters
- Expense Report: KPI cards (Total, Count, Categories, Largest Category), Summary view (category table + progress bar share visualization), Daily Expenses table, Detail view (per-transaction with employee/description), category filter dropdown
- All three reports have Print button that opens a formatted print window
- Reports nav link added to sidebar (BarChart3 icon, under Daily Operations, perm: reports.view)

**Testing: 34/34 backend tests pass · 100% frontend flows verified by testing agent**

### Terminology Rename (AgriPOS → AgriBooks) + Branch Transfer Print - COMPLETE ✅ (Feb 2026)
**Renamed across the entire frontend:**
- Brand: AgriPOS → **AgriBooks**; Subtitle: "Inventory & POS" → "Business Management"
- "Cashier Drawer" / "Cash Drawer" → **Operating Fund**
- "Starting Cashier Float" / "Starting Float" → **Opening Float**
- "Left in Register" → **Opening Float (Next Day)**
- "Transferred to Safe" / "Transfer to Safe" → **Transferred to Vault** / **Transfer to Vault**
- "Cash Sales" → **Walk-in Sales**
- "POS Sale" → **Sales Transaction**
- "Cash Count" → **Actual Count**; "Cash Register" references → removed
- HTML title, manifest, PWA icons all updated to AgriBooks

**Branch Transfer Print** (QuickBooks-style layout):
- Print button on every Branch Transfer Order (draft, sent, received)
- Opens in new window with professional print layout: company header, from/to branch, items table (Product, Transfer Capital, Total, Recommended Retail), signature lines for Prepared/Released/Received


**Inter-branch supply system with 3-price model and automatic price propagation.**

**3 prices per product:**
- Branch Capital = Main branch's cost (read-only reference)
- Transfer Capital = Branch Capital + category markup (suggested, fully editable per row)
- Branch Retail = Branch's selling price to customers (auto-filled from memory, editable)

**Features:**
- Category Markup Rules panel — set per-category add-on (fixed ₱ or % of capital), saved as default template per destination branch
- Price memory — auto-fills Branch Retail from last transfer to that branch
- Validation: RED + blocked if Transfer Capital > Branch Retail OR margin < configurable min (default ₱20)
- Admin override with reason (for near-expiry, etc.)
- History tab with status (draft → sent → received)
- Receive dialog — branch can adjust actual quantities received
- On confirm receipt: inventory deducted from source, added to destination, `branch_prices` updated (transfer_capital = cost, branch_retail = retail), price memory updated

**Backend endpoints:** `/branch-transfers` (CRUD, send, receive, markup-template, product-lookup)
**Collections:** `branch_transfer_orders`, `branch_transfer_templates`, `branch_transfer_price_memory`


**Code fixes:**
- Fixed N+1 query in `sales.py` — batch-fetches all products before the loop (eliminates N DB calls per sale item)
- Added MongoDB text index on products (name + sku + barcode) for fast search at scale
- JWT_SECRET startup warning if < 32 chars
- Replaced external Pexels login image with local `/public/login-bg.jpg`
- Removed "Default: admin / admin123" hint (now dev-only via `NODE_ENV`)

**Backup system:**
- `backend/services/backup_service.py` — mongodump → gzip archive → upload to Cloudflare R2 (falls back to local if R2 not configured)
- `backend/routes/backups.py` — API: POST /backups/create, GET /backups/list, POST /backups/restore/{filename}
- APScheduler wired into main.py — runs daily at configurable hour (default 1:00 AM)

**Docker deployment files:**
- `backend/Dockerfile` — Python 3.11 slim + MongoDB tools (for mongodump)
- `frontend/Dockerfile` — 2-stage (Node 18 build → nginx 1.25 serve)
- `frontend/nginx.conf` — serves React SPA + proxies /api to backend + gzip + caching
- `docker-compose.yml` — orchestrates MongoDB + Backend + Frontend with health checks
- `.env.production` — template with all required variables
- `backend/.dockerignore` + `frontend/.dockerignore`
- `DEPLOYMENT.md` — step-by-step guide (Hostinger VPS setup, Cloudflare DNS, R2 backup, maintenance)

**Deploy command (on VPS):**  `docker compose up -d --build`


- New `_compute_inventory_value(branch_id)` function in dashboard.py — aggregates quantity × cost_price (capital) and quantity × retail_price for all non-repack products with stock > 0
- Handles mixed-case retail price key (`retail` vs `Retail` from QB import)
- Returns: capital_value, retail_value, potential_margin, margin_pct, sku_count_in_stock
- **Owner Dashboard**: Branch cards now show "Stock @ Capital" and "Stock @ Retail" per branch
- **Branch Dashboard**: "Inventory Value" card with 4 metrics: Capital, Retail, Potential Margin, Margin %


**Dashboard (DashboardPage.js) - complete redesign:**
- **Owner View**: Date/day header, Total Sales Today, Total Cash Position, Outstanding AR, Low Stock Alerts. Branch cards show: Cash Sales/New Credit/Cashier+Safe/AR Outstanding/Last Close Date/Low Stock. Supplier Payables with due dates (red when urgent).
- **Branch View**: 6 KPI cards (Cash Sales, New Credit, AR Collected, Expenses, Net Cash Flow, Transactions); Cash Position card (Cashier + Safe + Total); AR Aging bars (0-30/31-60/61-90/90+) + Top Debtors; Credit Extended Today (who got credit, how much, balance); AR Payments Received Today; Unpaid POs with due dates (OVERDUE/DUE SOON/UPCOMING labels); Last close date + unclosed day alert.

**Z-Report (DailyLogPage.js + daily_operations.py):**
- New "New Credit Extended Today" section: lists every customer who got credit today (credit sales + cashouts + farm) with invoice#, amount, balance, type badge
- New "AR Balance at Close" section: running total outstanding AR at the time of closing
- Stored fields in daily_closings: `credit_sales_today`, `ar_credits_today`, `total_new_credit`, `total_ar_at_close`

**Close Wizard Step 3 (CloseWizardPage.js):**
- New expandable "Receive Payment for a Customer" panel — search any customer with outstanding AR, see their open invoices, click Receive on any invoice

**Bug fixed**: `dashboard/stats` was summing ALL branches' cashier wallets instead of the selected branch only.


- Added "Z-Report Archive" tab to Daily Operations page
- Shows all past closed days in a sortable table: Date, Branch, Cash Sales, AR Collected, Expenses, Over/Short, Closed By
- Branch filter + date search filter (admin sees all branches, others see their branch)
- Summary stats bar: total closed days, total cash sales, total AR collected, net over/short
- "View" button on each row opens the full Z-report in a dialog using the existing ZReport component
- Print button on the dialog


**Stress test covered all 3 branches simultaneously:**
- 61/61 backend tests pass, all transaction types verified
- Inventory deductions verified per branch (ENERTONE, Lannate, VITMIN, VOLPLEX, PLATINUM)
- AR balances correct after credit sales across all branches
- Offline sync working (14 products, 10 customers, 4 stock records synced)
- Supplier payables showing URGENT badge for 3-day due PO (PILMICO)
- Close wizard navigable for all branches

**CRITICAL BUG FIXED: payment_method case mismatch**
- Root cause: `UnifiedSalesPage.js` sent `payment_method: 'Cash'` (capital C) but `daily_operations.py` queried `'cash'` (lowercase) → all cash sales showed ₱0 in Z-reports
- Fixed in 3 layers: (1) frontend now sends lowercase, (2) `log_sale_items` in helpers.py normalizes to lowercase, (3) `daily_operations.py` uses case-insensitive `$regex` as safety net
- Z-report `total_cash_sales` now correctly shows ₱12,800 across all branches


**8-step guided close wizard at `/close-wizard`:**
1. Sales Log — sequential cash+credit sales, Quick Add Sale, Full Panel link
2. Customer Credits — credit invoices, cashouts, farm services grouped
3. AR Payments — balance-before, interest, penalty, amount paid, balance remaining; Quick Receive Payment
4. Expenses — today's expenses with employee advance monthly total notice; Quick Add Expense
5. Cash Count — expected vs actual, dynamic over/short indicator
6. Fund Allocation — safe/drawer split, auto-updates when actual cash changes
7. Close & Sign Off — Z-Report summary, manager/owner PIN sign-off, Close Day button
8. Open Tomorrow — confirmation that new transactions will auto-date to tomorrow (backend handles this)

**Two 1-Click Reports (header buttons, always accessible):**
- Low Stock Alert — all products with branch inventory history that are at 0 or below reorder point
- Supplier Payables — all unpaid POs, sorted overdue→urgent→pending, red badge when <7 days due

**Backend: 2 new endpoints in `daily_operations.py`:**
- `GET /api/low-stock-alert?branch_id=` — products ever stocked in branch now at/below reorder
- `GET /api/supplier-payables?branch_id=` — all unpaid POs with urgency flags


- Added `edit_cost` action to `products` permission module (backend `models/permissions.py`)
- Role presets: admin=true, manager=true, cashier=false, inventory_clerk=true
- Backend `PUT /products/{id}` now raises 403 if `cost_price` is submitted without `products.edit_cost` permission
- Frontend `ProductsPage.js` and `ProductDetailPage.js`: Cost Price / Capital field disabled + "locked" indicator when user lacks permission; price scheme fields remain fully editable
- Admin and manager can still edit prices freely; only cost/capital is gated separately


**3 bugs fixed in UserPermissionsPage + SettingsPage:**
1. **Double-toggle**: `<label>` wrapping Radix Switch caused `onCheckedChange` to fire twice (label click forwarded to input + Switch's own handler). Fixed by replacing `<label>` with `<div>` and adding `e.stopPropagation()` on Switch click. Applied to both UserPermissionsPage and SettingsPage TOTP controls.
2. **State mutation**: `handlePermissionToggle` did `{ ...prev }` shallow copy then mutated `prev[module][action]` directly. Fixed to deep-copy module: `{ ...(prev[module] || {}) }` before modifying.
3. **Wrong permissions editor**: SettingsPage had a hardcoded `PERMISSION_MODULES` with wrong keys (`pos` instead of `sales`, missing `count_sheets`, `purchase_orders`, wrong action names). Removed the broken dialog entirely. Permissions button now navigates to the correct `UserPermissionsPage`.
- Added `count_sheets` to UserPermissionsPage module icons.
### TOTP Dynamic PIN + Inventory Correction - COMPLETE ✅ (Feb 2026)

**TOTP (Google Authenticator) for Admin:**
- New `POST /api/auth/totp/setup` → generates TOTP secret + QR provisioning URI
- New `POST /api/auth/totp/verify-setup` → activates TOTP after confirmation
- New `GET /api/auth/totp/status` → returns enabled/verified status
- New `DELETE /api/auth/totp/disable` → disables TOTP
- New `POST /api/auth/verify-admin-action` → verifies via TOTP code or password fallback
- TOTP codes expire every 30 seconds; verification is server-side (offline use blocked)
- Fallback: admin's full login password accepted when authenticator is unavailable

**TOTP-Protected Actions Control Panel (Settings > Security):**
- Admin can configure which 9 sensitive actions require TOTP verification
- Stored in `system_settings` collection under key `totp_controls`
- Default protected: `inventory_adjust`, `close_day`

**Inventory Correction in Product Edit:**
- Collapsible "Inventory Correction" section in Edit Product dialog
- Admin applies correction directly (no TOTP prompt — already authenticated)
- Non-admin users must verify via TOTP or admin password
- Requires branch selection (disabled with warning in All Branches mode)
- Full audit log in `inventory_corrections` collection (old_qty → new_qty, reason, who, auth_mode)
- Recent corrections shown inline in the correction panel

**New files:**
- `frontend/src/components/TotpVerifyDialog.js` — shared TOTP verification dialog
- `backend/tests/test_totp_inventory_correction.py` — 27 tests, all passing

### Quick Repack Generator - Search & Warning Fixes - COMPLETE ✅ (Feb 2026)
- Fixed parent product search dropdown clipping in Quick Repack modal using React portal (`createPortal`) with `position: fixed`
- Added "⚠ has repack" indicator in search dropdown results for products that already have repacks
- Added toast warning when selecting a parent that already has a repack
- Added inline "⚠ Already has a repack" badge below selected parent in Quick Repack row


### Offline Download Progress Bar + Branch Isolation Fixes - COMPLETE ✅ (Feb 2026)

**1. Offline Data Pre-Download Widget (OfflineIndicator rewrite)**
- Step-by-step sync with progress bar: Connecting → Products → Inventory → Customers → Price Schemes
- 4 states: Never Synced (download button), Syncing (animated bar + %), Ready (green), Stale >4h (amber)
- Auto-triggers on login and on branch switch (inventory is branch-specific)
- Shows: last-synced time, branch name, product/customer/stock record counts

**2. IndexedDB Inventory Store (offlineDB.js DB v3)**
- Added `inventory` store keyed by `product_id`; new exports: `cacheInventory`, `getInventory`, `getInventoryItem`

**3. syncManager.js step-by-step progress**
- `refreshPOSCache(branchId)` emits named step events with pct 0-100

**4. Product Detail Page inventory bug fix**
- "Available" was using total across all branches → showing other branch's stock. Fixed to use current branch only.
- Backend `/products/{id}/detail` now accepts `branch_id` and filters coming/reserved per branch

**5. Count Sheet race condition + layout**
- `onBlur` on cases input skips save if focus moves to paired packs input (same product)
- Split input redesigned to single-row with unit labels above inputs

**6. Bug fixes from testing agent (3 pre-existing bugs)**
- `Stock by Branch` table was always empty — now uses `branches` from AuthContext (same pattern as Branch Pricing table)
- `COST ()` header showed blank method — changed `cost.method` to `cost.capital_method`
- Moving Average / Last Purchase showed ₱0 — backend now computes both from PO history and returns them in cost dict

**7. Offline Sync Enhancement — branch_prices cached**
- `/sync/pos-data` now returns `branch_prices` for the branch; IndexedDB DB v4 stores them keyed by product_id

**8. Import Center (`/import`)**
- .xlsx/.xls/.csv upload with drag-and-drop; QuickBooks auto-column detection
- Column mapper with presets; preview; results with skipped-duplicates checklist
- Inventory Seed (branch + admin PIN): sets initial quantities by product name match
- Downloadable CSV templates for both import types

**9. Quick Repack Generator (Products page header)**
- Live parent search autocomplete; single retail price → applied to ALL schemes
- Tab-friendly: Name → Unit → Qty per box → Add-on cost → Retail price → Generate

## Previous Updates (Feb 2026)

### Full Routing Audit + Receivables Fix - COMPLETE ✅ (Feb 2026)

**Critical bugs found & fixed:**
1. **Accounting Receivables Tab showed zero** — `GET /receivables` read from legacy empty `receivables` collection. Fixed to read from `invoices` collection (the real AR system). Now shows: farm expenses, credit sales, interest charges, cash outs — all with type badges.
2. **Payment on receivables was broken** — `POST /receivables/{id}/payment` now applies to invoices, updates customer balance and cashier wallet.
3. **Products category filter broken** — Fixed `/products/categories/list` → `/products/categories`.

**Audit result:** 32 frontend routes verified working. No other broken routes found.

### Purchase Order Overhaul + Pay Supplier + Statement of Account - COMPLETE ✅ (Feb 2026)

**PO Improvements:**
- Added `due_date` and `terms_days` to PO (auto-computes due date from terms)
- **Cash PO**: auto-creates expense record on save
- **Credit PO**: payment now also creates expense record
- **Cashier balance check before paying**: returns 400 with `cashier_balance`, `safe_balance`, `shortfall`; frontend shows amber warning + recommends switching to Safe
- `fund_source` parameter: pay from Cashier or Safe
- **Reopen PO**: `POST /{id}/reopen` reverses inventory addition, status back to "ordered" → edit → receive again (self-correcting negative inventory pattern)
- Cancelled POs no longer show Pay button

**Pay Supplier Page (`/pay-supplier`):**
- Supplier list with total owed + Overdue badge
- QB-style per-PO payment inputs + auto-apply "Pay All"
- Fund source selector (Cashier/Safe) with live balance display
- Amber warning when selected fund is insufficient
- Check#/Reference field (required for Check payments)
- PO Detail dialog shows items, payment history

**Dashboard Unpaid PO Widget:**
- Both single-branch and consolidated views
- Ranked: Overdue (red) → Due This Week (amber) → Upcoming
- Shows PO#, vendor, balance, due date

**Statement of Account (Customer):**
- Printer icon on each customer in Customers page
- Date range filter (From/To)
- Running balance column across all charges and payments
- Print button (browser print)
- **Employee Advance Expense**: Fixed `KeyError` when `branch_id` is missing (admin in "All Branches" view). Backend now returns clear 400 error. Frontend validates branch is selected before saving.
- **Interest Rate UI**: Clarified distinction between penalty rate (one-time %) and customer interest rate (stored in profile). Generate Interest button now disabled with explanation when customer has no interest rate set.

**What was built (QB-style payment page revamp):**
- **5 new backend endpoints** — all were previously missing:
  - `GET /customers/{id}/invoices` — all open items sorted: Penalty first → Interest → Regular (oldest first)
  - `POST /customers/{id}/generate-interest` — computes accrued interest, creates `INT-XXXXXXXX-XXXX` invoice per invoice breakdown
  - `POST /customers/{id}/generate-penalty` — applies flat % penalty to overdue invoices, creates `PEN-` invoice
  - `POST /customers/{id}/receive-payment` — QB-style multi-invoice allocation: `[{invoice_id, amount}]`
  - `GET /customers/{id}/payment-history` — full payment trail across all invoices

- **Frontend PaymentsPage.js** complete rewrite:
  - Customer list with balance display
  - Payment header: date, method, check#/reference, memo
  - **Per-row payment inputs** — each open invoice has its own editable "Amount" column
  - **Auto-apply button** — fills row amounts by rule (penalty → interest → oldest invoice)
  - **"Pay All" button** — one click to pay full balance
  - Running totals: Amount to Apply vs Total Balance Due
  - Allocation preview chips (what gets applied where)
  - **Collapsible charges section**: Generate Interest (with accrued preview breakdown), Generate Penalty (configurable %)
  - Payment History dialog with total received footer

**Accounts Page (`/accounts`) — Admin Only**
- Full user management table: create, edit, activate/deactivate users
- Role badges: Admin, Branch Manager, Cashier, Inventory Clerk
- Branch assignment per user (locked selector for non-admins)
- **Manager PIN management**: Admin can set/clear 4-6 digit PIN for any user via `PUT /users/{id}/pin` (with audit trail)
- Stats cards by role, search filter

**Enhanced Employee Section (`/employees`)**
- Full profile: position, employment type (regular/contractual/daily/probationary), branch, hire date, salary, daily rate
- Government IDs: SSS, PhilHealth, Pag-IBIG, TIN
- Emergency contact
- **Monthly CA Limit** per employee with enforcement + rollover tracking
- **Employee detail modal**: Profile tab + Cash Advances tab
  - CA tab: this-month total, monthly limit, remaining, progress bar, previous-month overage note
  - Salary deduction recording reduces `advance_balance`

**Employee Advance → Accounting Integration**
- Selecting "Employee Advance" in expense form reveals employee picker + CA summary panel
- If `this_month_total + new_amount > monthly_ca_limit` → requires **manager PIN** (same flow as credit sale approval)
- Saves `employee_id`, `employee_name` to expense; auto-updates `advance_balance`

**Admin/Manager PIN Bypass (Sales)**
- Credit and partial sales by admin/manager users no longer show the PIN dialog — auto-approved
- **Scheme selector always visible**: Not locked to customer's stored scheme — can override per transaction
- **Walk-in**: Scheme selector changes `defaultScheme` (session memory) + reprices cart immediately
- **With customer**: Scheme selector defaults to customer's stored scheme; changing it triggers "Update Customer Scheme?" dialog
  - "No, this sale only" — applies override for this transaction; shows "Override" badge next to balance/limit
  - "Yes, update customer" — persists via `PUT /api/customers/{id}` with toast confirmation
- **Auto-repricing**: Switching scheme reprices all open cart items (Quick) and line items (Order) instantly
- **New customer**: Created from sales page with chosen scheme → applies immediately
- **Order mode product click fixed**: SmartProductSearch dropdown now uses `position:fixed` + `onMouseDown` to escape `overflow:hidden` table container clipping
- **Order mode UX improved**: Shows product name as text after selection (not empty search box), X button to clear the line
- **Pricing consistency**: Both Quick and Order modes use the same price logic (`defaultScheme` for walk-in)
- **Zero-price protection**: If selected price scheme has no price for a product, shows ₱0.00 with warning; checkout is blocked until price is manually set
- **Below-capital protection**: Checkout blocked if any item's price < cost price (frontend validation mirrors backend)
- **Editable quantity in Quick mode**: Number input instead of just +/- buttons
- **Editable price in Quick mode**: Price is a direct number input; color-coded warnings for zero/below-cost prices
- **Price Save Dialog**: When price is changed in either mode, a dialog offers to permanently save the new price to the product's scheme (`PUT /api/products/{id}/update-price`)

### Company Setup Wizard - COMPLETE ✅ (Dec 20, 2025)
First-time setup wizard that walks new users through:
- **Step 1: Company Info** - Name, address, phone, email, tax ID, currency
- **Step 2: First Branch** - Branch name and location details
- **Step 3: Admin Account** - Username, password, manager PIN
- **Step 4: Opening Balances** - Cashier drawer, safe, and bank account starting balances

Key Features:
- Auto-detects fresh installation (no users/branches)
- Redirects to setup wizard if system is uninitialized
- Creates fund wallets with opening balances
- Sets up safe lots for accurate cash tracking
- System reset endpoint for testing

New Endpoints:
- `GET /api/setup/status` - Check if setup is needed
- `POST /api/setup/initialize` - Complete system setup
- `POST /api/setup/reset` - Reset all data (dangerous)
- `GET /api/setup/defaults` - Get default options

### Multi-Branch Frontend Integration - COMPLETE ✅ (Dec 20, 2025)
- **Owner Dashboard**: Consolidated view showing all branches with KPIs
  - Total Sales Today, Total Cash Position, Total Receivables, Low Stock Alerts
  - Branch Performance Grid with individual branch stats
  - Top Performing branches ranked, Alerts per branch
- **Branch Selector**: Admin can switch between "All Branches" and specific branch
- **Auto Branch Filtering**: API calls auto-append branch_id via axios interceptor
- **Branch-Locked Users**: Cashiers see only their assigned branch (locked selector)

### Count Sheets Feature - COMPLETE ✅ (Dec 20, 2025)
Inflow-style inventory verification and adjustment system:
- **Snapshot**: Captures system inventory at point in time
- **Split Counting**: Displays/inputs as "9 boxes + 50 tablets" for fractional qty
- **Category Grouping**: Items sorted alphabetically by category
- **Strict Mode**: All items must be counted before completion
- **One Active**: Only one count sheet per branch at a time
- **Adjustments**: Apply variances to inventory with full audit trail

### Backend Modular Refactor - COMPLETE ✅
- Migrated from 3800-line monolith to 18 modular route files
- Entry: `server.py` → `main.py` (all routers)
- Multi-branch data isolation verified

## What's Been Implemented

### Phase 10: Granular Permission System (Feb 19, 2026) ✅
**Inflow Cloud-style user permission management - COMPLETE**

Features:
- **User Permissions Page** (`/user-permissions`)
  - Left panel: User list with role badges (admin, manager, cashier, etc.)
  - Right panel: Permission editor with toggles for each action
  - Click user to select and load their permissions

- **Permission Modules** (12 modules, 53 total permissions)
  - Dashboard, Branches, Products, Inventory
  - Sales/POS, Purchase Orders, Suppliers, Customers
  - Accounting, Price Schemes, Reports, Settings

- **Per-Action Toggles**
  - Each module has specific actions: view, create, edit, delete
  - Special permissions: view_cost, sell_below_cost, give_discount, void, manage_credit, etc.

- **Role Presets**
  - Administrator: Full access to everything
  - Branch Manager: Manage branch ops, limited admin
  - Cashier: POS operations only
  - Inventory Clerk: Stock management focus
  - Custom: Manual per-user configuration

- **Quick Actions**
  - "None" button: Disable all permissions for a module
  - "All" button: Enable all permissions for a module
  - "Apply Preset" dropdown: Apply predefined role

- **Unsaved Changes**
  - Yellow banner shows pending changes
  - Discard/Save buttons for user confirmation

New Endpoints:
- `GET /api/permissions/modules` - All permission modules with actions
- `GET /api/permissions/presets` - All role presets
- `GET /api/permissions/presets/{key}` - Specific preset details
- `GET /api/users/{id}/permissions` - User's current permissions
- `PUT /api/users/{id}/permissions` - Update all permissions
- `PUT /api/users/{id}/permissions/module/{module}` - Update specific module
- `POST /api/users/{id}/apply-preset` - Apply preset to user

### Phase 9: Invoice Editor Feature (Feb 19, 2026) ✅
- QuickBooks-style invoice viewer/editor with audit trail
- Edit with mandatory reason, creates edit history
- Inventory auto-adjustment on quantity changes

### Phase 8: Interest & Penalty Enhancement (Feb 19, 2026) ✅
- Grace period support, auto-preview charges
- Simple daily interest formula

### Phase 7: Unified Sales System (Feb 19, 2026) ✅
- Combined Quick POS + Sales Order workflow
- Cash, Partial, Credit payment options
- Manager PIN approval for credit sales

### Previous Phases ✅
- Customer Transaction History
- Dashboard with Combined Receivables
- Offline POS with IndexedDB + auto-sync
- Purchase Orders with receiving + cost updates
- Fund Management (Cashier, Safe, Bank wallets)
- Daily Operations (Sales log, profit report, day close)
- Supplier Management with transaction history
- Parent/Repack inventory system

## Current File Structure (Modular Architecture)
```
/app
├── backend/
│   ├── server.py          # Entry point (imports from main.py)
│   ├── main.py            # FastAPI app with all routers
│   ├── config.py          # Centralized configuration
│   ├── server_legacy.py   # Old monolith (backup)
│   ├── ARCHITECTURE.md  
│   ├── utils/
│   │   ├── __init__.py    # Exports all utilities
│   │   ├── auth.py        # Auth: JWT, password hashing, permissions
│   │   ├── helpers.py     # now_iso, new_id, log_movement, etc.
│   │   └── branch.py      # Multi-branch: get_branch_filter, etc.
│   ├── models/
│   │   ├── __init__.py
│   │   └── permissions.py # PERMISSION_MODULES, ROLE_PRESETS
│   ├── routes/            # All API routes (17 modules)
│   │   ├── __init__.py    # Exports all routers
│   │   ├── auth.py        # Login, register, PIN verification
│   │   ├── branches.py    # Branch CRUD
│   │   ├── users.py       # User management, permissions
│   │   ├── products.py    # Products, repacks, pricing
│   │   ├── customers.py   # Customer CRUD with branch support
│   │   ├── inventory.py   # Stock levels, adjustments, transfers
│   │   ├── price_schemes.py # Price scheme management
│   │   ├── invoices.py    # Invoices, payments, interest, editing
│   │   ├── sales.py       # Unified sales endpoint
│   │   ├── purchase_orders.py # PO CRUD, receiving, payments
│   │   ├── dashboard.py   # Stats, branch summary
│   │   ├── accounting.py  # Fund wallets, expenses, AR/AP
│   │   ├── daily_operations.py # Daily log, report, close day
│   │   ├── suppliers.py   # Supplier CRUD
│   │   ├── employees.py   # Employee management, advances
│   │   ├── sync.py        # Offline POS data sync
│   │   └── settings.py    # Invoice prefixes, terms options
│   ├── tests/
│   └── .env
└── frontend/
    └── src/
        ├── components/
        ├── pages/
        └── App.js
```

## Default Credentials
- Username: admin
- Password: admin123
- Manager PIN: 1234

## Prioritized Backlog (Updated Feb 19, 2026)

### P0 (Critical - Completed) ✅
- [x] **Granular Permission System** (Inflow Cloud style)
- [x] **Invoice Editor** with audit trail
- [x] **Interest & Penalty with Grace Period**
- [x] **Unified Sales Interface**
- [x] **Customer Transaction Tracking**

### P1 (High Priority - Next)
- [x] **Backend Modular Refactoring - COMPLETE** (Dec 2025)
  - Created modular foundation: config.py, utils/, models/, routes/
  - Extracted ALL routes into 17 modular files
  - main.py orchestrates all routers
  - server.py is now a thin entry point
  - Old monolith backed up as server_legacy.py
  - Total: 17 route modules with 80+ endpoints
  - All modules tested and working
  
- [x] **Multi-Branch Data Isolation - COMPLETE** (Dec 2025)
  - Branch utilities in utils/branch.py
  - Branch filtering on all relevant endpoints
  - Dashboard shows multi-branch view for admin
  - /dashboard/branch-summary for owner overview
  - Cashier sees only their branch data

### P2 (Medium Priority)
- [ ] Advanced Reporting Dashboards
- [ ] Barcode scanning support
- [ ] Receipt printing (thermal)
- [ ] Bulk Import/Export (CSV)

### P3 (Future)
- [ ] Stock alerts and notifications
- [ ] Multi-currency support
- [ ] Mobile app API
- [ ] Audit trail / activity logs

## Key API Endpoints
- `GET /api/permissions/modules` - All permission modules
- `GET /api/permissions/presets` - Role presets
- `PUT /api/users/{id}/permissions` - Update permissions
- `POST /api/users/{id}/apply-preset` - Apply preset
- `GET /api/invoices/{id}` - Invoice with edit history
- `PUT /api/invoices/{id}/edit` - Edit invoice with reason
- `GET /api/customers/{id}/charges-preview` - Preview interest/penalty
- `POST /api/unified-sale` - Create sale (cash/partial/credit)
- `POST /api/auth/verify-manager-pin` - Verify manager PIN

## Testing Status
- **Full Regression (Dec 2025)**: 100% pass - All 21 features verified
  - Multi-branch Owner Dashboard working
  - Branch selector for admin (locked for cashier)
  - All 17+ pages loading correctly
  - API integration fixes applied (AccountingPage, SalesPage)
- **Test reports**: /app/test_reports/iteration_20.json (latest)

## Upcoming Tasks (P1)
- **Robust Offline Sync**: Transaction Envelope (local_id, device_id), idempotent sync endpoint, conflict resolution
  
## Future Tasks (P2)
- **Comprehensive Audit System**: Audit trail for price overrides, inventory adjustments, invoice edits
- **Real-Time Owner Visibility**: Pre-computed daily summaries, WebSockets for live updates
- **User Roles & Presets**: Reusable role templates (e.g., "Branch Manager")
- **Advanced Reporting**: Monthly/quarterly summaries, sales incentive tracking
- **Bulk Data Import/Export**: CSV import/export for products
