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
- "Send to Terminal" on Branch Transfer page for sent status transfers
- Transfer locking: sent_to_terminal status blocks PC receive (423), cancel
- Terminal receive flow with pricing display, variance handling
- All match → received (inventory moves), Variance → received_pending (source notified)
- WebSocket notification + red dot badges on Transfers tab

### Branch Transfer UX Redesign (Complete — Mar 2026)
- Replaced old "Incoming/Outgoing/Requests" sub-tabs with unified status-based filter pills
- Status categories: All, Requests, Drafts, In Transit, Terminal, Needs Review, Completed, Disputes
- Card-based transfer display replacing flat table rows
- Each card shows: order number, branch route, status badge, date, inline timeline, financials, action buttons
- Colored left borders per status (slate=draft, blue=in-transit, amber=terminal, orange=pending, emerald=completed, red=disputed)
- "Needs Review" pill auto-highlighted in orange when transfers need attention
- Stock Requests displayed as separate card layout with product tags
- All existing dialogs (View, Receive, Accept/Dispute) preserved and functional

### QR Code Terminal Login (Complete — Mar 2026)
- PC Settings > Connect Terminal shows "Quick Pair — Scan QR Code" with branch selector
- Generates a time-limited QR token (10 min expiry) tied to a branch
- QR code encodes terminal URL with pair token for one-scan mobile pairing
- Terminal auto-detects `?pair=TOKEN` URL param and auto-pairs without code screen
- URL cleaned after pairing for security
- Manual 6-digit code pairing preserved as fallback below QR section

### Terminal Pull Data — Self-Serve with PIN (Complete — Mar 2026)
- Terminal PO Check and Transfers tabs show "Pull" button
- Browsing available POs (draft/ordered) and Transfers (sent) for the terminal's branch
- PIN verification required before pulling — uses same PIN policies from Settings (admin PIN, manager PIN, TOTP)
- After pulling, status changes to sent_to_terminal and item appears in terminal checking flow
- Invalid PIN returns clear error message
- Terminal operator can self-serve without waiting for PC to push

### Terminal UX Improvements (Complete — Mar 2026)
- Branch restriction: managers/cashiers can only pair terminal to their assigned branch, admins can pair to any
- Camera scanner fix: resolved race condition where scanner div wasn't rendered before Html5Qrcode initialization
- Navigation redesign: replaced bottom tab bar with floating mode selector icon (lower-left)
- Floating menu shows: Sales, PO Check, Transfers, Settings
- Settings panel shows branch info, paired-by user, online status, Sync Now, and Unlink Terminal button
- Unlink Terminal clears session and returns to pairing screen

### Terminal Sales & UX Fixes (Complete — Mar 2026)
- Scanner debounce: 2-second cooldown prevents duplicate scans of same barcode
- Full checkout flow: Cash (amount tendered + change), Digital (screenshot upload required), Credit (customer + 15/30/60 day terms), Split (cash+digital with auto-calculation)
- Online sales: shows real API errors instead of silently saving offline
- Sales History: added sidebar link under Transactions, shows all sales newest-first with search, filters (All/Paid/Partial/Credit/Voided), sorting, pagination (50/page)

## Pricing Model (Branch Transfer — Must Preserve)
- **Branch Capital:** Source branch's cost (read-only)
- **Transfer Capital:** Price "sold" to destination (editable, with category markup)
- **Branch Retail:** Retail price at destination (admin-only editing)
- **Min Margin:** Transfer_capital to branch_retail
- **Repack pricing:** New retail prices for repacks at destination

## Branch Transfer Status Flow
```
draft → sent → sent_to_terminal → received (all match)
                                 → received_pending (variance) → accepted → received
                                                                → disputed → received_pending (re-count)
```

## NEXT SESSION — Priority Tasks

### Prioritized Backlog

### P1 (High Priority)
- Partial invoice payment trail
- Smart Journal Entries for forgotten sales
- Forgotten Sales on Closed Days workflow

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
- `/app/frontend/src/pages/BranchTransferPage.js` — Redesigned status-based view
- `/app/frontend/src/pages/SettingsPage.js` — Connect Terminal tab

## Test Reports
- `/app/test_reports/iteration_110.json` — Phase 1 (100%)
- `/app/test_reports/iteration_111.json` — Phase 2 (100%)
- `/app/test_reports/iteration_112.json` — Phase 3 (100%)
- `/app/test_reports/iteration_113.json` — Branch Transfer UX Redesign (100%)
- `/app/test_reports/iteration_114.json` — QR Code Terminal Login (100%)
- `/app/test_reports/iteration_115.json` — Terminal Pull Data (100%)
- `/app/test_reports/iteration_116.json` — Branch Restriction + Nav Redesign (100%)
- `/app/test_reports/iteration_117.json` — Terminal Sales Fixes + Sales History (100%)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Test Admin: testadmin@test.com / Test@123
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode
