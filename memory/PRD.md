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
- File uploads: Cloudflare R2 (agribooks-files bucket)
- Offline: IndexedDB (idb pattern), syncManager

## Key Formulas — CASH RECONCILIATION

### Expected Counter (Z-Report)
```
total_cash_in = cash_sales + partial_cash + cash_AR_only + split_cash_portion
expected_counter = starting_float + total_cash_in - cashier_expenses_only
```
- `cashier_expenses_only` = expenses WHERE fund_source != "safe"
- `cash_AR_only` = AR payments WHERE fund_source == "cashier"
- Safe-paid expenses and digital AR payments are tracked separately

### Fund Source Rules
- Every expense stores `fund_source` ("cashier" or "safe")
- Cashier expenses affect the drawer; safe expenses don't
- AR payments track fund_source from payment method (cash→cashier, GCash/Maya→digital)
- Z-Report only subtracts cashier-sourced expenses from expected counter

## Prioritized Backlog

### P0 — Completed
- [x] Mandatory e-payment receipt upload (digital/split sales)
- [x] Financial integrity overhaul (9+ bug fixes across payment pipeline)
- [x] **AUDIT FIX (Mar 2026):** Return void now ADDS money back (was double-deducting)
- [x] **AUDIT FIX (Mar 2026):** Daily close expected_counter uses cashier-only expenses
- [x] **AUDIT FIX (Mar 2026):** Daily close separates cash AR vs digital AR
- [x] **AUDIT FIX (Mar 2026):** Payable payment creates expense + updates linked PO
- [x] **AUDIT FIX (Mar 2026):** All expense types store fund_source (cashier/safe)
- [x] **AUDIT FIX (Mar 2026):** PO adjustment safe_lot has correct schema
- [x] **AUDIT FIX (Mar 2026):** Individual payment void handles digital wallets
- [x] **AUDIT FIX (Mar 2026):** Batch close uses same corrected formulas

### P0 — Completed (Mar 2026 — Usability)
- [x] Dedicated top-level Expenses page (/expenses) in sidebar under Transactions
  - New `ExpensesPage.js` with full CRUD, filters, Farm Expense, Customer Cash Out
  - Reuses same backend endpoints — no backend changes, zero regression risk
  - Error handling hardened for object-type API error responses
- [x] Clickable invoice/PO numbers across entire app
  - All invoice numbers in 8 pages now open InvoiceDetailModal (view + edit with PIN)
  - PO numbers on Dashboard navigate to Purchase Orders page
  - Pages: DailyLogPage, DashboardPage, AccountingPage, ExpensesPage, ReportsPage, AuditCenterPage
  - SalesPage and PaymentsPage already had this — verified no regression
- [x] Fix farm expense/cashout bugs (Mar 2026)
  - Toast notification now shows descriptive message with invoice number
  - Close Wizard and Daily Ops show farm expense description (what money was for)
  - Total Credit Extended Today uses `balance` instead of `grand_total` for partial payments
- [x] Employee Cash Advance quick action on Expenses page (Mar 2026)
  - New "Employee Cash Advance" button with violet styling alongside Farm Expense and Customer Cash Out
  - Dedicated dialog with employee selector, CA summary (monthly usage/limit/balance), amount, date, description
  - Manager PIN approval flow when monthly CA limit exceeded
  - Backend returns descriptive {expense, message} format
- [x] Employee name shown in expense summaries (Mar 2026)
  - Both Expenses page and Accounting page now display "Employee: [name]" in violet for Employee Advance expenses
  - Employee Advance category badge has violet styling
- [x] Farm Expense receipt upload (Mar 2026)
  - ReceiptUploadInline component added to Farm Expense dialog (desktop upload + phone QR)
  - "Skip & Upload Later" option with note about uploading in Closing Wizard or expense row
  - Backend farm endpoint now handles upload_session_ids to link receipt photos
