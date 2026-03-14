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

### Print Prompts After Sale/PO (Complete — Mar 2026)
- After every sale (Quick Sales + Orders), ReferenceNumberPrompt now shows Print Full Page and Print Thermal buttons
- Print generates doc code + QR code on all receipts
- Sales History page also generates QR codes when reprinting
- POSPage now shows the same prompt after checkout

### QR Document Lookup System (Complete — Mar 2026)
- Unique 8-char alphanumeric code per document (Sales, PO, Branch Transfer)
- QR code printed on every receipt linking to `/doc/:code`
- **3-Tier Access Model:**
  - Tier 1 (Open): Items, total, status, customer/supplier — no PIN needed
  - Tier 2 (PIN): Payment history, attached files, notes, reprint — Manager/Admin/TOTP PIN
  - Tier 3 (Terminal): Pull PO/Transfer to terminal, apply credit payment — paired terminal + PIN
- Terminal detection via localStorage `agrismart_terminal` session

### PrintEngine v2 Redesign (Complete — Mar 2026)
- Professional template: company left, doc info right, green header bar
- Clean info boxes for From/To or Supplier/Customer
- Spacious table with alternating rows, fewer columns
- QR code on all printed documents
- Consistent styling across all document types
- Branch Transfer migrated from custom HTML to centralized PrintEngine

### Branch Transfer UX Redesign (Complete — Mar 2026)
- Status-based filter pills (All, Requests, Drafts, In Transit, Terminal, Needs Review, Completed, Disputes)
- Card-based layout with timelines, action buttons, colored borders
- **UX enlarged for employee accessibility** (Mar 2026): Bigger filter pills, larger cards, bigger buttons with text labels, larger timeline dots
- **Branch role indicator** (Mar 2026): "You: Sender" (blue) / "You: Receiver" (green) tags on each transfer card

### Terminal Sales Fixes (Complete — Mar 2026)
- Scanner debounce (2s cooldown), full checkout flow, online API error handling
- Sales History sidebar link at /sales with search, filters, sorting, pagination

### Branch Isolation Bug Fix (Complete — Mar 2026)
- Removed `isAdmin ||` override from `isSourceBranch` and `isDestBranch` in BranchTransferPage.js
- Removed `isAdmin` bypass from Edit Draft and Send to Terminal buttons
- Fixed "Confirm Receipt" dialog to use branch context instead of isAdmin
- Admin in consolidated view sees View only; specific branch selection shows correct actions

## NEXT SESSION — Priority Tasks

### Task 1: Move Stock Requests from Purchase Orders to Branch Transfers (P1)
**Current:** Stock requests between branches are in Purchase Orders section
**Should be:** Under Branch Transfers since they're inter-branch operations
- Move the "Requests" tab/functionality from PurchaseOrdersPage to BranchTransferPage
- Update the request creation flow to live under Branch Transfers
- Update sidebar navigation if needed
- Keep the "Generate Transfer from Request" flow working

### Task 2: Backend Branch Isolation Audit (P1)
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
- `/app/frontend/src/pages/BranchTransferPage.js` — Branch isolation fixed, UX enlarged
- `/app/frontend/src/pages/terminal/` — All terminal components
- `/app/frontend/src/pages/SalesPage.js` — Sales history
- `/app/frontend/src/components/Layout.js` — Sidebar navigation

## Test Reports
- `/app/test_reports/iteration_118.json` — Branch Isolation Fix + UX Enlargement (100%)

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Manager PIN: 521325

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react
