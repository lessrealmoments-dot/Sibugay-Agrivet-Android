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

### Multi-Branch Stress Test + Cash Sales Bug Fix - COMPLETE ✅ (Feb 2026)
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
