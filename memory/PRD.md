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

### QR Document Lookup System (Complete — Mar 2026)
- Unique 8-char alphanumeric code per document (Sales, PO, Branch Transfer)
- QR code printed on every receipt linking to `/doc/:code`
- 3-Tier Access Model (Open / PIN / Terminal)
- Terminal detection via localStorage `agrismart_terminal` session

### PrintEngine v2 Redesign (Complete — Mar 2026)
- Professional template with QR codes on all document types
- Thermal (58mm) + Full Page templates for Sales, PO, and Branch Transfers
- Consistent styling across all document types

### Branch Transfer UX Redesign (Complete — Mar 2026)
- Status-based filter pills, card-based layout, enlarged UX
- Branch role indicator ("You: Sender" / "You: Receiver")
- Branch isolation fix (admin can't bypass branch context)

### Centralized Receipt & Modal UX Fix (Complete — Mar 2026)
- SaleDetailModal, PODetailModal, PurchaseOrderPage detail — all generate doc_code + QR on print
- Action toolbar redesign: all actions visible (Print Full, Print 58mm, View on Phone, Upload Receipt, Verify, Edit) as `flex-wrap` row below title
- Document code search in QuickSearch (Ctrl+K) with "QR Code Match" badge

### Stock Request Migration to Branch Transfers (Complete — Mar 2026)
- **Moved "Branch Stock Request" from Purchase Orders to Branch Transfers**
- New "Request Stock" tab in Branch Transfers with simplified form:
  - Your Branch (locked) → Request From Branch → Product search + Qty → Notes → Send
  - Show retail price toggle for supply branch visibility
  - Still creates `purchase_order` with `po_type: branch_request` on backend (zero migration risk)
- **Removed Source Type Toggle from Purchase Orders** — PO page is now purely for external suppliers
- **Incoming/Outgoing Requests view** in Transfers History:
  - "Incoming" tab shows requests from other branches (existing, with "Generate Transfer" action)
  - "My Requests" tab shows requests you sent (new, with fulfillment status tracking)
- Backend: Added `po_type` filter to `/purchase-orders` list endpoint

## How Stock Requests Connect to Everything

### Data Flow
```
Branch A (requester) → Request Stock tab → POST /purchase-orders (po_type=branch_request)
  → Notification to Branch B (supply branch)
  → Branch B sees in "Incoming Requests" → "Generate Transfer" button
  → Creates actual branch_transfer order → Normal transfer lifecycle
  → On receive: inventory adjusted, linked PO marked fulfilled/partially_fulfilled
```

### Connections
- **Stock movement**: Only on transfer receive (inventory addition/deduction)
- **Cash/cost tracking**: Via `transfer_capital` on the actual transfer
- **Notifications**: Fired on request creation to supply branch
- **Fulfillment**: Transfer receive updates linked PO via `request_po_id`
- **Internal invoices**: Created on transfer generation from request
- **Incident tickets**: Created on transfer disputes (count variance)

## NEXT SESSION — Priority Tasks

### Task 1: Incident Ticket Connectivity Audit (P1)
- Audit how transfer disputes create incident tickets
- Ensure tickets are connected to Reports and Audit section
- Verify price moving average impact from disputed transfers
- Map all incident ticket sources: transfers, count sheets, POs

### Task 2: Backend Branch Isolation Audit (P1)
- Audit transfer endpoints: `/receive`, `/accept-receipt`, `/dispute-receipt`
- Ensure each validates user belongs to correct branch

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
- `/app/backend/routes/purchase_orders.py` — PO CRUD (now with po_type filter)
- `/app/backend/routes/search.py` — Universal search with doc code lookup
- `/app/backend/routes/doc_lookup.py` — Doc code generation and lookup
- `/app/backend/routes/incident_tickets.py` — Incident ticket CRUD
- `/app/frontend/src/pages/BranchTransferPage.js` — Transfers + Request Stock + History
- `/app/frontend/src/pages/PurchaseOrderPage.js` — External supplier POs only
- `/app/frontend/src/pages/terminal/` — All terminal components
- `/app/frontend/src/components/SaleDetailModal.js` — Sale detail with QR print
- `/app/frontend/src/components/PODetailModal.js` — PO detail with QR print
- `/app/frontend/src/components/QuickSearch.js` — Ctrl+K search with doc code scanning
- `/app/frontend/src/lib/PrintEngine.js` — Centralized print engine

## Test Reports
- `/app/test_reports/iteration_122.json` — Centralized Receipt + Modal UX + QuickSearch (100%)
- `/app/test_reports/iteration_123.json` — Stock Request Migration (100%)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Company Admin: jovelyneahig@gmail.com / Aa@050772
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react
