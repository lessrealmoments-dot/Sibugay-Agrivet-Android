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
- Inline interest rate configuration

### Expense Fund Source Routing (2026-03-12)
- Payment method correctly routes to the right wallet (cashier/digital/safe)

### Sales History Enhancement (2026-03-12)
- All sales with pagination, sortable columns, search, filter chips
- Quick Action menu: View Details, Print Receipt (58mm), Print Full Page (8.5x11), Add Payment

### PIN Security Fixes (2026-03-12)
- SalesOrderPage credit PIN enforcement
- Manager PINs restricted to assigned branch only

### Date Editing for PO & SO (2026-03-12)
- Invoice/SO and PO date changes with closed-day validation
- Closed-day edits require PIN + auto-create journal entries

### Print System — Complete (2026-03-13)

#### Phase 1: Foundation
- **Business Info Settings** (Settings > Business Info tab)
- **Print Engine** (`lib/PrintEngine.js`) — shared utility, 2 formats x 7 document types
- **Quick Action Menu** on Sales History rows

#### Phase 2: Wired Into All Sections
- **Sale Detail Modal** — 58mm and 8.5x11 print buttons
- **PO Detail Dialog** — Print button (Purchase Order format)
- **Expense Detail Modal** — Print button (Expense Voucher format)
- **Customer Statement Modal** — Upgraded to PrintEngine (Statement of Account format)
- **Z-Report / Close Wizard** — Already had window.print() + PDF download

#### Document Types & Formats
| Document | Thermal (58mm) | Full Page (8.5x11) | Where |
|----------|:-:|:-:|-------|
| **Order Slip** | Yes | Yes | Cash/digital sales |
| **Trust Receipt** | Yes | Yes | Credit/partial sales (with PD 115 legal terms) |
| **Purchase Order** | — | Yes | PO detail dialog |
| **Stock Transfer Slip** | — | Yes | Branch transfers |
| **Expense Voucher** | — | Yes | Expense detail |
| **Return Slip** | Yes | Yes | Returns |
| **Statement of Account** | — | Yes | Customer statement modal |

## Prioritized Backlog

### P1 (Upcoming)
- Visual "trail" indicator for partial invoices with same-day payments
- Smart Journal Entries
- Over-limit Cash Advances logic
- Closing History page
- Portable Android POS prep (stripped-down UI: PO + Sales only, with SDK integration)

### P2 (Future)
- PWA conversion
- Weight-embedded EAN-13 barcodes
- Automated Payment Gateway
- Demo Login System
- SuperAdminPage refactoring
- eslint warnings cleanup
- Admin PO fix tool

## Key Files
- `frontend/src/lib/PrintEngine.js` — Print engine (7 doc types)
- `frontend/src/pages/SalesPage.js` — Sales History + Quick Action
- `frontend/src/pages/SettingsPage.js` — Business Info tab
- `frontend/src/components/SaleDetailModal.js` — Print buttons
- `frontend/src/components/ExpenseDetailModal.js` — Print button
- `frontend/src/components/CustomerStatementModal.js` — Print via PrintEngine
- `frontend/src/pages/PurchaseOrderPage.js` — PO print button
- `backend/routes/settings.py` — Business info API
- `backend/routes/verify.py` — Branch-aware PIN verification
- `backend/routes/invoices.py` — Enhanced list + date editing

## Test Reports
- `/app/test_reports/iteration_106.json` — Sales History + PIN fixes (100%)
- `/app/test_reports/iteration_107.json` — Print Phase 1 (100%)
- `/app/test_reports/iteration_108.json` — Print Phase 2 (100%)
