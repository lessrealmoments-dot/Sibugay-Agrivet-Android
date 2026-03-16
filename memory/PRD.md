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

### Count Sheets — Reserved Stock Fix (Complete — Mar 2026)
- **Bug fixed**: Snapshot was using only `inventory.quantity` (available), ignoring `reserved_qty`. Counters physically see all stock including reserved items, causing false +surplus variances.
- **Fix**: `system_quantity = quantity + reserved_qty` (total physical on shelf). Added `system_available_qty` and `system_reserved_qty` fields per item.
- **Adjustment fix**: When applying adjustments, only updates `quantity = actual_counted - reserved_qty`. Reserved stock stays untouched (managed by release system, not count sheets).
- **UI**: Count sheet shows `"80 avail + 20 reserved"` sub-note under system qty when reserved stock is present.

### Pending Releases Page (Complete — Mar 2026)
- New sidebar page under Inventory & Purchasing: `/pending-releases`
- Summary cards: pending invoices, total reserved qty, overdue count (>30 days)
- Table: invoice #, customer, date, age badge (green/amber/red), status, items remaining, progress bar
- Filter by branch (admin) and status (pending only / all)
- Click any row or external link icon opens the `/doc/{code}` release management page
- Overdue alert banner with auto-return explanation

### QR Operational Workflows — Phase 2 Stock Release via QR (Complete — Mar 2026)
- **Inventory model corrected**: Partial release now deducts `inventory.quantity` immediately at sale (same as full release) AND increments `inventory.reserved_qty`. Physical stock = quantity + reserved_qty. Available to sell = quantity only.
- **`/api/qr-actions/{code}/release_stocks`**: PIN-gated release action. Decrements `reserved_qty` on release. Idempotent via `release_ref`. Branch-restricted manager PIN enforced.
- **30-day expiry job**: Daily APScheduler job returns `qty_remaining` from `reserved_qty` back to `quantity`. Logs `expiry_return` movement. Notifies branch manager.
- **Void guard**: Void on partial-release invoice only returns unreleased qty. Clears reservations. Already-released stock correctly treated as gone.
- **`DocViewerPage` updated**: Shows Release Stock panel when `available_actions` includes `release_stocks`. After release, status updates live. Shows ordered/released/remaining per item with "All" shortcut.
- **Doc code fallback**: `/doc` (no code) shows text input form. "Enter document code manually" link at bottom of every doc page. Terminal pull still works.
- **`/doc/view/{code}`** now returns `available_actions[]`, `reservations[]`, `release_mode`, `stock_release_status`.

### QR Operational Workflows — Phase 1 Foundation (Complete — Mar 2026)
- **Stock Reservation Model**: `release_mode: "full" | "partial"` on all invoices. Partial release reserves stock without deducting inventory until physical handover.
- **`sale_reservations` collection**: Tracks per-product reservations per invoice, with `qty_reserved/released/remaining` and 30-day expiry.
- **Available stock calc updated**: `products.py` search-detail and barcode-lookup now subtract active reservations from available stock.
- **Sales History badges**: Unreleased / Partially Released / Released shown on invoice list.
- **Z-Report / Close Wizard warning**: Step 1 shows count of unreleased invoices and total reserved qty. Overdue (>30 days) shown in red.
- **PIN System extended**: Added `admin_totp` method (TOTP restricted to admin/owner role only). Added 5 QR action policies: `qr_release_stocks`, `qr_receive_payment`, `qr_view_payment_history`, `qr_po_receive`, `qr_transfer_receive` — all configurable in Settings → Security → PIN Policies.
- **`/api/stock-releases`**: New endpoints to list pending releases, summary, and per-invoice detail.

