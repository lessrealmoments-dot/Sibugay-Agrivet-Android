# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business. Rebranded to "AgriBooks". Neutral accounting terms for government compliance.

## Core Requirements
- Offline Functionality with auto-sync
- Product Management (3000+ SKUs, parent/repack system)
- Multi-Branch Management (branch-specific data, owner overview, Branch Transfers)
- Advanced Accounting (expenses, receivables, fund management)
- Complex Pricing & Credit (tiers, interest/penalty system)
- Sales & Purchasing Workflow (unified interfaces)
- Daily Operations (Close Wizard, Z-Report, archive)
- Granular Permissions & Security (Inflow-Cloud-style, TOTP 2FA)
- Editable Invoices & POs (audit trail, Reopen PO)
- Inventory Management (count sheets, corrections, audit log)
- Employee & User Management (PINs, cash advances)
- Data Import (QuickBooks products)

## Tech Stack
- Frontend: React (Create React App), Tailwind CSS, Shadcn/UI, Lucide icons
- Backend: FastAPI (Python), MongoDB
- Auth: JWT, TOTP (pyotp), Manager PINs
- File uploads: Local disk (/app/uploads), QR-based upload + view system
- Offline: IndexedDB (idb pattern), syncManager

## Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── accounting.py
│   │   ├── audit.py            # Audit engine + offline package
│   │   ├── auth.py             # Login, TOTP, PIN verify
│   │   ├── backup.py
│   │   ├── branch_transfers.py
│   │   ├── branches.py
│   │   ├── count_sheets.py
│   │   ├── customers.py
│   │   ├── daily_operations.py
│   │   ├── dashboard.py
│   │   ├── employees.py
│   │   ├── import_data.py
│   │   ├── inventory.py
│   │   ├── invoices.py
│   │   ├── notifications.py
│   │   ├── price_schemes.py
│   │   ├── products.py
│   │   ├── purchase_orders.py
│   │   ├── reports.py
│   │   ├── returns.py
│   │   ├── sales.py
│   │   ├── settings.py
│   │   ├── setup.py
│   │   ├── suppliers.py
│   │   ├── sync.py
│   │   ├── uploads.py          # QR upload + view token
│   │   ├── users.py            # +is_auditor, +auditor_pin
│   │   └── verify.py           # NEW: Transaction verification
│   └── main.py
└── frontend/
    └── src/
        ├── App.js              # +/view-receipts/:token route
        ├── components/
        │   ├── Layout.js
        │   ├── OfflineIndicator.js
        │   ├── PriceScanManager.js
        │   ├── ReceiptGallery.js
        │   ├── UploadQRDialog.js
        │   ├── VerificationBadge.js  # NEW
        │   ├── VerifyPinDialog.js    # NEW
        │   └── ViewQRDialog.js       # NEW
        └── pages/
            ├── AccountingPage.js     # +verify/view buttons on expenses
            ├── AuditCenterPage.js    # +Discrepancies tab, +Prepare for Audit tab
            ├── BranchTransferPage.js # +verify/view buttons
            ├── PurchaseOrderPage.js  # +verify/view buttons + badge in list
            ├── ViewReceiptsPage.js   # NEW: public mobile gallery + verify
            └── ... (all other pages)
```

## What's Been Implemented (Chronological)

### Phase 1 — Core POS & Inventory (early sessions)
- Multi-branch setup, products, inventory, sales (POS + invoice)
- Customer management, price schemes, AR tracking
- Basic expense recording, fund management
- Daily Close Wizard, Z-Report

### Phase 2 — Advanced Features
- Branch Transfers with two-step GRN workflow (shortages/excesses)
- Purchase Order system (drafts, cash/credit, discounts, freight/VAT)
- Pay Supplier centralized page
- Branch-to-branch PO requests
- Customer Return & Refund Wizard

### Phase 3 — Audit & Reporting (recent sessions)
- AR Aging, Sales, Expense reports
- Comprehensive Audit Center with traffic-light scoring + rule-based insights
- Smart Price Scanner (detect negative-margin products)
- QR-based receipt upload system (all modules)
- Editable Reopened POs with payment adjustment workflow
- Backend hardening (prevent negative fund balances)

### Phase 4 — Verification & Audit Offline Pack (2026-02-24)
- **Transaction Verification System**:
  - Admin PIN (system setting, hashed) — `POST /api/verify/admin-pin/set`
  - Admin TOTP (Google Authenticator) — existing
  - Auditor PIN (users with `is_auditor=True`) — via user management
  - Verify POs, Expenses, Branch Transfers with pin dialog
  - Flag discrepancies: expected vs found qty + value impact calculation
  - `Verified ✅` / `Verified ⚠️ Discrepancy` / `Resolved` badges
- **Discrepancy Report** tab in Audit Center
  - Lists all unresolved discrepancies with value impact
  - Resolve: Apply Correction or Dismiss with justification
- **"View on Phone" QR** for uploaded photos
  - Generates read-only view token (1hr expiry)
  - Mobile-optimized gallery with swipe/pinch-to-zoom
  - Verify from phone with PIN
  - Shows transaction context + verification status
- **Prepare for Audit** tab in Audit Center
  - Auto-detects period from last 2 count sheets
  - Downloads all transactions to sessionStorage
  - Pre-fetches all photos via browser cache
  - Live progress indicator

## Key API Endpoints

### Verification (NEW)
- `POST /api/verify/admin-pin/set` — Set admin verification PIN (admin only)
- `GET /api/verify/admin-pin/status` — Check if PIN configured
- `POST /api/verify/{doc_type}/{doc_id}` — Verify a transaction
- `DELETE /api/verify/{doc_type}/{doc_id}` — Remove verification (admin only)
- `GET /api/verify/discrepancies` — List all discrepancies
- `POST /api/verify/discrepancies/{id}/resolve` — Resolve (apply/dismiss)

### Uploads (UPDATED)
- `POST /api/uploads/generate-view-token` — View-only QR token
- `GET /api/uploads/view-session/{token}` — Public: get files for view QR

### Audit (UPDATED)
- `GET /api/audit/offline-package` — Download all transactions + file metadata

## DB Schema Updates
- `system_settings`: `{key: "admin_pin", pin_hash, set_by, set_at}`
- `discrepancy_log`: `{id, doc_type, doc_id, doc_number, doc_title, doc_date, branch_id, item_description, expected_qty, found_qty, unit, unit_cost, value_impact, note, verified_by_name, verified_at, resolved, resolution, resolved_at, resolved_by}`
- `view_tokens`: `{id, token, token_type: "view", token_expires_at, record_type, record_id, record_summary, created_by, created_at}`
- `users`: Added `is_auditor: bool`, `auditor_pin: str`
- `purchase_orders/expenses/branch_transfer_orders`: Added verification fields

## Credentials
- Admin: `owner` / `521325`
- Admin Verification PIN: `1234` (set via /api/verify/admin-pin/set)
- Cashier: `cashier` / `1234`

## Prioritized Backlog

### P1 — Upcoming
- **Employee Cash Advance Summary Report** — Track advances by employee
- **User Role Presets** — Save named permission sets; user assigns by name

### P2 — Backlog
- "Pack & Ship" workflow for Branch Transfers (explicit packing confirmation)
- Resilient Offline Sync (Transaction Envelope + idempotent sync endpoint)
- Offline-first audit mode (persist audit package to IndexedDB, not just sessionStorage)

### Refactoring (Tech Debt)
- Break down PurchaseOrderPage.js, BranchTransferPage.js, CloseWizardPage.js into smaller components
