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

### QR Security Hardening (2026-03-17) — Complete
- **Gap 1 fixed:** PIN brute-force lockout per doc_code. 5 failures → admin alert; 10 failures → 15-min 429 lockout. Auto-resets on success.
- **Gap 2 fixed:** `receive_payment` and `transfer_receive` now require idempotency UUID (`payment_ref`, `transfer_ref`) — duplicate submissions rejected with 409.
- **Gap 3 fixed:** Every QR payment now writes a double-entry journal record (Debit Cash/Digital, Credit AR).
- **Gap 4 fixed:** `client_ip` and `user_agent` captured on every `qr_action_log` entry.
- **Gap 5 fixed:** `DocViewerPage.jsx` shows attempts-remaining warning (≤4 left) and a live countdown banner when locked.
- New functions in `utils/security.py`: `check_qr_lockout`, `log_failed_qr_pin_attempt`, `log_successful_qr_pin_attempt`, `_raise_qr_security_alert`.


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

### Terminal Smart QR Scan + Branch Security (2026-03-17) — Complete
- **BUG FIX:** QR pair token no longer hardcodes "admin" role — uses actual initiating user's role
- **BUG FIX:** `pull-po` and `pull-transfer` PIN are now branch-restricted (manager PINs only work for their branch)
- **BUG FIX:** Blank receipt reprint from DocViewer fixed — now uses `PrintEngine` with proper 58mm thermal + full-page format instead of `window.print()` on raw HTML
- **NEW:** `terminal_pull` and `qr_cross_branch_action` added to `PIN_POLICY_ACTIONS`; `qr_cross_branch_action` is TOTP-only (no static manager PIN allowed cross-branch)
- **NEW:** `GET /api/doc/search?q=...&branch_id=...` endpoint — branch-scoped search by invoice number, PO number, or transfer order number; returns `doc_code` for navigation
- **NEW:** Global H10P HID keyboard wedge scanner in `TerminalShell` — detects doc codes (8-char alphanumeric), URLs containing doc codes, `agrismart://` deeplinks, and invoice numbers from hardware scanner input; routes to correct action across all tabs
- **NEW:** Smart doc search in terminal header — accepts invoice/PO/transfer numbers, shows dropdown of matching results with doc codes
- **NEW:** DocViewerPage cross-branch enforcement — when `?branch=` param doesn't match doc's branch, shows TOTP-only unlock gate; after TOTP verification, actions are unlocked with audit trail
- **NEW:** Terminal navigation to `/doc/` always passes `?branch=session.branchId` for proper cross-branch detection

### Capacitor APK Wrapper + H10P Printer SDK (2026-03-18) — Complete
- **Capacitor setup**: `@capacitor/core@6` + `@capacitor/android@6` installed, `capacitor.config.ts` created in live-URL mode (always loads `https://agri-books.com`, no APK rebuild for web updates)
- **Android project generated**: `frontend/android/` — full Capacitor Android project structure
- **H10P Printer AIDL files**: `PrinterInterface.aidl`, `PSAMCallback.aidl`, `PSAMData.aidl` placed in correct AIDL directory (`recieptservice.com.recieptservice` package)
- **Native plugin**: `H10PPrinterPlugin.java` — binds to `recieptservice.com.recieptservice.service.PrinterService`, renders HTML→Bitmap via headless WebView, calls `printer.beginWork()` → `printer.printBitmap(bitmap)` → `printer.endWork()`
- **PrintBridge.js**: environment-aware router — detects `Capacitor.isNativePlatform()`, routes to SDK on H10P or `window.print()` on browser
- **H10PPrinterPlugin.js**: Capacitor JS interface with web browser fallback
- **PrintEngine.js**: added `generateHtml()` method (returns HTML without print script, used by PrintBridge for native path)
- **Terminal print call sites updated**: `TerminalSales.jsx`, `TerminalShell.jsx`, `DocViewerPage.jsx` — all use `PrintBridge.print()` instead of `PrintEngine.print()`
- **PWA manifest updated**: `start_url: /terminal`, `orientation: portrait` — ready for "Add to Home Screen"
- **Build guide**: `frontend/ANDROID_BUILD_GUIDE.md` — complete step-by-step APK build instructions
- **AAR placeholder**: `android/app/libs/README.txt` — user must copy `printer-release.aar` here before building
- When the H10P Newland scanner reads a document QR code, a bottom sheet appears INSTANTLY
- Shows: doc number, customer/supplier, amount, status, item count
- **Three actions:** [Print 58mm Thermal] [Print Full Page] [View / Take Action]
- Reprint happens directly without navigating away — no PIN needed for reprinting
- Uses `PrintEngine` with `basicDocToPrintData()` transformer to map public doc view fields to PrintEngine format
- Falls back to doc viewer navigation if doc not found

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