- [x] Employee CA Summary Report (Mar 2026)
  - New "CA Summary" tab in Reports page with KPI cards + full employee table
  - Shows monthly usage vs limit, usage %, over-limit count (with approver info), prev month overage, unpaid balance
  - Z-Report/Close Wizard enhanced: shows OVER CA flag + "Approved by: [name]" on employee advances
  - Backend: GET /api/employees/ca-report with month and branch filters
  - All daily operations endpoints (daily-report, daily-log, daily-close-preview, daily-close) return is_over_ca, monthly_ca_limit fields
  - DailyLogPage: all 3 sections (mini report, full report advance_expenses, preview) show over-CA flag + limit + approver
  - daily-report endpoint enriches advance_expenses with CA data (was previously missing)

### P0 — Completed (Mar 2026 — System Audit)
- [x] Full system audit: 20 bugs found and fixed across 7 backend + 2 frontend files (Mar 2026)
  - BUG 1: Daily Log "Total Sales Today" double-counted partial payments → fixed grand_total = total_all
  - BUG 2: Z-Report Preview excluded partial payments from credit section → fixed query to include partial
  - BUG 3: Expense edit safe logic INVERTED (money flowed backwards) → swapped conditions
  - BUG 4: PO Pay balance used subtotal instead of grand_total → fixed to use grand_total
  - BUG 5: Audit cash reconciliation used ALL expenses (not cashier-only) → fixed to cashier-only
  - BUG 6: Expense edit didn't adjust employee advance_balance → added adjustment
  - BUG 7: Receivable payment ignored interest/penalties → aligned with invoice payment logic
  - BUG 8: Expense Report included voided expenses → added voided filter
  - BUG 9: Expense List API included voided expenses → added voided filter
  - BUG 10: Customer Transactions total included voided invoices → excluded voided
  - BUG 11: Close Wizard showed grand_total instead of balance for partial credit → fixed display
  - BUG 12: Daily Log AR section showed grand_total instead of balance → fixed display
  - BUG 13: Daily Report net_profit = gross_profit (misleading) → now subtracts real expenses
  - BUG 14: Receivable payment silently discarded overpayments → now rejects with error
  - BUG 16: Count Sheet moving avg used different source than PO receive → aligned to movements
  - BUG 19: Close starting float used yesterday only → now uses last closed date
  - BUG 20: Safe expense deductions had no record_safe_movement audit trail → added
- [x] Branch-specific supplier pricing system (Mar 2026)
  - PO receive no longer overwrites global product.cost_price — only writes to branch_prices
  - product_vendors.last_price is now branch-scoped (each branch tracks its own vendor prices)
  - New: GET /api/purchase-orders/vendor-prices — PO form auto-fills from vendor's last price
  - New: POST /api/suppliers/import-from-branch — copies supplier + pricing from another branch
  - New: GET /api/suppliers/available-for-import — lists importable suppliers from other branches
  - Frontend PO form: select supplier → loads vendor prices → auto-fills unit_price from history
- [x] Unified PIN verification across all sections (Mar 2026)
  - All PIN-protected actions now use centralized `_resolve_pin` from verify.py
  - Accepts: Owner PIN (system_settings), Manager PIN (user doc), TOTP (Google Authenticator), Auditor PIN
  - Fixed: auth.py verify-manager-pin, accounting.py fund transfers/reversals, daily_operations.py close, invoices.py void, returns.py void
- [x] Split/Partial payment tabs disabled without customer (Mar 2026)
  - Split, Partial, and Credit tabs now all require a customer to be selected before use
- [x] PIN Policy Configuration System (Mar 2026)
  - 23 PIN-protected actions across 9 modules (Sales, Fund Mgmt, Reversals, Daily Ops, Inventory, Products, PO, Audit, System)
  - 4 PIN methods: Owner PIN, Manager PIN, TOTP (Google Auth), Auditor PIN
  - Admin-only Settings UI: matrix of actions × methods with toggle buttons
  - New: GET/PUT /api/settings/pin-policies — CRUD for per-action PIN type policies
  - `_resolve_pin` now accepts `allowed_methods` filter; `verify_pin_for_action` loads policy per action
  - All endpoints updated: auth.py, accounting.py, daily_operations.py, invoices.py, returns.py, purchase_orders.py, uploads.py, verify.py, backups.py
  - 6 new PIN-enforceable actions: invoice edit, product delete, inventory adjust, price override, reopen PO, POS discount
  - Replaces old TOTP Controls section in Settings
