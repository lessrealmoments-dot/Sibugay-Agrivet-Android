# AgriBooks PRD

## Original Problem Statement
Full-stack POS, Inventory, and Accounting platform for Philippine retail businesses.

## Core Architecture
- **Frontend:** React + Shadcn/UI + Tailwind
- **Backend:** FastAPI + MongoDB
- **3rd Party:** Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode

## What's Been Implemented

### Accounts Receivable (AR) Module
- Fixed & enhanced "Find & Pay" panel in CloseWizardPage
- Redesigned PaymentsPage to QuickBooks-style layout
- Discount functionality for interest/penalties
- Inline interest rate configuration (set on-the-fly, save to profile)

### Expense Fund Source Routing (2026-03-12)
- **Fixed:** Payment method now correctly routes to the right wallet
  - Cash/Check → Cashier Drawer (fund_source: "cashier")
  - GCash/Maya/Bank Transfer/Credit Card → Digital Wallet (fund_source: "digital")
  - Cash (from Safe) → Safe (fund_source: "safe")
- Updated all 4 expense endpoints: regular, farm, customer cashout, employee advance
- Helper functions: `derive_fund_source()`, `deduct_from_fund_source()` in accounting.py
- Daily close preview now correctly separates expenses by fund source (cashier, safe, digital)
- Expected counter formula only subtracts cashier expenses from drawer balance
- Frontend shows fund source indicator on expense rows

### Sales History Enhancement (2026-03-12)
- **Removed date dependency** — shows ALL sales with proper pagination (25/page)
- **Sortable columns:** Sale #, Customer, Total, Date (click to toggle asc/desc)
- **Search:** by invoice number or customer name
- **Filter chips:** All, Paid, Partial, Credit, Voided
- **Pagination:** First/Prev/Next/Last with page counter
- **Matches PO page pattern** — consistent UX across the app

### PIN Security Fixes (2026-03-12)
- **SalesOrderPage credit PIN enforcement:** Credit saves now require manager PIN dialog
- **Manager PIN branch restriction:** Manager PINs now only work on their assigned branch. Admin PIN, TOTP, and Auditor PIN still work across all branches.
- **Backend `verify_pin_for_action`** accepts optional `branch_id` for branch-aware verification

### Date Editing for PO & SO (2026-03-12)
- **Invoice/SO edits** now support `order_date` and `invoice_date` changes
- **PO edits** now support `purchase_date` changes
- **Closed-day validation:** Cannot change a date to one that's already been closed
- **Closed-day edits:** Editing a transaction from a closed day requires manager PIN; financial changes auto-create a journal entry
- **SaleDetailModal** shows date input in edit mode with closed-day warnings
- **PO Detail** shows date input in edit mode

## Prioritized Backlog

### P1 (Upcoming)
- Visual "trail" indicator for partial invoices receiving same-day payments
- Implement "Smart Journal Entries"
- Research over-limit Cash Advances logic
- Investigate "Closing History" page need
- Convert app to PWA
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway
- "Demo Login" System

### P2 (Future)
- Unify and refactor remaining subpar UI modules
- Fix 3 remaining `react-hooks/exhaustive-deps` eslint warnings
- Create admin tool to fix broken Purchase Orders in DB
- "Weigh & send" mode for phone scanner
- Kiosk Mode for POS
- Advanced Reporting on barcode scan history
- User Roles & Presets
- "Pack & Ship" Workflow
- Smarter Price Suggestions
- Refactor SuperAdminPage.jsx (>1000 lines monolith)
- Fix AdminLoginPage.jsx window.location.href → useNavigate

## Key Files Modified This Session
- `frontend/src/pages/SalesPage.js` — Full rewrite
- `frontend/src/pages/SalesOrderPage.js` — Added PIN dialog
- `frontend/src/components/SaleDetailModal.js` — Added date editing
- `frontend/src/pages/PurchaseOrderPage.js` — Added date editing
- `backend/routes/invoices.py` — Enhanced list, date editing, journal entry
- `backend/routes/verify.py` — Branch-aware PIN verification
- `backend/routes/auth.py` — Pass branch_id to PIN verification
- `backend/routes/purchase_orders.py` — Date editing with closed-day check

## Test Reports
- `/app/test_reports/iteration_7.json` — Expense fund source (prev session)
- `/app/test_reports/iteration_106.json` — Sales History + PIN fixes (100% pass)
