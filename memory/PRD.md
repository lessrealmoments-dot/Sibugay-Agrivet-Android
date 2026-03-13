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
- Payment method correctly routes to the right wallet (cashier/digital/safe)
- Updated all 4 expense endpoints
- Daily close preview correctly separates expenses by fund source

### Sales History Enhancement (2026-03-12)
- Removed date dependency — shows ALL sales with pagination (25/page)
- Sortable columns: Sale #, Customer, Total, Date
- Search by invoice number or customer name
- Filter chips: All, Paid, Partial, Credit, Voided
- **Quick Action menu** on every row: View Details, Print Receipt (58mm), Print Full Page (8.5x11), Add Payment

### PIN Security Fixes (2026-03-12)
- SalesOrderPage credit saves now require manager PIN dialog
- Manager PINs restricted to assigned branch only
- Backend `verify_pin_for_action` accepts optional `branch_id`

### Date Editing for PO & SO (2026-03-12)
- Invoice/SO and PO edits support date changes
- Closed-day validation prevents changing to closed dates
- Closed-day edits require PIN + auto-create journal entries

### Print System — Phase 1 (2026-03-13)
- **Business Info Settings** (Settings > Business Info tab): Business Name (required), Address, Phone, TIN, Receipt Footer, Trust Receipt Terms — all editable
- **Print Engine** (`lib/PrintEngine.js`): Shared utility generating print-ready HTML
  - 2 formats: Thermal (58mm) and Full Page (8.5x11)
  - 2 document types: **Order Slip** (cash sales) and **Trust Receipt** (credit/partial sales with legal clause)
- **Quick Action Menu** on Sales History rows: contextual print/view/payment actions
- **Trust Receipt** includes legally binding PD 115 terms and conditions with {business_name} placeholder

### Print Document Types
| Document | Thermal | Full Page | Auto-determined by |
|----------|:-------:|:---------:|-------------------|
| Order Slip | Yes | Yes | Cash/digital/split sales (balance = 0) |
| Trust Receipt | Yes | Yes | Credit/partial sales (balance > 0) |

## Prioritized Backlog

### P0 (Phase 2 Print — Next)
- Wire print into Sale Detail Modal (print button)
- Wire print into POS checkout (auto-prompt or button)
- Add print to PO detail, Z-Report, Returns
- Full-page templates for: Purchase Order, Stock Transfer Slip, Expense Voucher, Return Slip, Statement of Account

### P1 (Upcoming)
- Visual "trail" indicator for partial invoices with same-day payments
- Smart Journal Entries
- Over-limit Cash Advances logic
- Closing History page
- Portable Android POS prep (stripped-down UI: PO + Sales only)

### P2 (Future)
- PWA conversion
- Weight-embedded EAN-13 barcodes
- Automated Payment Gateway
- Demo Login System
- SuperAdminPage refactoring
- eslint warnings cleanup
- Admin PO fix tool

## Key Files
- `frontend/src/lib/PrintEngine.js` — Print engine
- `frontend/src/pages/SalesPage.js` — Sales History with Quick Action
- `frontend/src/pages/SettingsPage.js` — Business Info tab
- `backend/routes/settings.py` — Business info API
- `backend/routes/verify.py` — Branch-aware PIN verification
- `backend/routes/invoices.py` — Enhanced list + date editing

## Test Reports
- `/app/test_reports/iteration_106.json` — Sales History + PIN fixes (100%)
- `/app/test_reports/iteration_107.json` — Print System Phase 1 (100%)
