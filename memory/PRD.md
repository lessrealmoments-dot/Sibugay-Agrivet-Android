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

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Company Admin: jovelyneahig@gmail.com / Aa@050772
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react