### QR Operational Workflows — Phase 3 (Complete — Mar 2026)
- `POST /api/qr-actions/{code}/receive_payment` — PIN-gated, Cash→cashier wallet, Digital→digital wallet, updates customer AR
- `ReceivePaymentPanel` inside Tier 2 of DocViewerPage.jsx (reuses Tier 2 unlock PIN)
- Reflects in Z-report and payment history automatically

### QR Operational Workflows — Phase 4 (Complete — Mar 2026)
- `POST /api/qr-actions/{code}/transfer_receive` — PIN-gated, delegates to `receive_transfer()` with synthetic user
- Exact match → inventory moves immediately (status: received). Variance → received_pending, source branch notified
- `TransferReceivePanel` in DocViewerPage.jsx — locked → PIN → qty inputs → confirm → done
- `verify_pin` endpoint made generic (works for both invoice and branch_transfer)
- Branch transfer items in open view now include `product_id`

### QR Operational Workflows — Phase 5 (Complete — Mar 2026)
- Terminal Doc Code Entry: Search icon in TerminalShell header → type code → navigate to /doc/{code}

### Branch Transfer Security Fixes (Complete — Mar 2026)
- View modal: "Confirm Receipt" only shows for destination branch (sender cannot see it)
- View modal: "Verify" button restricted to admin/auditor only
- Backend: `receive_transfer()` now guards against non-destination-branch users (403)

### admin_totp Removed (Complete — Mar 2026)
- Merged into standard `totp` method. Removed from PIN_METHODS, QR policy defaults updated.

### PO Bug Fix (Complete — Mar 2026)
- `setSourceType`/`setSupplyBranchId`/`setShowRetailToggle` missing useState declarations added to PurchaseOrderPage.js

### Sales Order Redesign & Security Hardening (Complete — Mar 2026)
- **UI Redesign:** Order mode form in `UnifiedSalesPage.js` matches inFlow layout
- **Date as Single Source of Truth:** Removed `invoice_date`, `order_date` is sole controller for reports
- **Timezone Fix:** Default date uses browser's local time (PHT), not UTC
- **Synchronized Date UI:** Sale Date field and Unclosed Days banner are perfectly synced
- **Closed-Day Guard:** Frontend + backend block sales on formally closed days (Z-report finalized)
- **Floor-Date Guard (System Start):** Backend rejects dates before the branch's earliest operational date. Frontend `min` attribute on date input. Prevents encoding sales before the system existed.
- **Collapsible Order Header:** Customer Details & Order Info section is collapsible (collapsed by default), giving more vertical space to the product entry table
- **Editable Customer Info:** Contact/Phone and Billing Address fields are editable when a customer is selected. Pre-checkout dialog asks "Save to customer record?" or "Use for this order only?" before proceeding to payment.

See `/app/memory/ROADMAP.md` for full implementation spec.

### Dashboard Widget Collapse Fix (Complete — Mar 2026)
- Added `MIN_H_MAP` / `MIN_W_MAP` constants; all layout items now carry `minH`/`minW` guards
- `validateLayouts()` sanitizes stale/corrupted `localStorage` layouts on load
- Enabled `isResizable={true}` with `se` resize handles on both Owner & Branch grids
- Fixed critical P0 bug: added getDerivedStateFromProps pattern (`prevLayoutKey` guard) so layouts reset synchronously on owner↔branch view switch — no widget collapses after branch change
- Added CSS for resize handle (bottom-right corner indicator)

### Controlled Negative Stock Override (Complete — Mar 2026)
- Hard stock block replaced with structured 422 `insufficient_stock` response listing all failing items
- `InsufficientStockModal` in `UnifiedSalesPage.js`: 3 options — Encode PO, Manager Override, Cancel
- Manager Override requires PIN (`stock_negative_override` policy: manager_pin / admin_pin / totp)
- Override passes `manager_override_pin` on retry; backend verifies PIN, skips stock guard, allows negative inventory
- Auto-creates `incident_tickets` record (`ticket_type: "negative_stock_override"`, `status: open`) per overridden item — linked to invoice, records who approved and method
- Inventory page: negative items show red "Negative — Investigate" badge with red row background
- Close Wizard Step 1: non-blocking warning banner listing negative items + link to Incident Tickets
- Count Sheets snapshot: items with negative available qty get `has_negative_stock: true` flag + "⚠ Negative — check open ticket" warning in red
- Low-stock alert endpoint: `negative_stock` status added, sorts above `out_of_stock`
- Moving average: completely unaffected (only `purchase`/`transfer_in` movements update MA)
- Offline: same as before — offline sync already allows negative with `stock_warnings`; online path now consistent


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

### P1
- Cross-branch payment wallet routing (cash at receiving branch's wallet)
- Admin tool for corrupted POs in production DB

### P2
- Visual trail for partial invoices (linked payment transactions)
- Smart Journal Entries for forgotten/back-dated sales
- Refactor SuperAdminPage.jsx (monolithic, 1000+ lines)
- Fix react-hooks/exhaustive-deps ESLint warnings (3 remaining)
- Update AdminLoginPage.jsx to use useNavigate

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
