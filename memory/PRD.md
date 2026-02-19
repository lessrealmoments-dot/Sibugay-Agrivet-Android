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
- [x] POS interface with product search, cart, multiple payment methods
- [x] Auto stock deduction from parent when repack is sold
- [x] Multiple price schemes (Retail, Wholesale, Special, Government)
- [x] Customer management with price scheme assignment
- [x] Accounting: Expenses tracking, Receivables, Payables with payment recording
- [x] Sales history with void capability (restores inventory)
- [x] Dashboard with KPIs, recent sales, top products, low stock alerts
- [x] User management with role assignment and password reset

## What's Been Implemented (Feb 19, 2026)

### Phase 1: MVP Core
### Backend (server.py)
- Full REST API with 30+ endpoints under /api prefix
- JWT auth with bcrypt password hashing
- MongoDB collections: users, branches, products, inventory, customers, price_schemes, sales, expenses, receivables, payables, inventory_logs
- Parent/Repack system with auto stock deduction logic
- Database seeding: default admin, main branch, 4 price schemes
- Database indexing for performance

### Phase 2: PWA + Offline POS (Feb 19, 2026)
- **Simplified Inventory Page**: Shows product name, SKU, category, type (Stockable/Service/Repack), on-hand stock, status badges. Clicking any row navigates to Product Detail.
- **Comprehensive Product Detail Page** with accordion sections:
  - Sales Information (pricing tiers in ₱ PHP)
  - Create Repack (generate repack SKUs)
  - Capital/Cost (Moving Average, Last Purchase with warning, Manual)
  - Inventory (On Hand per branch, Coming from POs, Reserved from delivery sales, Available)
  - Extra Info (Barcode, Reorder Point/Qty, Last Vendor, Unit of Measurement)
  - Product Vendors (add/remove vendors per product)
  - Movement History (sales, purchases, returns, adjustments with user tracking)
  - Order History (combined sales + purchase history with prices)
- **Purchase Orders**: CRUD + receive flow (receiving adds to inventory + logs movements + updates cost)
- **Sale Reserve/Release**: Delivery sales create "reserved" status, release deducts inventory
- **Movement Logging**: All inventory changes (sales, purchases, adjustments) are automatically tracked
- **Philippine Peso (₱)**: All currency displays across Dashboard, POS, Products, Accounting
- **Service Worker** (`public/sw.js`): Caches app shell, static assets, API responses, Google Fonts
- **PWA Manifest** (`public/manifest.json`): standalone display, installable on desktop/tablet
- **IndexedDB** (`lib/offlineDB.js`): Stores products, customers, price schemes, pending offline sales
- **Sync Manager** (`lib/syncManager.js`): Auto-syncs pending sales every 30s, full data refresh on reconnect
- **Offline POS Flow**: Pre-loads all product data via /sync/pos-data, client-side search, saves sales to IndexedDB when offline
- **Conflict Prevention**: UUID-based sale IDs generated on client, server-side duplicate detection in /sales/sync
- **Backend Sync Endpoints**: GET /api/sync/pos-data (bulk data), POST /api/sales/sync (batch sync with dedup)
- **Offline Indicator**: Shows online/offline status in sidebar + POS header, pending sale count, manual sync button
- **PWA Install**: Browser prompts "Install App" button in sidebar

### Frontend (11 pages)
- LoginPage: Split layout with warehouse image
- DashboardPage: 6 KPI cards, receivables widget, top products, recent sales
- BranchesPage: CRUD table with dialog forms
- ProductsPage: Product list with search/filter, parent/repack generation dialog
- InventoryPage: Stock levels per branch, adjust/transfer dialogs, low stock filter
- POSPage: Full POS interface with product grid, cart, checkout, customer selection
- CustomersPage: CRUD with price scheme assignment
- PriceSchemesPage: Price tier management with calculation methods
- SalesPage: Sales history with detail view and void capability
- AccountingPage: Tabbed interface for expenses, receivables, payables
- SettingsPage: User management with granular permission toggles

## Prioritized Backlog
### P0 (Critical)
- [x] Offline POS with IndexedDB + auto-sync when online (DONE)
- [x] Conflict prevention via UUID sale IDs + server duplicate detection (DONE)
- [x] PWA installable app (DONE)

