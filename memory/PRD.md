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
- [x] **Unified Sales Interface** - Combined Quick POS and Sales Order with mode toggle
- [x] **Derived Repack Inventory** - Repacks don't have their own stock; calculated from parent
- [x] Multiple price schemes (Retail, Wholesale, Special, Government)
- [x] Customer management with price scheme assignment
- [x] **Customer Transaction History** - View all invoices and balances per customer
- [x] **Enhanced Interest & Penalty System** - With grace period and auto-preview
- [x] Accounting: Expenses tracking, Receivables, Payables with payment recording
- [x] Sales history with void capability (restores inventory)
- [x] **Dashboard with Combined Receivables** - Shows total from invoices + legacy AR
- [x] User management with role assignment and password reset

## Interest & Penalty System (Feb 19, 2026)

### How It Works:

```
Invoice Date ──→ Due Date ──→ Grace Period ──→ Interest Starts
                                (7 days)

Example: Invoice Jan 1, Terms: Net 30, Grace: 7 days
Jan 1 ──→ Jan 31 ──→ Feb 7 ──→ Interest starts Feb 8
(Invoice)  (Due)    (Grace ends)
```

### Interest Calculation:
- **Formula**: `Interest = Balance × (Rate% / 30) × Days Past Grace`
- **Example**: ₱10,000 balance, 3% monthly, 15 days overdue past grace
  - Interest = 10,000 × (3/100/30) × 15 = ₱150

### Features:
1. **Auto-Preview** (`GET /customers/{id}/charges-preview`)
   - Shows computed interest WITHOUT creating invoices
   - Displays breakdown per invoice with days overdue
   - Used when receiving payments

2. **Generate Interest Button** (`POST /customers/{id}/generate-interest`)
   - Creates a single Interest Charge invoice
   - Only for invoices past grace period
   - Updates `last_interest_date` to prevent double-charging

3. **Generate Penalty Button** (`POST /customers/{id}/generate-penalty`)
   - One-time flat rate penalty (default 5%)
   - Only for invoices past grace period
   - Marks invoices with `penalty_applied: true`

4. **Per-Customer Configuration**:
   - `interest_rate`: Monthly interest rate (%)
   - `grace_period`: Days after due date before interest starts (default 7)

### Invoice Fields:
- `interest_rate`: Rate for this invoice (fallback to customer rate)
- `last_interest_date`: Last date interest was computed
- `penalty_applied`: Boolean flag (one-time penalty)
- `penalty_date`: When penalty was applied

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

### Phase 8: Interest & Penalty Enhancement (Feb 19, 2026)
- **Grace Period Support**: 7-day default, configurable per customer
- **Auto-Preview Charges**: See computed interest before generating
- **Interest Formula**: Simple daily `Balance × (Rate%/30) × Days`
- **One-Time Penalty**: Flat rate, tracks `penalty_applied` per invoice
- **Customer Fields**: Added `interest_rate` and `grace_period`
- **Enhanced UI**: Shows grace period info, interest breakdown

### Phase 7: Unified Sales System (Feb 19, 2026)
- **Unified Sales Page** (`/sales-new`): Combined Quick POS + Sales Order
- **Payment Options**: Cash (immediate), Partial (balance to AR), Credit (full to AR)
- **Manager Approval**: PIN verification for credit sales (1234 default)
- **Credit Limit Check**: Validates customer credit limit before sale
- **Customer Transactions**: Full history view with summary cards
- **Dashboard Receivables**: Combined total from invoices + legacy receivables

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
│   ├── server.py        # Main API server (~2900 lines)
│   ├── ARCHITECTURE.md  # API documentation
│   ├── tests/
│   │   └── test_interest_penalty.py
│   └── .env
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── UnifiedSalesPage.js   # Combined Quick/Order sales
    │   │   ├── PaymentsPage.js       # Enhanced with charges preview
    │   │   ├── CustomersPage.js      # With grace_period field
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
- [x] **Unified Sales Interface** - Combined Quick/Order modes
- [x] **Customer Transaction Tracking** - All sales reflect on account
- [x] **Dashboard Receivables** - Combined total
- [x] **Interest & Penalty with Grace Period** - Auto-preview, manual generation

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
- `GET /api/customers/{id}/charges-preview` - Preview interest/penalty without creating invoices
- `POST /api/customers/{id}/generate-interest` - Create interest invoice with grace period
- `POST /api/customers/{id}/generate-penalty` - Create one-time penalty invoice
- `POST /api/unified-sale` - Create sale (cash/partial/credit)
- `POST /api/auth/verify-manager-pin` - Verify manager PIN
- `GET /api/customers/{id}/transactions` - Customer transaction history
- `GET /api/dashboard/stats` - Dashboard stats with combined receivables
