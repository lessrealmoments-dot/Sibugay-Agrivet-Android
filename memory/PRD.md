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

## What's Been Implemented

### Phase 9: Invoice Editor Feature (Feb 19, 2026)
**QuickBooks-style invoice viewer/editor - double-click any invoice to view/edit**

Features:
- **Universal Invoice Detail Modal** (`InvoiceDetailModal.js`)
  - Opens on double-click/click of any invoice number
  - Shows full invoice details: items, customer, dates, totals
  - Works across all pages: Payments, Sales History, Customer Transactions
  - Supports all types: Sales Invoice, PO, Interest Charge, Penalty Charge

- **Edit with Audit Trail**
  - Requires edit reason (mandatory text field)
  - Optional proof/attachment upload
  - Creates edit history record with: who, when, why, what changed
  - "Edited" badge on invoices with edit count
  - Click badge to view full edit history

- **Inventory Auto-Adjustment on Edit**
  - Increase qty → Deduct more from inventory
  - Decrease qty → Return stock to inventory
  - Remove item → Full return
  - Add item → New deduction

- **PO Price Updates**
  - Editing PO item price updates product cost_price

New Endpoints:
- `GET /api/invoices/{id}` - Get invoice with edit_history and edit_count
- `GET /api/invoices/by-number/{number}` - Find invoice by number across collections
- `PUT /api/invoices/{id}/edit` - Edit invoice (requires reason)
- `GET /api/invoices/{id}/edit-history` - Get edit history

### Phase 8: Interest & Penalty Enhancement (Feb 19, 2026)
- **Grace Period Support**: 7-day default, configurable per customer
- **Auto-Preview Charges**: See computed interest before generating
- **Interest Formula**: Simple daily `Balance × (Rate%/30) × Days`
- **One-Time Penalty**: Flat rate, tracks `penalty_applied` per invoice

### Phase 7: Unified Sales System (Feb 19, 2026)
- **Unified Sales Page** (`/sales-new`): Combined Quick POS + Sales Order
- **Payment Options**: Cash (immediate), Partial (balance to AR), Credit (full to AR)
- **Manager Approval**: PIN verification for credit sales (1234 default)
- **Credit Limit Check**: Validates customer credit limit before sale

### Previous Phases
- Customer Transaction History
- Dashboard with Combined Receivables
- Offline POS with IndexedDB + auto-sync
- Purchase Orders with receiving + cost updates
- Fund Management (Cashier, Safe, Bank wallets)
- Daily Operations (Sales log, profit report, day close)
- Supplier Management with transaction history
- Parent/Repack inventory system (derived quantities)
- Enhanced expense management (Farm, Cash Out workflows)

## Current File Structure
```
/app
├── backend/
│   ├── server.py        # Main API server (~3100 lines)
│   ├── ARCHITECTURE.md  
│   ├── tests/
│   │   └── test_invoice_edit.py  # Invoice edit tests
│   └── .env
└── frontend/
    ├── src/
    │   ├── components/
    │   │   └── InvoiceDetailModal.js  # NEW: Universal invoice viewer/editor
    │   ├── pages/
    │   │   ├── UnifiedSalesPage.js
    │   │   ├── PaymentsPage.js       # Updated: clickable invoice numbers
    │   │   ├── SalesPage.js          # Updated: clickable invoice numbers
    │   │   └── CustomersPage.js
    │   └── App.js
```

## Default Credentials
- Username: admin
- Password: admin123
- Manager PIN: 1234

## Prioritized Backlog (Updated Feb 19, 2026)

### P0 (Critical - Completed)
- [x] **Invoice Editor** - QuickBooks-style view/edit with audit trail
- [x] **Interest & Penalty with Grace Period**
- [x] **Unified Sales Interface**
- [x] **Customer Transaction Tracking**

### P1 (High Priority - User Requested)
- [ ] **Granular Permission System** (like Inflow Cloud)
  - User Permissions page with checkboxes per module
  - Preset roles (Admin, Manager, Cashier) + custom
  - Per-feature access: No Access / View Only / Full Access
- [ ] **Multi-Branch Data Isolation**
  - Branch-specific: prices, customers, suppliers, capital
  - Global: product names/SKUs
  - Owner view: all branches; User view: assigned branch only
- [ ] Backend Modular Refactoring

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
- `GET /api/invoices/{id}` - Get invoice with edit history
- `GET /api/invoices/by-number/{number}` - Find invoice by number
- `PUT /api/invoices/{id}/edit` - Edit invoice with reason
- `GET /api/invoices/{id}/edit-history` - Get edit history
- `GET /api/customers/{id}/charges-preview` - Preview interest/penalty
- `POST /api/customers/{id}/generate-interest` - Create interest invoice
- `POST /api/unified-sale` - Create sale (cash/partial/credit)
- `POST /api/auth/verify-manager-pin` - Verify manager PIN