### P1 (High)
- [ ] Barcode scanning support in POS
- [ ] Batch product import (CSV for 3000+ SKUs)
- [ ] Receipt printing (thermal printer support)
- [ ] Inventory reports and analytics
- [ ] Sales reports by date range, branch, product

### P2 (Medium)
- [ ] Auto price calculation from schemes (apply formula to all products)
- [ ] Purchase orders and supplier management
- [ ] Stock alerts and notifications
- [ ] Daily cash register open/close with reconciliation
- [ ] Product images and categories management

### P3 (Low/Future)
- [ ] Multi-currency support
- [ ] API for mobile app
- [ ] Audit trail / activity logs
- [ ] Data backup and export
- [ ] Dashboard charts with Recharts

## Default Credentials
- Username: admin
- Password: admin123

### Phase 4: Sales Order System + Fund Management + Payments (Feb 19, 2026)
- **Sales Order Page**: Excel-style line items with full invoice header (Customer, Contact, Phone, Address, Terms, PO#, Sales Rep, Prefix, Order/Invoice/Due dates)
- **Smart Product Search**: Type-ahead search with detail bubbles showing retail price (₱), capital, available stock, reserved, coming inventory, parent stock for repacks. Arrow key navigation + Enter to select.
- **Invoice System**: Auto-generated invoice numbers with configurable prefixes (SI, DR, TR, PO). Auto-computed due dates from terms. Per-line discounts (₱ or %) + overall discount + freight.
- **Repack Capital Auto-Compute**: Parent cost / units per parent + add-on cost = repack capital
- **Fund Management**: Three wallet types (Cashier Drawer, Safe with dated cash lots, Bank). Safe uses intelligent lot allocation (largest-first, fewest lots). Full lot usage audit trail.
- **Payments Page**: Customer invoice lookup, record payments with fund source selection (Cashier/Safe/Bank). Interest & penalties deducted first, then principal.
- **Interest Computation**: Prorated monthly from last computation date. Auto-detects overdue invoices. Per-customer interest rates.
- **Payment Terms**: COD, Net 7/15/30/60, Custom days. Due date auto-computed.

### Phase 6: Daily Operations - Sales Log, Profit & Day Close (Feb 19, 2026)
- **Sequential Sales Log**: Auto-records each sold item with sequence #, time, product, customer, invoice, qty, price, discount, line total, running total. Printable for notebook comparison.
- **Daily Profit Report**: Revenue, COGS, Gross Profit, Expenses, Net Profit. Sales by Category breakdown. Expense list with quick-add buttons for Regular/Advance/Farm expenses.
- **Close Accounts**: Locks the day. Cash Counting (Expected vs Actual + Checks + Other). Extra Cash computation (Actual - Expected). End-of-Day Allocation (cash to drawer + cash to safe). Auto-deposits to safe as dated lot.
- **Employee Management**: Add employees with name/position. Track monthly cash advance totals.
- **Farm Expense System**: When recording farm expense, selects customer/farm + purpose tag. Auto-creates receivable invoice ("Farm Cash Out - Tilling") added to customer's balance.
- **Day Lock**: Once closed, new sales auto-go to next day. Prevents edits on closed dates.

### Bug Fix: Badge Overlay (Feb 19, 2026)
- **Issue**: "Made with Emergent" badge at bottom-right (z-index: 9999) was obstructing UI buttons (Checkout, Close Day, etc.)
- **Fix**: Added CSS override in `index.css` to hide `#emergent-badge` with `display: none !important` + multiple fallbacks
- **Status**: VERIFIED - Badge hidden, all UI elements accessible

### Bug Fix: New Product Form [object Object] (Feb 19, 2026)
- **Issue**: Clicking "Add Product" passed click event as `prefillName` arg, rendering `[object Object]` in Product Name field
- **Fix**: Changed `onClick={openCreate}` to `onClick={() => openCreate()}` in ProductsPage.js line 122
- **Status**: VERIFIED - Product Name field now starts empty, product creation works correctly

### Feature: Optional SKU (Feb 19, 2026)
- **Change**: SKU field is now optional when creating products. If left blank, system auto-generates a unique SKU (P-XXXXXXXX format)
- **Backend**: Skip duplicate check for empty SKUs, auto-generate if not provided
- **Frontend**: Updated label to "(optional - auto-generated if blank)" with new placeholder
- **Status**: VERIFIED


### Critical Fix: Daily Closing Double-Counting (Feb 19, 2026)
- **Problem**: Expected Cash doubled actual amount (₱1,100 sales showed ₱2,200) because system added sales_log totals + invoice payments — same-day paid invoices counted twice
- **Fix**: Expected Cash now uses `total_cash_received` (invoice payments + POS cash) instead of `sales + payments`. Credit Collections only counts payments on OLD invoices.
- **Renames**: "Total Sales" → "New Sales Today", "Total Payments Received" → "Credit Collections Today", Dashboard "Today's Revenue" → "New Sales Today"
- **Key rule**: New Sales Today = revenue/profit. Credit Collections = cash recovery only. Never combined as revenue.
- **Status**: VERIFIED


### Major Feature: Unified Cash Flow System (Feb 19, 2026)
- **Problem**: Fund Management was disconnected — POS sales, invoice payments, and expenses didn't update wallet balances. Cashier Drawer was only set at Day Close (stale snapshot).
- **Solution**: Every cash event now updates wallets in real-time:
  - POS cash sale → Cashier Drawer +
  - Invoice with payment → Cashier Drawer +
  - Expense/Farm/Advance → Cashier Drawer -
  - Credit sale → no wallet change (correct)
  - Offline sync → Cashier Drawer + (on sync)
- **Day Close**: Expected Cash = Cashier Drawer wallet balance (real-time). No more computing from sales+payments.
- **POS → sales_log**: POS sales now logged to sales_log for unified daily reporting.
- **Auto-create wallet**: Cashier Drawer wallet auto-created on first transaction if missing.
- **helper**: `update_cashier_wallet(branch_id, amount, reference)` — single function for all cash movements with audit trail via wallet_movements collection.
- **Status**: VERIFIED — 100% test pass rate (9/9 backend, all frontend)


### Feature: Purchase Order Payment Integration (Feb 19, 2026)
- **Renamed**: "Expected Date" → "Purchase Date" (defaults to today)
- **Payment Method**: "Pay in Cash" or "Purchase on Credit" selector on PO form
- **Cash PO**: Deducts total from Cashier Drawer wallet immediately on creation
- **Credit PO**: Creates payable record, no cash movement. "Pay" button appears in PO list to pay later (deducts from cashier)
- **New endpoint**: `POST /api/purchase-orders/{po_id}/pay` — pays credit PO, updates balance, linked payable
- **PO fields added**: `payment_method`, `payment_status` (paid/unpaid/partial), `amount_paid`, `balance`

### Feature: QuickBooks-Style Receive Payments (Feb 19, 2026)
- **Complete rewrite** of Receive Payments page with QuickBooks-inspired workflow
- **Customer lookup**: Select customer → all open invoices displayed with Original, Paid, Open Balance columns + totals row
- **Total Open Balance**: Prominent display of customer's total outstanding amount
- **Generate Interest**: Account-level button computes interest on ALL overdue invoices and creates a single Interest Charge invoice
- **Compute Penalty**: Similar, creates Penalty Charge invoice with configurable % rate
- **Smart Payment Allocation**: Enter amount received → auto-applies in priority order:
  1. Interest Charge invoices first
  2. Penalty Charge invoices second  
  3. Oldest regular invoices last
- **Live Allocation Preview**: Shows exactly how payment will be distributed before confirming
- **Connected to Fund Management**: Payment auto-updates Cashier Drawer wallet
- **New endpoints**: generate-interest, generate-penalty, receive-payment (all per customer)
- **Status**: VERIFIED — 100% test pass (13/13 backend, all frontend)

- **Status**: VERIFIED — Cash/Credit PO creation, wallet updates, payable creation, late payment all working

### Feature: PO Number Field Repositioning (Feb 19, 2026)
- **Change**: Moved PO Number field from first position to near the Notes field
- **Layout**: First row now contains: Vendor Name, Purchase Date, Payment, Status, PO Number (5 columns)
- **Notes**: Has its own dedicated row with placeholder "Optional notes for this purchase order"
- **Status**: VERIFIED

### Feature: Suppliers Management Page (Feb 19, 2026)
- **New Page**: `/suppliers` - dedicated supplier management with full transaction history
- **Supplier List**: Left panel shows all suppliers with search functionality
- **Stats Cards**: When supplier selected, shows Total POs, Total Purchased, Total Paid, Pending Payment
- **PO List Tabs**: Filter by All, Unpaid, Pending Delivery with counts
- **PO Table**: Shows PO#, Date, Items, Total, Paid, Balance, Delivery status, Payment status
- **PO Detail Dialog**: Click any PO number to see full details including items and payment history
- **Payment History**: Bottom section shows all payments made to the supplier
- **Navigation**: Added "Suppliers" link in sidebar
- **Status**: VERIFIED — 100% test pass (all frontend features working)

### Backend Organization (Feb 19, 2026)
- **Approach**: Quick organization of existing `server.py` with clear section headers
- **Documentation**: Created `/app/backend/ARCHITECTURE.md` with complete API reference
- **Structure**: Added table of contents at top of `server.py` with line numbers for each route section
- **Status**: COMPLETE — Backend organized, documentation created, all APIs working

### Supplier Management Enhancement (Feb 19, 2026)
- **New Feature**: Full supplier CRUD with contact details (name, contact person, phone, email, address, notes)
- **Suppliers Page**: Added "New Supplier" button with creation dialog
- **Supplier Details**: When selecting a supplier, shows contact info card with Edit button
- **PO Quick-Create**: Smart vendor search in PO form with dropdown - type a new name to quick-create supplier
- **Backend Endpoints**: Added `/api/suppliers` CRUD endpoints
- **Status**: VERIFIED — 100% test pass (backend 9/9, frontend all features working)

### Enhanced Expense Management (Feb 19, 2026)
- **Preset Categories**: Dropdown with 17 categories (Utilities, Rent, Supplies, Transportation, Fuel/Gas, Employee Advance, Repairs & Maintenance, Marketing, Salaries & Wages, Communication, Insurance, Professional Fees, Taxes & Licenses, Office Supplies, Equipment, Miscellaneous)
- **Payment Methods**: Cash, Check, Bank Transfer, GCash, Maya, Credit Card (with color-coded badges)
- **Reference Number**: Track check numbers, OR numbers, receipt references
- **Notes Field**: Additional details for each expense
- **Edit Capability**: Update existing expenses with pre-filled form
- **Filtering & Search**: Filter by category, payment method, date range; search by description/reference
- **Farm Expense Workflow** (amber theme, tractor icon):
  - Records farm service expense (Tilling, Plowing, Labor, Gas, etc.)
  - Selects customer to bill
  - Auto-creates invoice for the customer
  - Links expense to invoice (shows invoice number in table)
- **Customer Cash Out Workflow** (blue theme, banknote icon):
  - Records cash loan/advance to customer
  - Selects customer who borrowed money
  - Auto-creates invoice for the customer (they owe money)
  - Links expense to invoice (shows invoice number in table)
  - Shows "Loaned to: CustomerName" in expense table
- **Status**: VERIFIED — 100% test pass (all features working)

## Current File Structure
```
/app
├── backend/
│   ├── server.py        # Main API server (~2500 lines)
│   ├── ARCHITECTURE.md  # Complete API documentation
│   ├── tests/           # Backend tests
│   └── .env
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── AccountingPage.js      # Enhanced expense management
    │   │   ├── PurchaseOrderPage.js   # PO with smart supplier search
    │   │   ├── SuppliersPage.js       # Supplier management
    │   │   └── ... other pages
    │   ├── components/
    │   └── App.js
```

## Default Credentials
- Username: admin
- Password: admin123

## Prioritized Backlog (Updated Feb 19, 2026)

### P0 (Critical - Technical Debt)
- [x] **Backend Organization**: Added section headers and created ARCHITECTURE.md documentation

### P1 (High Priority)
- [ ] Advanced Reporting Dashboards (monthly/quarterly summaries, sales incentive tracking)
- [ ] Barcode scanning support in POS
- [ ] Receipt printing (thermal printer support)
- [ ] Full modular refactoring (if needed in future)

### P2 (Medium Priority)
- [ ] User Roles & Permissions UI (dedicated management page)
- [ ] Bulk Data Import/Export (CSV for products)
- [ ] Stock alerts and notifications
- [ ] Product images and categories management
- [ ] Recurring expenses (auto-create monthly rent, utilities)
- [ ] Budget tracking per category

### P3 (Low/Future)
- [ ] Multi-currency support
- [ ] API for mobile app
- [ ] Audit trail / activity logs
- [ ] Data backup and export
- [ ] Dashboard charts with Recharts
- [ ] Receipt image upload