### Product Name Deduplication (Complete — Feb 2026)
- Identified 11 product name groups with 66 duplicate records (caused by missing uniqueness constraint)
- Migration: merged inventory (44 records), updated PO items (74), movements (218) into canonical products
- Added case-insensitive name uniqueness validation to POST /products and PUT /products/:id
- Self-update (renaming to same name) correctly allowed; cross-product name conflict blocked

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
- Sales with barcode scanner, full checkout, print order slip
- PO verification + Transfer receive with variance handling
- WebSocket real-time notifications, Terminal Pull

### QR Document Lookup System (Complete — Mar 2026)
- Unique 8-char doc code per document, QR on every receipt
- 3-Tier Access Model (Open / PIN / Terminal)
- Document code scanning in Ctrl+K QuickSearch

### PrintEngine v2 (Complete — Mar 2026)
- Professional template with QR codes on all document types
- Thermal (58mm) + Full Page templates for Sales, PO, and Branch Transfers
- Centralized across all detail modals (Sales, PO, Transfer)

### Stock Request Migration to Branch Transfers (Complete — Mar 2026)
- "Request Stock" tab in Branch Transfers with simplified form
- Removed Source Type toggle from Purchase Orders (now purely external suppliers)
- Incoming/Outgoing Requests view in Transfers History
- Backend: Added `po_type` filter to `/purchase-orders` list endpoint

### Transfer Dispute & Incident Ticket Connectivity (Complete — Mar 2026)
**How the dispute flow affects inventory & pricing:**
```
1. SEND: Branch A sends 10 → NO inventory deducted yet
2. RECEIVE: Branch B counts 5 → status: received_pending (NO movement)
3a. ACCEPT: Branch A confirms 5 → A: -5, B: +5, remaining 5 stay at A
    → Moving average at B recalculated with transfer_in @ resolved capital
    → Capital loss logged for the variance (5 * transfer_capital)
3b. DISPUTE: Branch A says "re-count" → B re-counts → back to step 2
```

**New features implemented:**
1. **Incident ticket badge clickable on transfer cards** — Amber `INC-00001` badge navigates to `/incident-tickets`
2. **Transfer Variances in Audit Center** — New tab with:
   - 4 summary cards: Total Variance Transfers, Capital Loss, Open Tickets, Unresolved Capital at Risk
   - Detailed variance list with incident ticket links and capital loss per transfer
   - New backend endpoint: `GET /api/audit/transfer-variances`
3. **Bidirectional links** — Transfer detail → Incident Ticket (clickable badge). Incident Ticket → Transfer (clickable link in table and detail dialog)
4. **Dispute History Timeline** — Visual timeline on transfer view dialog showing:
   - First Count (blue dot) with shortages/excesses
   - Dispute by Source (red dot) with dispute note
   - Re-count (amber dot)
   - Acceptance (green dot) with incident ticket link

### Transfer Variance Modal Fix (Complete — Mar 2026)
- Extracted `TransferDetailModal.js` as a reusable read-only transfer view component
- Audit Center "View" button now opens inline popup instead of navigating to Branch Transfers page
- Shows: order header, status timeline, variance history, reconciliation table, print button
- BranchTransferPage's existing action-based view dialog remains unchanged

### Transfer Variances & Incident Tickets Merge (Complete — Mar 2026)
- Merged Transfer Variances tab from Audit Center into the Incident Tickets page
- Incident Tickets page is now the single source of truth: two main tabs ("Incident Tickets" + "All Transfer Variances")
- Summary cards show combined metrics (Total Variances, Capital Loss, Active Tickets, Resolved, Unresolved Loss)
- Transfer order links in both tabs open TransferDetailModal popup inline
- Ticket badges on variance items navigate to tickets tab with search
- Removed Transfer Variances tab from Audit Center (now has: Verification, Transactions, Security Flags)

### Phase 1: Request Stock Dual-Branch Inventory Visibility (Complete — Mar 2026)
- Added `also_branch_id` param to `/products/search-detail` endpoint for dual-branch stock lookup
- Product search dropdown now shows stock levels from both your branch and the supplier branch
- Selected product rows display both stock counts inline
- Fixed product search endpoint mismatch (`/detail-search` → `/search-detail`)
- Fixed `branch_id` missing from stock request POST body + backend fallback from JWT