- [x] Split payment decomposition in daily log (Mar 2026)
  - Split payments no longer appear as "Split" in payment method breakdown
  - Cash portion → "Cash", digital portion → platform name (e.g., "GCash")
  - sales_log entries store split metadata (split_cash_amount, split_digital_amount, split_digital_platform)
- [x] Capital injection in closing wizard expected counter (Mar 2026)
  - Expected counter now includes: capital injections, safe↔cashier transfers
  - Fund transfers displayed as separate line items in closing wizard
  - Fixed double-counting when no previous close (wallet balance already reflects all activity)
  - fund_transfers now store `date` and `target_wallet` fields
- [x] Smart Unclosed Date Detection + Date Picker (Mar 2026)
  - UnclosedDaysBanner component: detects unclosed days per branch, shows amber warning banner
  - Date selector dropdown: switch encoding date between Today and any unclosed past date
  - Integrated on Sales page (/sales-new) and Expenses page (/expenses)
  - Past date indicator: "All transactions will be saved to [date]" with highlighted amber button
  - Backend: sales_log entries now use order_date from request (not auto-detected get_active_date)
  - Backend: fund_transfer endpoint accepts optional `date` parameter
  - Backend: GET /api/daily-close/unclosed-days returns full list with per-day transaction counts
  - No formula changes — existing closing wizard works seamlessly with correctly-dated transactions
- [x] Audit Center Full Overhaul (Mar 2026)
  - Fixed cash reconciliation formula to match Closing Wizard: Starting Float + Cash In (Cash Sales + Partial Cash + Split Cash + Cash AR) + Net Fund Transfers - Cashier Expenses
  - Fixed starting float: reverse-calculated from wallet when no previous daily close exists (prevents misleading formula display)
  - Added missing components: partial cash, split cash, fund transfers (capital injection, safe↔cashier), digital AR separation
  - Detailed drill-down lists: expenses (with verified/unverified badge, receipt indicator, fund_source), AR payments (with fund_source, clickable invoices), fund transfers, partial/split invoices
  - New "Unverified Items" section: shows expenses, POs, AND digital payments (GCash/Maya) not verified by admin/auditor with receipt warnings
  - "Verify All" bulk action: batch-verify all unverified items with a single PIN entry via POST /api/audit/bulk-verify
  - Interactive receipt viewer: click "View receipt" to open ReceiptGallery dialog for expenses, POs, and invoices
  - Payables section enhanced with PO detail drill-down (PO numbers, vendor, overdue status, verification status)
  - Score summary grid includes new "Unverified" tile; overall audit score factors in unverified severity
  - Print report includes unverified items summary
  - Warning banner when no previous daily close found (starting float reverse-calculated)

### P0 — Upcoming
- [ ] Z-Report PDF: Include detailed breakdowns matching Closing Wizard UI (AR payments, fund transfers, expenses, etc.)
- [ ] Fix broken PO data (admin tool to reprocess failed POs)
- [ ] Quick-action menu on Sales History page (Re-send Receipt, Print Invoice)
- [ ] Closing History page (view past Z-Reports with search by date/branch)
- [ ] Cash Advances over-limit handling (deduct from next salary, reflect in reports)

### P1 — Upcoming
- [ ] Weight-embedded EAN-13 barcode recognition in POS
- [ ] Convert app to PWA (installable, offline-first)
- [ ] Demo Login System
- [ ] Automated Payment Gateway (Stripe/PayPal)

### P2 — Backlog
- [ ] Refactor SuperAdminPage.jsx (1000+ lines)
- [ ] Refactor AdminLoginPage.jsx (SPA navigation)
- [ ] Weigh & send mode for phone scanner
- [ ] Quick-action user details on Team page
- [ ] Kiosk Mode for POS
- [ ] Advanced Reporting on barcode scan history
- [ ] User Roles & Presets
- [ ] "Pack & Ship" Workflow
- [ ] Smarter Price Suggestions

## 3rd Party Integrations
- Cloudflare R2: File storage
- Resend: Transactional emails
- Google Authenticator: 2FA
- fpdf2: PDF reports
- python-barcode: Backend barcode generation
- jsbarcode: Frontend barcode rendering
- html5-qrcode: Camera barcode scanning
