# AgriBooks PRD

## Original Problem Statement
Build a full-featured POS (Point-of-Sale) system called **AgriBooks** with multi-tenant, multi-branch support. The system includes sales management, purchase orders, inventory, branch transfers, accounting, employee management, and more.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn UI
- **Backend:** FastAPI (Python) + MongoDB
- **Offline:** IndexedDB + Service Worker (PWA)
- **Storage:** Cloudflare R2
- **Real-time:** WebSocket (FastAPI native)

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
- **YouTube TV-style device pairing:** Terminal shows 6-char code, PC enters it in Settings > Connect Terminal tab
- **Backend APIs:** generate-code, poll, pair, active, disconnect
- **Terminal Shell:** Mobile-optimized layout at /terminal with bottom nav (Sales | PO Check | Transfers)
- **Sales Module:** Product search, camera/hardware barcode scanning, cart, checkout, offline save
- **PO Check Module (basic):** View/verify purchase orders
- **Transfers Module (basic):** View/receive pending transfers
- **Offline Support:** Uses existing IndexedDB + sync manager
- **Receipt Numbering:** KS- prefix for terminal sales

### AgriSmart Terminal — Phase 2 WebSocket + PO Locking (Complete — Mar 2026)
- **Real-time WebSocket:**
  - `/api/terminal/ws/pairing/{code}` — Instant pairing notification (no more 2s polling)
  - `/api/terminal/ws/terminal/{terminal_id}` — Real-time PO/transfer push notifications
  - Polling kept as 3s fallback when WebSocket fails
  - WebSocket auto-reconnect on disconnect
- **PO Locking Mechanism:**
  - "Send to Terminal" button on PC PO page for draft/ordered POs
  - Status `sent_to_terminal` locks PO on PC (returns 423 if edit attempted)
  - PC shows "Locked — checking on terminal" badge
  - Terminal fetches only `sent_to_terminal` POs
- **Terminal PO Verification:**
  - View all items with ordered quantities
  - Adjust received quantities per item
  - Add verification notes
  - "Finalize & Send to PC" button
  - Records variances (ordered vs received differences)
  - Unlocks PO back to `ordered` with `terminal_verified=true`
  - PC shows "Terminal verified" badge
- **Real-time PO Assignment:**
  - When PC sends PO to terminal, WebSocket notifies terminal instantly
  - Red dot badge on PO Check tab for new assignments
  - Auto-refresh PO list on notification

## Prioritized Backlog

### P0 (Immediate)
- User testing of AgriSmart Terminal Phase 2

### P1 (High Priority)
- AgriSmart Terminal Phase 3: Branch Transfer locking + receiving through terminal
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
- Portable POS Android App (Capacitor wrap + thermal printer SDK + Newland scanner SDK)
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway & Demo Login
- "Weigh & Send" mode, advanced reporting, user roles/presets, "Pack & Ship"

## Key Files
- `/app/backend/routes/terminal.py` — Terminal pairing, session, WebSocket endpoints
- `/app/backend/routes/terminal_ws.py` — WebSocket connection manager
- `/app/backend/routes/purchase_orders.py` — send-to-terminal, terminal-finalize endpoints
- `/app/frontend/src/pages/terminal/TerminalPage.jsx` — Main terminal page
- `/app/frontend/src/pages/terminal/TerminalPairScreen.jsx` — Pairing with WebSocket + polling fallback
- `/app/frontend/src/pages/terminal/TerminalShell.jsx` — Shell with WebSocket real-time events
- `/app/frontend/src/pages/terminal/TerminalSales.jsx` — Mobile sales module
- `/app/frontend/src/pages/terminal/TerminalPOCheck.jsx` — PO verification with finalize
- `/app/frontend/src/pages/terminal/TerminalTransfers.jsx` — Branch transfer receiving
- `/app/frontend/src/pages/PurchaseOrderPage.js` — "Send to Terminal" button, lock/verified badges
- `/app/frontend/src/pages/SettingsPage.js` — Connect Terminal tab

## Test Reports
- `/app/test_reports/iteration_110.json` — Phase 1 (100% pass)
- `/app/test_reports/iteration_111.json` — Phase 2 (100% pass)

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Manager PIN: 521325
