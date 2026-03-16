# AgriBooks PRD

## Original Problem Statement
Build a full-featured POS system called **AgriBooks** with multi-tenant, multi-branch support including sales, purchase orders, inventory, branch transfers, accounting, employee management, and more. Extended with an AgriSmart Terminal (handheld Android + barcode scanner + thermal printer) and a QR-based operational workflow system.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn UI
- **Backend:** FastAPI (Python) + MongoDB
- **Offline:** IndexedDB + Service Worker (PWA)
- **Storage:** Cloudflare R2
- **Real-time:** WebSocket (FastAPI native)

## 3rd Party Integrations
- Cloudflare R2, Resend, Google Authenticator, fpdf2, python-barcode, jsbarcode, html5-qrcode, qrcode.react

## Credentials
- Super Admin: janmarkeahig@gmail.com / Aa@58798546521325
- Company Admin: jovelyneahig@gmail.com / Aa@050772
- Manager PIN: 521325

---

## What's Been Implemented

### Core POS (Complete)
- Multi-tenant org management, branch management, user roles & permissions
- Unified sales: walk-in, credit, partial, digital, split payments
- Purchase orders (external suppliers only), suppliers, branch transfers
- Inventory management, count sheets, barcode printing
- Customers, price schemes, branch-specific pricing
- Daily operations, close-of-day wizard, Z-reports
- Payments, fund management, expenses, accounting, journal entries
- Audit center, incident tickets, backups, reports
- Mobile barcode scanner, returns/refunds

### AgriSmart Terminal (Complete — Mar 2026)
- Device pairing (6-char code + QR auto-pair)
- Terminal Shell with floating mode selector (Sales | PO Check | Transfers | Settings)
- Sales with barcode scanner, full checkout, print order slip
- PO verification + Transfer receive with variance handling
- WebSocket real-time notifications, Terminal Pull

### QR Document Lookup System (Complete — Mar 2026)
- Unique 8-char doc code per document, QR on every receipt
- 3-Tier Access Model (Open / PIN / Terminal)
- Document code scanning in Ctrl+K QuickSearch
- `/doc` entry page (type code manually if QR faded)
- `/doc/:code` full action page

### PrintEngine v2 (Complete — Mar 2026)
- Professional template with QR codes on all document types
- Thermal (58mm) + Full Page templates for Sales, PO, Branch Transfers

### Transfer Dispute & Incident Ticket System (Complete — Mar 2026)
- Structured variance resolution workflow (transit_loss, sender_error, write_off, etc.)
- Auto-generated double-entry journal entries on resolution
- PIN-based authorization for resolving incidents
- Audit Center + Incident Tickets merged for single source of truth

### QR Operational Workflows — Phase 1 (Complete — Mar 2026)
- `release_mode: "full" | "partial"` on invoices
- `inventory.quantity` = available. `inventory.reserved_qty` = customer's stock pending pickup.
- Physical on shelf = quantity + reserved_qty (always accurate)
- `sale_reservations` collection for delivery tracking
- `admin_totp` PIN method (TOTP for admin/owner only)
- 5 QR PIN policies in Settings → Security → PIN Policies
- `/api/stock-releases` endpoints (list, summary, per-invoice)
- Z-Report warning for pending releases
- Sales History badges: Unreleased / Partially Released / Released
- Partial release toggle in checkout dialog

### QR Operational Workflows — Phase 2 (Complete — Mar 2026)
- `POST /api/qr-actions/{code}/release_stocks` — PIN-gated, branch-restricted, idempotent
- `POST /api/qr-actions/{code}/verify_pin` — unlock panel without action
- `StockReleaseManager` in `DocViewerPage.jsx` — unified PIN-gated panel: history + form + confirmation
- 30-day expiry APScheduler job → `expiry_return` movement, manager notification
- Void guard for partial-release invoices (only reverses unreleased portion)
- Auto doc_code generated at partial-release sale creation (returned in response)

### Count Sheets — Reserved Stock Fix (Complete — Mar 2026)
- `system_quantity = quantity + reserved_qty` (total physical on shelf)
- Adjustment: `new_quantity = actual_counted - reserved_qty` (reserved untouched)
- UI shows "80 avail + 20 reserved" breakdown

