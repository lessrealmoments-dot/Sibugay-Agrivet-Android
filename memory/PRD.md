# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business (originally single-tenant). Now converting to a **subscription-based, multi-tenant SaaS platform** — similar to QuickBooks for Philippine retail businesses.

**Tagline:** Audit-Grade Retail Intelligence  
**Sub-tagline:** Serious control for serious businesses  
**Built for:** Growing businesses

---

## CRITICAL AGENT NOTE — VPS DEPLOYMENT
**EVERY TIME code is ready to deploy to agri-books.com, ALWAYS include these 3 commands:**

```bash
cd /var/www/agribooks && git pull origin main
supervisorctl restart agribooks-backend
cd frontend && yarn build
```

**Steps before running the above:**
1. User must click **"Save to Github"** in Emergent first to push the code
2. SSH into VPS: `ssh root@76.13.215.32`
3. Run the 3 commands above in order

**VPS Details:**
- Domain: `agri-books.com`
- IP: `76.13.215.32`
- User: `root`
- Backend managed by: `supervisorctl` (process name: `agribooks-backend`)
- Frontend: static build served by Nginx from `/var/www/agribooks/frontend/build/`
- No hot reload on VPS — backend needs supervisorctl restart, frontend needs yarn build

---

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
- **[SaaS] Multi-tenancy: organization_id isolation on all data**
- **[SaaS] Subscription plans: Basic/Standard/Pro with branch/user limits**
- **[SaaS] Public landing page + self-registration**
- **[SaaS] Super Admin platform management panel**

## Tech Stack
- Frontend: React (Create React App), Tailwind CSS, Shadcn/UI, Lucide icons
- Backend: FastAPI (Python), MongoDB
- Auth: JWT (with org_id + is_super_admin), TOTP (pyotp), Manager PINs
- Multi-tenancy: ContextVar-based TenantDB wrapper (transparent org isolation)
- File uploads: Cloudflare R2 (agribooks-files bucket)
- Offline: IndexedDB (idb pattern), syncManager

## Key Formulas — CASH RECONCILIATION

### Expected Counter (Z-Report)
```
total_cash_in = cash_sales + partial_cash + cash_AR_only + split_cash_portion
expected_counter = starting_float + total_cash_in - cashier_expenses_only
```
- `cashier_expenses_only` = expenses WHERE fund_source != "safe"
- `cash_AR_only` = AR payments WHERE fund_source == "cashier"
- Safe-paid expenses and digital AR payments are tracked separately

### Fund Source Rules
- Every expense stores `fund_source` ("cashier" or "safe")
- Cashier expenses affect the drawer; safe expenses don't
- AR payments track fund_source from payment method (cash→cashier, GCash/Maya→digital)
- Z-Report only subtracts cashier-sourced expenses from expected counter

## Prioritized Backlog

### P0 — Completed
- [x] Mandatory e-payment receipt upload (digital/split sales)
- [x] Financial integrity overhaul (9+ bug fixes across payment pipeline)
- [x] **AUDIT FIX (Mar 2026):** Return void now ADDS money back (was double-deducting)
- [x] **AUDIT FIX (Mar 2026):** Daily close expected_counter uses cashier-only expenses
- [x] **AUDIT FIX (Mar 2026):** Daily close separates cash AR vs digital AR
- [x] **AUDIT FIX (Mar 2026):** Payable payment creates expense + updates linked PO
- [x] **AUDIT FIX (Mar 2026):** All expense types store fund_source (cashier/safe)
- [x] **AUDIT FIX (Mar 2026):** PO adjustment safe_lot has correct schema
- [x] **AUDIT FIX (Mar 2026):** Individual payment void handles digital wallets
- [x] **AUDIT FIX (Mar 2026):** Batch close uses same corrected formulas

### P0 — Completed (Mar 2026 — Usability)
- [x] Dedicated top-level Expenses page (/expenses) in sidebar under Transactions
  - New `ExpensesPage.js` with full CRUD, filters, Farm Expense, Customer Cash Out
  - Reuses same backend endpoints — no backend changes, zero regression risk
  - Error handling hardened for object-type API error responses
- [x] Clickable invoice/PO numbers across entire app
  - All invoice numbers in 8 pages now open InvoiceDetailModal (view + edit with PIN)
  - PO numbers on Dashboard navigate to Purchase Orders page
  - Pages: DailyLogPage, DashboardPage, AccountingPage, ExpensesPage, ReportsPage, AuditCenterPage
  - SalesPage and PaymentsPage already had this — verified no regression

### P0 — Upcoming
- [ ] Fix broken PO data (admin tool to reprocess failed POs)
- [ ] Quick-action menu on Sales History page (Re-send Receipt, Print Invoice)
- [ ] Closing History page (view past Z-Reports with search by date/branch)

### P1 — Upcoming
- [ ] Weight-embedded EAN-13 barcode recognition in POS
- [ ] Convert app to PWA (installable, offline-first)
- [ ] Demo Login System
- [ ] Automated Payment Gateway (Stripe/PayPal)

### P2 — Backlog
- [ ] Refactor SuperAdminPage.jsx (1000+ lines)
- [ ] Refactor AdminLoginPage.jsx (SPA navigation)
- [ ] Weigh & send mode for phone scanner
- [ ] Quick-action user details on Team page
- [ ] Kiosk Mode for POS
- [ ] Advanced Reporting on barcode scan history
- [ ] Employee Cash Advance Summary Report
- [ ] User Roles & Presets
- [ ] "Pack & Ship" Workflow
- [ ] Smarter Price Suggestions

## 3rd Party Integrations
- Cloudflare R2: File storage
- Resend: Transactional emails
- Google Authenticator: 2FA
- fpdf2: PDF reports
- python-barcode: Backend barcode generation
- jsbarcode: Frontend barcode rendering
- html5-qrcode: Camera barcode scanning
