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
