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

### AgriSmart Terminal — Phase 1-3 (Complete — Mar 2026)
- Device pairing (6-char code + QR auto-pair)
- Terminal Shell with floating mode selector (Sales | PO Check | Transfers | Settings)
- Sales with barcode scanner (debounced), full checkout (Cash/Digital/Credit/Split), print order slip
- PO verification + Transfer receive with variance handling
- WebSocket real-time notifications
- Branch restriction: managers/cashiers locked to their branch
- Terminal Pull: self-serve PO/Transfer pull with PIN verification
- Settings panel with Unlink Terminal

### Branch Transfer UX Redesign (Complete — Mar 2026)
- Status-based filter pills (All, Requests, Drafts, In Transit, Terminal, Needs Review, Completed, Disputes)
- Card-based layout with timelines, action buttons, colored borders

### Terminal Sales Fixes (Complete — Mar 2026)
- Scanner debounce (2s cooldown), full checkout flow, online API error handling
- Sales History sidebar link at /sales with search, filters, sorting, pagination

## NEXT SESSION — Priority Tasks (User Confirmed)

### Task 1: Branch Process Isolation Fix (P0 — CRITICAL LOGIC BUG)
**Problem:** `isSourceBranch` and `isDestBranch` in BranchTransferPage.js use `isAdmin ||` which makes admins see ALL actions for ALL transfers regardless of branch context. This breaks branch isolation.

**Current (broken):**
```javascript
const isSourceBranch = isAdmin || o.from_branch_id === effectiveBranchId;
const isDestBranch = isAdmin || o.to_branch_id === effectiveBranchId;
```

**Fix:** Remove admin override — actions should be strictly branch-context:
```javascript
const isSourceBranch = o.from_branch_id === effectiveBranchId;
const isDestBranch = o.to_branch_id === effectiveBranchId;
```

**Correct flow:**
- Branch A requests stock from Branch B
- Branch B prepares and sends → only Branch B sees Send/Cancel
- Branch A receives and counts → only Branch A sees Receive
- If variance: status = received_pending → only Branch B sees Accept/Dispute
- Branch A should NEVER see Branch B's accept/dispute buttons and vice versa

Also check the backend endpoints for the same admin bypass issue.

### Task 2: Move Stock Requests from Purchase Orders to Branch Transfers (P0)
**Current:** Stock requests between branches are in Purchase Orders section
**Should be:** Under Branch Transfers since they're inter-branch operations
- Move the "Requests" tab/functionality from PurchaseOrdersPage to BranchTransferPage
- Update the request creation flow to live under Branch Transfers
- Update sidebar navigation if needed
- Keep the "Generate Transfer from Request" flow working

### Task 3: Backend Branch Isolation Audit
- Audit all transfer endpoints: `/receive`, `/accept-receipt`, `/dispute-receipt`
- Ensure each endpoint validates that the requesting user belongs to the correct branch for the action
- Source branch actions: send, cancel, accept-receipt, dispute-receipt
- Dest branch actions: receive, re-count after dispute
- Admin in consolidated view should see everything but actions restricted to branch context

## Prioritized Backlog

### P1 (High Priority)
- Partial invoice payment trail
- Smart Journal Entries for forgotten sales
- Forgotten Sales on Closed Days workflow

### P2 (Medium Priority)
- Admin tool for corrupted POs in production DB
- Refactor SuperAdminPage.jsx (1000+ lines)
- Fix react-hooks/exhaustive-deps warnings

### P3 (Future)
- Capacitor APK wrap (thermal printer + Newland scanner SDK)
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway & Demo Login
- Advanced reporting, "Pack & Ship"

## Key Files
- `/app/backend/routes/terminal.py` — Terminal pairing, QR, pull, WebSocket
- `/app/backend/routes/branch_transfers.py` — Transfer CRUD, receive, accept/dispute
- `/app/backend/routes/purchase_orders.py` — PO CRUD, stock requests
- `/app/frontend/src/pages/BranchTransferPage.js` — **Lines 1516-1517 are the bug**
- `/app/frontend/src/pages/terminal/` — All terminal components
- `/app/frontend/src/pages/SalesPage.js` — Sales history
- `/app/frontend/src/components/Layout.js` — Sidebar navigation

## Test Reports
- `/app/test_reports/iteration_113.json` — Branch Transfer UX (100%)
- `/app/test_reports/iteration_114.json` — QR Login (100%)
- `/app/test_reports/iteration_115.json` — Terminal Pull (100%)
- `/app/test_reports/iteration_116.json` — Branch Restriction + Nav (100%)
- `/app/test_reports/iteration_117.json` — Sales Fixes (100%)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Test Admin: testadmin@test.com / Test@123
- Test Manager: testmanager@test.com / Test@123 (Branch 1 only)
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react
