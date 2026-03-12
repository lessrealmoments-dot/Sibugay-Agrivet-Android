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

## Prioritized Backlog

### P0 (Immediate)
- User verification of expense fund routing changes

### P1 (Upcoming)
- Visual "trail" indicator for partial invoices receiving same-day payments
- Implement "Smart Journal Entries"
- Research over-limit Cash Advances logic
- "Quick-action menu" on Sales History page
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
- Advanced barcode scan reporting
- User Roles & Presets
- "Pack & Ship" Workflow
- Smarter Price Suggestions

### Refactoring
- SuperAdminPage.jsx: Monolithic (>1000 lines), needs breakdown
- AdminLoginPage.jsx: Uses `window.location.href` instead of `useNavigate`

## Key Files
- `backend/routes/accounting.py` - Expense creation, AR, fund routing
- `backend/routes/daily_operations.py` - Daily close preview, expected counter
- `backend/utils/helpers.py` - Wallet update helpers
- `frontend/src/pages/ExpensesPage.js` - Expense UI
- `frontend/src/pages/CloseWizardPage.js` - Close wizard
- `frontend/src/pages/PaymentsPage.jsx` - AR payments

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Company Admin: jovelyneahig@gmail.com / Aa@050772
- Manager PIN: 521325
