# AgriBooks PRD

## Original Problem Statement
Build a full-featured POS system called **AgriBooks** with multi-tenant, multi-branch support including sales, purchase orders, inventory, branch transfers, accounting, employee management, and more.

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

### AgriSmart Terminal — Phase 1 Foundation (Complete — Mar 2026)
- YouTube TV-style device pairing (6-char code)
- Terminal Shell at /terminal with bottom nav (Sales | PO Check | Transfers)
- Sales Module with camera/hardware barcode scanning, cart, checkout
- Offline support via IndexedDB + sync manager
- KS- prefix for terminal receipts

### AgriSmart Terminal — Phase 2 WebSocket + PO Locking (Complete — Mar 2026)
- Real-time WebSocket for instant pairing and PO/transfer push notifications
- PO "Send to Terminal" with locking mechanism (423 on PC edit)
- Terminal PO verification with quantity adjustment and finalize
- Variance recording with terminal_verified badge on PC

### AgriSmart Terminal — Phase 3 Branch Transfer Integration (Complete — Mar 2026)
- **"Send to Terminal" on Branch Transfer page** for `sent` status transfers
- **Transfer locking:** `sent_to_terminal` status blocks PC receive (423), cancel
- **Terminal receive flow:**
  - Shows items with sent qty, transfer capital, branch retail pricing
  - Quantity adjustment per item with variance badges (short/excess)
  - Capital impact display for variances
  - "Submit with Variance" or "Confirm Receipt" based on variance
  - All quantities match → `received`, inventory updated immediately
  - Variance detected → `received_pending`, source branch notified for accept/dispute
- **WebSocket notification** when transfer is assigned to terminal
- **Red dot badges** on Transfers tab for new assignments
- **PC badges:** "On Terminal" (amber) and "Terminal" (green after verification)

## Pricing Model (Branch Transfer — Must Preserve)
- **Branch Capital:** Source branch's cost for product (read-only)
- **Transfer Capital:** Price at which product is "sold" to destination branch (editable, with category markup)
- **Branch Retail:** Retail price at destination branch (admin-only editing)
- **Min Margin:** Transfer_capital to branch_retail
- **Repack pricing:** Set new retail prices for repacks at destination

## Branch Transfer Status Flow
```
draft → sent → sent_to_terminal → received (all match)
                                 → received_pending (variance) → accepted → received
                                                                → disputed → received_pending (re-count)
```

## Prioritized Backlog

### P1 (High Priority)
- Branch Transfer UX redesign (unified view: My Requests / Incoming / Outgoing)
- Branch Stock Request flow (simplified form, no receipt upload)
- Partial invoice payment trail
- Smart Journal Entries for forgotten sales

### P2 (Medium Priority)
- Admin tool for corrupted POs in production DB
- Refactor SuperAdminPage.jsx (1000+ lines)
- Fix react-hooks/exhaustive-deps warnings
- Over-limit Cash Advances logic

### P3 (Future)
- Capacitor APK wrap (thermal printer + Newland scanner SDK)
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway & Demo Login
- "Weigh & Send" mode, advanced reporting, "Pack & Ship"

## Key Files
- `/app/backend/routes/terminal.py` — Terminal pairing, WebSocket endpoints
- `/app/backend/routes/terminal_ws.py` — WebSocket connection manager
- `/app/backend/routes/purchase_orders.py` — send-to-terminal, terminal-finalize
- `/app/backend/routes/branch_transfers.py` — send-to-terminal, terminal-receive, locking
- `/app/frontend/src/pages/terminal/` — All terminal components
- `/app/frontend/src/pages/PurchaseOrderPage.js` — Send to Terminal button
- `/app/frontend/src/pages/BranchTransferPage.js` — Send to Terminal, lock/verified badges
- `/app/frontend/src/pages/SettingsPage.js` — Connect Terminal tab

## Test Reports
- `/app/test_reports/iteration_110.json` — Phase 1 (100%)
- `/app/test_reports/iteration_111.json` — Phase 2 (100%)
- `/app/test_reports/iteration_112.json` — Phase 3 (100%)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Manager PIN: 521325
