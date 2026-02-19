# AgriPOS - Multi-Branch Inventory, POS & Accounting System

## Original Problem Statement
Build an Accounting, Inventory, and POS website for multibranch management, similar to QuickBooks Online and Inflow Inventory Online, with unique features including:
- Parent Product & Repack system with auto stock deduction
- Offline POS with auto-sync capability
- 3000+ SKU support with preset product setup
- Multiple price schemes (Retail, Wholesale, Special, Government)
- Granular role-based permissions
- Advanced accounting (expenses, receivables, payables)

## User Personas
1. **Admin/Owner** - Full system access, manages all branches, users, and financial data
2. **Branch Manager** - Manages branch operations, inventory, sales, with configurable permissions
3. **Cashier** - POS operations, customer service, limited system access

## Architecture
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui components
- **Backend**: FastAPI (Python) with JWT authentication
- **Database**: MongoDB with Motor async driver
- **Design**: Manrope + IBM Plex Sans fonts, Forest Green (#1A4D2E) primary, dark sidebar layout

## Core Requirements
- [x] JWT-based authentication with role-based access control
- [x] Granular toggleable permissions per user (view/create/edit/delete per module)
- [x] Multi-branch management (CRUD branches)
- [x] Product management with Parent/Repack system
- [x] Repack auto-generation from parent products with SKU linking
- [x] Inventory management per branch with stock adjustments and transfers
- [x] **UPDATED: Unified Sales Interface** - Combined Quick POS and Sales Order with mode toggle
- [x] **UPDATED: Derived Repack Inventory** - Repacks don't have their own stock; calculated from parent
- [x] Multiple price schemes (Retail, Wholesale, Special, Government)
- [x] Customer management with price scheme assignment
- [x] **UPDATED: Customer Transaction History** - View all invoices and balances per customer
- [x] Accounting: Expenses tracking, Receivables, Payables with payment recording
- [x] Sales history with void capability (restores inventory)
- [x] **UPDATED: Dashboard with Combined Receivables** - Shows total from invoices + legacy AR
- [x] User management with role assignment and password reset

## Unified Sales System (Feb 19, 2026)

### How It Works:
1. **Single page** (`/sales-new`) with mode toggle: Quick vs Order
2. **Quick Mode**: Product grid, fast cart operations, walk-in optimized
3. **Order Mode**: Excel-style line items with Terms, PO#, full invoice features
4. **Unified Checkout**:
   - **Cash**: Full payment → Invoice status: `paid`
   - **Partial**: Partial payment → Balance to AR, status: `partial`
   - **Credit**: No payment → Full amount to AR, status: `open`
5. **Credit Controls**:
   - Credit limit check before sale
   - Manager PIN approval required for credit/partial sales
6. **All sales create invoices** for proper tracking

### Manager PIN System:
- Managers/Admins set their PIN via `/auth/set-manager-pin`
- Default admin PIN: `1234`
- PIN required for: Credit sales, Partial payments, Credit limit overrides

### Customer Account Integration:
- All invoices reflect on customer account
- Transaction history shows all invoices + legacy receivables
- Balance updates in real-time

## Parent/Repack Inventory System (Feb 19, 2026)

### How It Works:
1. **Parent products** have real inventory in the `inventory` collection
2. **Repacks have NO inventory** - their stock is calculated dynamically:
   - `Repack Available = Parent Stock × units_per_parent`
3. **When repack is sold**:
   - Parent inventory is deducted: `parent_deduction = quantity_sold / units_per_parent`
   - No change to repack inventory (doesn't exist)
4. **Cannot adjust repack inventory** - must adjust parent instead

## What's Been Implemented

### Phase 7: Unified Sales System (Feb 19, 2026)
- **Unified Sales Page** (`/sales-new`): Combined Quick POS + Sales Order with mode toggle
- **Payment Options**: Cash (immediate), Partial (balance to AR), Credit (full to AR)
- **Manager Approval**: PIN verification for credit sales (1234 default)
- **Credit Limit Check**: Validates customer credit limit before sale
- **Customer Transactions**: Full history view with summary cards
- **Dashboard Receivables**: Combined total from invoices + legacy receivables
- **New Endpoints**:
  - `POST /api/unified-sale` - Create sale with payment handling
  - `POST /api/auth/verify-manager-pin` - Verify manager PIN
  - `PUT /api/auth/set-manager-pin` - Set manager PIN
  - `GET /api/customers/{id}/transactions` - Get customer transaction history

### Previous Phases
- Offline POS with IndexedDB + auto-sync
- Purchase Orders with receiving + cost updates
- Fund Management (Cashier, Safe, Bank wallets)
- Daily Operations (Sales log, profit report, day close)
- Supplier Management with transaction history
- Parent/Repack inventory system
- Enhanced expense management (Farm, Cash Out workflows)

## Current File Structure
```
/app
├── backend/
│   ├── server.py        # Main API server (~2700 lines)
│   ├── ARCHITECTURE.md  # Complete API documentation
│   ├── tests/           # Backend tests
│   └── .env
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── UnifiedSalesPage.js   # NEW: Combined Quick/Order sales
    │   │   ├── CustomersPage.js      # Updated: Transaction history
    │   │   ├── DashboardPage.js      # Updated: Combined receivables
    │   │   └── ... other pages
    │   ├── components/
    │   └── App.js
```

## Default Credentials
- Username: admin
- Password: admin123
- Manager PIN: 1234

## Prioritized Backlog (Updated Feb 19, 2026)

### P0 (Critical - Completed)
- [x] **Unified Sales Interface** - Combined Quick/Order modes with credit controls
- [x] **Customer Transaction Tracking** - All sales reflect on customer account
- [x] **Dashboard Receivables** - Shows combined total

### P1 (High Priority)
- [ ] Advanced Reporting Dashboards (monthly/quarterly summaries, sales incentive tracking)
- [ ] Barcode scanning support in POS
- [ ] Receipt printing (thermal printer support)
- [ ] **Backend Modular Refactoring** - Split server.py into routes/services/models

### P2 (Medium Priority)
- [ ] User Roles & Permissions UI (dedicated management page)
- [ ] Bulk Data Import/Export (CSV for products)
- [ ] Stock alerts and notifications
- [ ] Product images and categories management

### P3 (Low/Future)
- [ ] Multi-currency support
- [ ] API for mobile app
- [ ] Audit trail / activity logs
- [ ] Data backup and export
- [ ] Dashboard charts with Recharts

## Key API Endpoints (New/Updated)
- `POST /api/unified-sale` - Create sale (cash/partial/credit)
- `POST /api/auth/verify-manager-pin` - Verify manager PIN
- `PUT /api/auth/set-manager-pin` - Set manager PIN
- `GET /api/customers/{id}/transactions` - Customer transaction history
- `GET /api/dashboard/stats` - Dashboard stats with combined receivables