### Pending Releases Page (Complete — Mar 2026)
- `/pending-releases` sidebar page under Inventory & Purchasing
- Summary cards, age badges, progress bars, overdue alerts
- Click row → opens `/doc/{code}` release management page

### Product Data Integrity (Complete — Mar 2026)
- Name uniqueness validation (case-insensitive) on create + update
- Price scheme uniqueness validation on create
- Cleaned 66 duplicate products + 129 duplicate price schemes from DB
- Branch Pricing section in Product Detail now shows only current branch when on specific branch

---

## NEXT: QR Workflow Phases 3–6

See `/app/memory/ROADMAP.md` for full implementation spec.

### Phase 3 — QR Payment Receive (NEXT UP)
`POST /api/qr-actions/{code}/receive_payment`
- Receives cash/digital payments on invoices via QR scan
- Routes to existing wallet functions (update_cashier_wallet / update_digital_wallet)
- Updates customer AR balance
- Z-report picks up payments automatically (queries invoices.payments[])

### Phase 4 — PO Receive via QR
`POST /api/qr-actions/{code}/po_receive`
- Delegates to terminal_finalize_po() in purchase_orders.py
- Already-received POs: view-only (available_actions=[])

### Phase 5 — Transfer QR Receive
`POST /api/qr-actions/{code}/transfer_receive`
- Delegates entirely to receive_transfer() in branch_transfers.py
- Handles variance → received_pending automatically

### Phase 6 — Terminal Doc Code Entry
- Add "Find by Code" input in terminal shell header
- navigate('/doc/${code}') — no other changes needed

---

## Prioritized Backlog

### P1 — User Verification Pending
Phase 3 incident resolution (PIN auth + auto-journal entries for incident tickets) — completed but user never confirmed working.

### P2
- Visual trail for partial invoices (linked payment transactions)
- Smart Journal Entries for forgotten/back-dated sales
- Admin tool for corrupted POs in production DB
- Refactor SuperAdminPage.jsx (monolithic, 1000+ lines)
- Fix react-hooks/exhaustive-deps ESLint warnings (3 remaining)

### P3 (Future)
- Native Android APK (Capacitor wrap, thermal printer, Newland scanner SDK)
- Weight-embedded EAN-13 barcode recognition
- Automated Payment Gateway & Demo Login
- Advanced reporting, "Pack & Ship" workflow, user role presets

---

## Key Files Reference

### Backend
- `routes/qr_actions.py` — All QR actions (add phases 3/4/5 here)
- `routes/doc_lookup.py` — available_actions[] logic
- `routes/purchase_orders.py` — terminal_finalize_po() for Phase 4
- `routes/branch_transfers.py` — receive_transfer() for Phase 5
- `routes/invoices.py` — payment schema for Phase 3
- `routes/verify.py` — verify_pin_for_action(), _resolve_pin()
- `routes/stock_releases.py` — pending releases endpoints
- `routes/count_sheets.py` — snapshot/adjust with reserved_qty
- `routes/sales.py` — partial release creates sale_reservations + auto doc_code
- `routes/incident_tickets.py` — resolution workflow + journal entries
- `lib/verify.py` or `routes/verify.py` — PIN policies

### Frontend
- `pages/DocViewerPage.jsx` — ALL QR action UI. StockReleaseManager = pattern to follow.
- `pages/PendingReleasesPage.jsx` — Tracking page
- `pages/CountSheetsPage.js` — Shows system_reserved_qty breakdown
- `pages/UnifiedSalesPage.js` — Partial release toggle in checkout
- `pages/SalesPage.js` — Stock release status badges
- `pages/CloseWizardPage.js` — Pending releases warning in Step 1
- `components/InvoiceDetailModal.js` — Releases tab (shows stock_releases[])
- `components/Layout.js` — Sidebar nav (Pending Releases added)

## Test Reports
- `test_reports/iteration_15-17.json` — Phase 3 incident resolution
- Latest: all QR phases tested manually with curl + screenshots
