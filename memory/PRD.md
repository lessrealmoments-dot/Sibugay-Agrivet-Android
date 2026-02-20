# AgriPOS - Multi-Branch Inventory, POS & Accounting System

## Original Problem Statement
Build an Accounting, Inventory, and POS website for multibranch management, similar to QuickBooks Online and Inflow Inventory Online, with unique features including:
- Parent Product & Repack system with auto stock deduction
- Offline POS with auto-sync capability
- 3000+ SKU support with preset product setup
- Multiple price schemes (Retail, Wholesale, Special, Government)
- Granular role-based permissions (Inflow Cloud style)
- Advanced accounting (expenses, receivables, payables)
- QuickBooks-style editable invoices with audit trail

## User Personas
1. **Admin/Owner** - Full system access, manages all branches, users, and financial data
2. **Branch Manager** - Manages branch operations, inventory, sales, with configurable permissions
3. **Cashier** - POS operations, customer service, limited system access
4. **Inventory Clerk** - Stock management, purchase orders, receiving

## Architecture
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui components
- **Backend**: FastAPI (Python) with JWT authentication
- **Database**: MongoDB with Motor async driver
- **Design**: Manrope + IBM Plex Sans fonts, Forest Green (#1A4D2E) primary, dark sidebar layout

## Latest Update (Dec 2025)

### Multi-Branch Frontend Integration - COMPLETE ✅ (Dec 20, 2025)
- **Owner Dashboard**: Consolidated view showing all branches with KPIs
  - Total Sales Today, Total Cash Position, Total Receivables, Low Stock Alerts
  - Branch Performance Grid with individual branch stats
  - Top Performing branches ranked, Alerts per branch
- **Branch Selector**: Admin can switch between "All Branches" and specific branch
- **Auto Branch Filtering**: API calls auto-append branch_id via axios interceptor
- **Branch-Locked Users**: Cashiers see only their assigned branch (locked selector)

### Count Sheets Feature - COMPLETE ✅ (Dec 20, 2025)
Inflow-style inventory verification and adjustment system:
- **Snapshot**: Captures system inventory at point in time
- **Split Counting**: Displays/inputs as "9 boxes + 50 tablets" for fractional qty
- **Category Grouping**: Items sorted alphabetically by category
- **Strict Mode**: All items must be counted before completion
- **One Active**: Only one count sheet per branch at a time
- **Adjustments**: Apply variances to inventory with full audit trail

### Backend Modular Refactor - COMPLETE ✅
- Migrated from 3800-line monolith to 18 modular route files
- Entry: `server.py` → `main.py` (all routers)
- Multi-branch data isolation verified

## What's Been Implemented

### Phase 10: Granular Permission System (Feb 19, 2026) ✅
**Inflow Cloud-style user permission management - COMPLETE**

Features:
- **User Permissions Page** (`/user-permissions`)
  - Left panel: User list with role badges (admin, manager, cashier, etc.)
  - Right panel: Permission editor with toggles for each action
  - Click user to select and load their permissions

- **Permission Modules** (12 modules, 53 total permissions)
  - Dashboard, Branches, Products, Inventory
  - Sales/POS, Purchase Orders, Suppliers, Customers
  - Accounting, Price Schemes, Reports, Settings

- **Per-Action Toggles**
  - Each module has specific actions: view, create, edit, delete
  - Special permissions: view_cost, sell_below_cost, give_discount, void, manage_credit, etc.

- **Role Presets**
  - Administrator: Full access to everything
  - Branch Manager: Manage branch ops, limited admin
  - Cashier: POS operations only
  - Inventory Clerk: Stock management focus
  - Custom: Manual per-user configuration

- **Quick Actions**
  - "None" button: Disable all permissions for a module
  - "All" button: Enable all permissions for a module
  - "Apply Preset" dropdown: Apply predefined role

- **Unsaved Changes**
  - Yellow banner shows pending changes
  - Discard/Save buttons for user confirmation

New Endpoints:
- `GET /api/permissions/modules` - All permission modules with actions
- `GET /api/permissions/presets` - All role presets
- `GET /api/permissions/presets/{key}` - Specific preset details
- `GET /api/users/{id}/permissions` - User's current permissions
- `PUT /api/users/{id}/permissions` - Update all permissions
- `PUT /api/users/{id}/permissions/module/{module}` - Update specific module
- `POST /api/users/{id}/apply-preset` - Apply preset to user

### Phase 9: Invoice Editor Feature (Feb 19, 2026) ✅
- QuickBooks-style invoice viewer/editor with audit trail
- Edit with mandatory reason, creates edit history
- Inventory auto-adjustment on quantity changes

### Phase 8: Interest & Penalty Enhancement (Feb 19, 2026) ✅
- Grace period support, auto-preview charges
- Simple daily interest formula

### Phase 7: Unified Sales System (Feb 19, 2026) ✅
- Combined Quick POS + Sales Order workflow
- Cash, Partial, Credit payment options
- Manager PIN approval for credit sales

### Previous Phases ✅
- Customer Transaction History
- Dashboard with Combined Receivables
- Offline POS with IndexedDB + auto-sync
- Purchase Orders with receiving + cost updates
- Fund Management (Cashier, Safe, Bank wallets)
- Daily Operations (Sales log, profit report, day close)
- Supplier Management with transaction history
- Parent/Repack inventory system

## Current File Structure (Modular Architecture)
```
/app
├── backend/
│   ├── server.py          # Entry point (imports from main.py)
│   ├── main.py            # FastAPI app with all routers
│   ├── config.py          # Centralized configuration
│   ├── server_legacy.py   # Old monolith (backup)
│   ├── ARCHITECTURE.md  
│   ├── utils/
│   │   ├── __init__.py    # Exports all utilities
│   │   ├── auth.py        # Auth: JWT, password hashing, permissions
│   │   ├── helpers.py     # now_iso, new_id, log_movement, etc.
│   │   └── branch.py      # Multi-branch: get_branch_filter, etc.
│   ├── models/
│   │   ├── __init__.py
│   │   └── permissions.py # PERMISSION_MODULES, ROLE_PRESETS
│   ├── routes/            # All API routes (17 modules)
│   │   ├── __init__.py    # Exports all routers
│   │   ├── auth.py        # Login, register, PIN verification
│   │   ├── branches.py    # Branch CRUD
│   │   ├── users.py       # User management, permissions
│   │   ├── products.py    # Products, repacks, pricing
│   │   ├── customers.py   # Customer CRUD with branch support
│   │   ├── inventory.py   # Stock levels, adjustments, transfers
│   │   ├── price_schemes.py # Price scheme management
│   │   ├── invoices.py    # Invoices, payments, interest, editing
│   │   ├── sales.py       # Unified sales endpoint
│   │   ├── purchase_orders.py # PO CRUD, receiving, payments
│   │   ├── dashboard.py   # Stats, branch summary
│   │   ├── accounting.py  # Fund wallets, expenses, AR/AP
│   │   ├── daily_operations.py # Daily log, report, close day
│   │   ├── suppliers.py   # Supplier CRUD
│   │   ├── employees.py   # Employee management, advances
│   │   ├── sync.py        # Offline POS data sync
│   │   └── settings.py    # Invoice prefixes, terms options
│   ├── tests/
│   └── .env
└── frontend/
    └── src/
        ├── components/
        ├── pages/
        └── App.js
```

## Default Credentials
- Username: admin
- Password: admin123
- Manager PIN: 1234

## Prioritized Backlog (Updated Feb 19, 2026)

### P0 (Critical - Completed) ✅
- [x] **Granular Permission System** (Inflow Cloud style)
- [x] **Invoice Editor** with audit trail
- [x] **Interest & Penalty with Grace Period**
- [x] **Unified Sales Interface**
- [x] **Customer Transaction Tracking**

### P1 (High Priority - Next)
- [x] **Backend Modular Refactoring - COMPLETE** (Dec 2025)
  - Created modular foundation: config.py, utils/, models/, routes/
  - Extracted ALL routes into 17 modular files
  - main.py orchestrates all routers
  - server.py is now a thin entry point
  - Old monolith backed up as server_legacy.py
  - Total: 17 route modules with 80+ endpoints
  - All modules tested and working
  
- [x] **Multi-Branch Data Isolation - COMPLETE** (Dec 2025)
  - Branch utilities in utils/branch.py
  - Branch filtering on all relevant endpoints
  - Dashboard shows multi-branch view for admin
  - /dashboard/branch-summary for owner overview
  - Cashier sees only their branch data

### P2 (Medium Priority)
- [ ] Advanced Reporting Dashboards
- [ ] Barcode scanning support
- [ ] Receipt printing (thermal)
- [ ] Bulk Import/Export (CSV)

### P3 (Future)
- [ ] Stock alerts and notifications
- [ ] Multi-currency support
- [ ] Mobile app API
- [ ] Audit trail / activity logs

## Key API Endpoints
- `GET /api/permissions/modules` - All permission modules
- `GET /api/permissions/presets` - Role presets
- `PUT /api/users/{id}/permissions` - Update permissions
- `POST /api/users/{id}/apply-preset` - Apply preset
- `GET /api/invoices/{id}` - Invoice with edit history
- `PUT /api/invoices/{id}/edit` - Edit invoice with reason
- `GET /api/customers/{id}/charges-preview` - Preview interest/penalty
- `POST /api/unified-sale` - Create sale (cash/partial/credit)
- `POST /api/auth/verify-manager-pin` - Verify manager PIN

## Testing Status
- **Granular Permissions**: 100% tested (12 backend, all frontend features)
- **Test reports**: /app/test_reports/iteration_18.json
