# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business (originally single-tenant). Now converting to a **subscription-based, multi-tenant SaaS platform** — similar to QuickBooks for Philippine retail businesses.

**Tagline:** Audit-Grade Retail Intelligence  
**Sub-tagline:** Serious control for serious businesses  
**Built for:** Growing businesses

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
- File uploads: Local disk (/app/uploads), QR-based upload + view system
- Offline: IndexedDB (idb pattern), syncManager

## Subscription Plans (Pricing)
| Plan | PHP/mo | USD/mo | Branches | Users |
|------|--------|--------|----------|-------|
| Basic | ₱1,500 | $30 | 1 | 5 |
| Standard | ₱4,000 | $80 | 2 | 15 |
| Pro | ₱7,500 | $150 | 5 | Unlimited |
| Extra Branch | ₱1,500 | $30 | +1 per addon | - |
| Trial | Free | Free | 5 (Pro features) | Unlimited |

Annual billing: 2 months free (pay 10 months, get 12).

## Architecture
```
/app
├── backend/
│   ├── config.py           # TenantDB wrapper + ContextVar org isolation
│   ├── routes/
│   │   ├── auth.py         # Email/username login, org subscription in /me
│   │   ├── organizations.py # Registration, plans, /my org info
│   │   ├── superadmin.py   # Platform admin (orgs, stats, subscription mgmt)
│   │   └── ... (all existing routes - unchanged, tenant isolation is transparent)
│   └── main.py             # Startup migration + super admin creation
└── frontend/
    └── src/
        ├── App.js          # New routes: /, /register, /upgrade, /superadmin
        ├── pages/
        │   ├── LandingPage.js    # NEW: Public marketing page
        │   ├── RegisterPage.js   # NEW: Company self-registration
        │   ├── LoginPage.js      # UPDATED: Email/username login
        │   ├── UpgradePage.js    # NEW: Subscription upgrade with QR payment
        │   ├── SuperAdminPage.js # NEW: Platform admin panel
        │   └── ... (all existing pages unchanged)
        ├── components/
        │   └── Layout.js         # UPDATED: Trial expiry banner, upgrade link
        └── contexts/
            └── AuthContext.js    # UPDATED: Email login, subscription state
```

## Key API Endpoints

### SaaS (NEW)
- `POST /api/organizations/register` — Self-registration (public)
- `GET /api/organizations/plans` — Plan definitions (public)
- `GET /api/organizations/my` — Current org info + subscription
- `GET /api/superadmin/organizations` — All orgs (super admin only)
- `PUT /api/superadmin/organizations/{id}/subscription` — Update plan
- `GET /api/superadmin/stats` — Platform stats

### Auth (UPDATED)
- `POST /api/auth/login` — Now accepts `email` or `username`, returns subscription info
- `GET /api/auth/me` — Now includes subscription info

## DB Schema (Key)
### organizations (NEW collection)
```json
{
  "id": "uuid",
  "name": "Company Name",
  "owner_email": "admin@co.com",
  "plan": "trial|basic|standard|pro|suspended",
  "subscription_status": "trial|active|expired|suspended",
  "trial_ends_at": "ISO date",
  "max_branches": 1,
  "max_users": 5,
  "extra_branches": 0,
  "is_default": false,
  "is_demo": false
}
```
### All existing collections
Added `organization_id` field to all 20+ collections via TenantDB migration.

## Super Admin Access
- Portal: `/admin` (NOT linked from any public page — security by obscurity)
- Email: janmarkeahig@gmail.com
- Password: Aa@58798546521325
- TOTP: Google Authenticator (setup required on first login at /admin)
- Recovery: 8 backup codes generated on TOTP setup (emailed + shown once)

## Regular Admin (Default Org)
- Email: sibugayagrivetsupply@gmail.com
- Password: 521325

## Prioritized Backlog

### P0 — Critical SaaS (COMPLETED ✅)
- [x] Multi-tenancy foundation (TenantDB wrapper)
- [x] Email-only login (removed username)
- [x] Self-registration + 14-day trial
- [x] Landing page with dynamic pricing + feature table (live from backend)
- [x] Super Admin panel (v3: 4-tab Overview/Organizations/Feature Flags/Payment Settings)
  - [x] Feature Flags tab — toggle per-plan per-feature with All On/Off, Save & Publish
  - [x] Dynamic feature matrix stored in DB, fetched by landing page
  - [x] Pricing cards show live top features from DB
- [x] Separate admin portal at /admin with Google Authenticator TOTP + backup codes
- [x] Email notifications via Resend (welcome, trial warning, grace, locked, activated)
- [x] 3-day grace period + daily subscription check scheduler - sends warnings + locks expired accounts

### P1 — Upcoming
- Employee Cash Advance Summary Report
- User Role Presets (save named permission sets)
- Demo organization with realistic seed data
- Payment QR codes (actual Maya/GCash/Bank/PayPal QR codes)

### P2 — Backlog
- "Pack & Ship" workflow for Branch Transfers
- Resilient Offline Sync improvements
- Annual billing automation
- Stripe/PayMongo integration for automated billing
