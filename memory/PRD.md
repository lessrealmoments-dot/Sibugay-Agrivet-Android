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

## Architecture
```
/app
├── backend/
│   ├── config.py           # TenantDB wrapper + ContextVar org isolation
│   ├── routes/
│   │   ├── auth.py         # Email/username login, org subscription in /me
│   │   ├── daily_operations.py # Close Wizard, Z-Report, batch close
│   │   ├── sales.py        # Unified sales endpoint
│   │   ├── accounting.py   # Expenses, fund wallets, receivables
│   │   └── ... (all existing routes)
│   └── utils/helpers.py    # log_sale_items, fund wallet helpers
└── frontend/
    └── src/
        └── pages/
            └── CloseWizardPage.js # 8-step closing wizard + batch mode
```

## Key API Endpoints

### Daily Close / Closing Wizard
- `GET /api/daily-log?branch_id=X&date=Y` — Sales log with by_payment_method summary
- `GET /api/daily-close-preview?branch_id=X&date=Y` — Cash reconciliation preview
- `GET /api/daily-close/unclosed-days?branch_id=X` — Detect unclosed days
- `GET /api/daily-close-preview/batch?branch_id=X&dates=d1,d2,d3` — Batch preview
- `POST /api/daily-close` — Close single day
- `POST /api/daily-close/batch` — Close multiple days as one record
- `GET /api/daily-close/{date}` — Get close status

## Closing Wizard Steps
1. **Sales Log** — ALL sales (cash, GCash, Maya, split, credit) in sequential order with payment badges
2. **Customer Credits** — Per-invoice item breakdown with partial payment status (Total/Paid/Balance)
3. **AR Payments** — Payments received on existing credit
4. **Expenses** — Grouped by category (Farm, Cash-out, Employee Advance, regular) with subtotals
5. **Actual Count** — Cash breakdown (Opening Float, Cash Sales, Partial, AR, Total Cash In, Expenses, Expected) + E-Wallet display
6. **Fund Allocation** — Vault + Opening Float distribution
7. **Close & Sign Off** — Z-Report with Cash Drawer Reconciliation, Per-Day Breakdown (batch), Credit/Expense/Digital summaries, Manager PIN
8. **Open Tomorrow** — Success + next day

## Batch Close Feature
- Available when 2+ unclosed days detected
- "Close All as Group" button enters batch mode
- All sales, credits, expenses combined into single closing record
- Requires reason field + Manager PIN
- Per-day breakdown in Z-Report (sales by payment method, expenses per day)
- Placeholder records created for each individual date (marked as batch_member)
- Wallet updated to reflect combined closing

## Super Admin Access
- Portal: `/admin`
- Email: janmarkeahig@gmail.com
- Password: Aa@58798546521325

## Prioritized Backlog

### P0 — Completed
(See CHANGELOG.md for full history)

### P0 — Current / In Progress
- [x] Closing Wizard Phase 1-4: Fixed Sales Log, Credits, Expenses, Actual Count, Z-Report
- [x] Closing Wizard Phase 5: Batch/Group closing with combined Z-Report
- [x] Quantity decimal support (0.5 for half bags) in Quick Sales
- [x] Split payment receipt upload QR (same as digital payments)
- [x] E-payment verification section in Sales History (platform, ref#, photos, verify button)
- [x] Split payment recording fix: cash portion → Cash Sales, digital portion → Digital Sales

### P0 — Upcoming
- [ ] Closing History page (view past Z-Reports with search by date/branch)
- [ ] Sales History per day or per closing period

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