### Phase 2: Structured Variance Resolution Workflow (Complete — Mar 2026)
- Resolution Type dropdown: transit_loss, sender_error, receiver_error, write_off, insurance_claim, partial_recovery
- Accountable Party field (conditional — shown for transit_loss, insurance_claim, partial_recovery)
- Sender Confirmation flow: sender can confirm actual quantities; if all match receiver, ticket auto-resolves as "sender_error" (no real loss)
- Enhanced resolve dialog with contextual hints per resolution type
- Resolution column added to tickets table
- Backend: /api/incident-tickets/resolve enhanced, /api/incident-tickets/sender-confirm new, /api/incident-tickets/resolution-types new

### Phase 3: Automated Journal Entries & Cash Movement (Complete — Mar 2026)
- Auto-generates balanced journal entries on incident resolution based on type:
  - transit_loss: DR 1110 Driver/Courier Receivable, CR 1200 Inventory
  - write_off: DR 5500 Inventory Loss/Write-off, CR 1200 Inventory
  - insurance_claim: DR 1120 Insurance Receivable, CR 1200 Inventory
  - partial_recovery: DR Cash + DR Loss, CR Inventory (split)
  - sender_error / receiver_error: No JE (no financial impact)
- Capital Loss summary excludes sender_error tickets (real loss only)
- PIN authorization required for resolve (admin/manager/TOTP, single input, respects pin policies)
- Ticket detail shows: Approved by, Charged to, Journal Entry reference
- New chart of accounts: 1110 Driver/Courier Receivable, 1120 Insurance Receivable
- New entry type: incident_adjustment

## NEXT SESSION — Priority Tasks

### Task 1: Backend Branch Isolation Audit (P1)
- Audit transfer endpoints: `/receive`, `/accept-receipt`, `/dispute-receipt`
- Ensure each validates user belongs to correct branch

### Task 2: Partial Invoice Payment Trail (P1)
- Visual "trail" for partial invoices showing payment history

### Task 3: Smart Journal Entries (P2)
- For forgotten sales on closed days

## Prioritized Backlog

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
- `/app/backend/routes/branch_transfers.py` — Transfer CRUD, receive, accept/dispute
- `/app/backend/routes/purchase_orders.py` — PO CRUD (with po_type filter)
- `/app/backend/routes/audit.py` — Audit + transfer variance stats endpoint
- `/app/backend/routes/incident_tickets.py` — Incident ticket CRUD
- `/app/frontend/src/pages/BranchTransferPage.js` — Transfers + Request Stock + Dispute Timeline
- `/app/frontend/src/pages/AuditCenterPage.js` — Audit Center with Transfer Variances tab
- `/app/frontend/src/components/TransferDetailModal.js` — Reusable read-only transfer detail modal
- `/app/frontend/src/pages/IncidentTicketsPage.js` — Ticket list with transfer links
- `/app/frontend/src/pages/PurchaseOrderPage.js` — External supplier POs only
- `/app/frontend/src/lib/PrintEngine.js` — Centralized print engine
- `/app/frontend/src/components/QuickSearch.js` — Ctrl+K search with doc code scanning

## Test Reports
- `/app/test_reports/iteration_123.json` — Stock Request Migration (100%)
- `/app/test_reports/iteration_124.json` — Dispute/Ticket Connectivity (100%)
- `/app/test_reports/iteration_125.json` — Transfer Variance Modal Fix (100%, 6/6 tests)
- `/app/test_reports/iteration_126.json` — Variance + Tickets Merge (100%, 10/10 tests)
- `/app/test_reports/iteration_127.json` — Phase 2 Resolution Workflow (100%, 17/17 backend + full frontend)
- `/app/test_reports/iteration_128.json` — Phase 3 Auto Journal Entries (100%, all features verified)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Company Admin: jovelyneahig@gmail.com / Aa@050772
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react
