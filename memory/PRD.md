# AgriBooks PRD

## Original Problem Statement
Build a full-featured POS (Point-of-Sale) system called **AgriBooks** with multi-tenant, multi-branch support. The system includes sales management, purchase orders, inventory, branch transfers, accounting, employee management, and more.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn UI
- **Backend:** FastAPI (Python) + MongoDB
- **Offline:** IndexedDB + Service Worker (PWA)
- **Storage:** Cloudflare R2

## What's Been Implemented

### Core POS (Complete)
- Multi-tenant org management, branch management, user roles & permissions
- Unified sales with walk-in/credit/consignment support
- Purchase orders, suppliers, branch transfers
- Inventory management, count sheets, barcode printing
- Customers, price schemes, branch-specific pricing
- Daily operations, close-of-day wizard, Z-reports
- Payments, fund management, expenses, accounting, journal entries
- Audit center, incident tickets, backups, reports
- Mobile barcode scanner, returns/refunds

### Budget Checker Kiosk Mode (Complete — Feb 2026)
- F1 to lock, Ctrl+Shift+U to unlock with PIN
- Product search, price display, budget calculation
- Offline-capable with cached PIN hash (SHA-256)
- PWA service worker for app shell caching

### AgriSmart Terminal — Phase 1 Foundation (Complete — Mar 2026)
- **YouTube TV-style device pairing:** Terminal shows 6-char code, PC enters it in Settings > Connect Terminal tab to pair
- **Backend APIs:** POST /api/terminal/generate-code, GET /api/terminal/poll/{code}, POST /api/terminal/pair, GET /api/terminal/active, POST /api/terminal/disconnect/{terminal_id}
- **Terminal Shell:** Mobile-optimized layout at /terminal with bottom navigation (Sales | PO Check | Transfers)
- **Terminal Sales Module:** Product search, camera barcode scanner (html5-qrcode), hardware barcode listener, cart management, checkout with offline save
- **Terminal PO Check Module:** View/verify purchase orders, adjust received quantities, finalize PO
- **Terminal Transfers Module:** View pending branch transfers, adjust received quantities, receive transfers
- **Settings Integration:** "Connect Terminal" tab with code input, branch selection, active terminals list with disconnect
- **Offline Support:** Uses existing IndexedDB + sync manager infrastructure, data download on pair
- **Receipt Numbering:** KS- prefix for terminal sales (Kiosk Sale)

## Prioritized Backlog

### P0 (Immediate)
- None — user testing of AgriSmart Terminal Phase 1

### P1 (High Priority)
- AgriSmart Terminal Phase 2: PO locking mechanism, "Send to Kiosk" on PC, receipt upload from terminal
- AgriSmart Terminal Phase 3: Branch Transfer locking, real-time conflict prevention
- Partial invoice payment trail
- Smart Journal Entries for forgotten sales
- Forgotten Sales on Closed Days workflow

### P2 (Medium Priority)
- Admin tool for corrupted Purchase Orders in production DB
- Refactor SuperAdminPage.jsx (1000+ lines)
- Fix react-hooks/exhaustive-deps warnings
- Refactor AdminLoginPage.jsx to use useNavigate
- Over-limit Cash Advances logic
- Closing History page

### P3 (Future)
- Portable POS Android App (thermal printer SDK integration)
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway & Demo Login
- "Weigh & Send" mode, advanced reporting, user roles/presets, "Pack & Ship"

## Key Files
- `/app/backend/routes/terminal.py` — Terminal pairing & session management
- `/app/frontend/src/pages/terminal/TerminalPage.jsx` — Main terminal page (pairing + shell)
- `/app/frontend/src/pages/terminal/TerminalPairScreen.jsx` — YouTube TV-style pairing code
- `/app/frontend/src/pages/terminal/TerminalShell.jsx` — Mobile shell with bottom nav
- `/app/frontend/src/pages/terminal/TerminalSales.jsx` — Mobile sales module
- `/app/frontend/src/pages/terminal/TerminalPOCheck.jsx` — PO verification
- `/app/frontend/src/pages/terminal/TerminalTransfers.jsx` — Branch transfer receiving
- `/app/frontend/src/pages/SettingsPage.js` — Connect Terminal tab (line ~132-230)

## Test Reports
- `/app/test_reports/iteration_110.json` — AgriSmart Terminal Phase 1 (100% pass)

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Manager PIN: 521325
