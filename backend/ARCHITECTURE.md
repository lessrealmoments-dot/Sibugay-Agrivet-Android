# AgriPOS Backend Architecture

## Overview
AgriPOS uses a fully modular FastAPI architecture with MongoDB. The refactoring is **COMPLETE** - all routes have been extracted from the monolith into separate, maintainable modules.

## Directory Structure

```
/app/backend/
├── server.py              # Entry point (imports from main.py)
├── main.py                # FastAPI app with all routers
├── config.py              # Database and environment configuration
├── server_legacy.py       # Original monolith (backup)
├── requirements.txt       # Python dependencies
│
├── utils/
│   ├── __init__.py        # Exports all utilities
│   ├── auth.py            # Authentication: JWT, password hashing, permissions
│   ├── helpers.py         # Common helpers: IDs, timestamps, logging
│   └── branch.py          # Multi-branch: access control, data isolation
│
├── models/
│   ├── __init__.py        # Exports all models
│   └── permissions.py     # Permission modules and role presets
│
├── routes/                # ALL route modules (17 total)
│   ├── __init__.py        # Exports all routers
│   ├── auth.py            # Login, register, password, PIN verification
│   ├── branches.py        # Branch CRUD
│   ├── users.py           # User management and permissions
│   ├── products.py        # Products, repacks, pricing, search
│   ├── customers.py       # Customer CRUD, transactions (branch-filtered)
│   ├── inventory.py       # Stock levels, adjustments, transfers
│   ├── price_schemes.py   # Price scheme management
│   ├── invoices.py        # Invoice CRUD, payments, interest, editing (branch-filtered)
│   ├── sales.py           # Unified sales endpoint
│   ├── purchase_orders.py # PO CRUD, receiving, payments (branch-filtered)
│   ├── dashboard.py       # Stats, branch summary (branch-filtered)
│   ├── accounting.py      # Fund wallets, expenses, receivables, payables
│   ├── daily_operations.py # Daily log, report, close day
│   ├── suppliers.py       # Supplier CRUD
│   ├── employees.py       # Employee management, advances
│   ├── sync.py            # Offline POS data sync
│   └── settings.py        # Invoice prefixes, terms options
│
└── tests/
    └── test_*.py
```

## Module Summary

| Module | Endpoints | Description |
|--------|-----------|-------------|
| auth.py | 6 | Login, register, PIN verification |
| branches.py | 4 | Branch CRUD |
| users.py | 12 | User management, permissions |
| products.py | 11 | Products, repacks, search |
| customers.py | 6 | Customer CRUD, transactions |
| inventory.py | 4 | Stock levels, adjustments |
| price_schemes.py | 4 | Price tier management |
| invoices.py | 9 | Invoice CRUD, payments, editing |
| sales.py | 1 | Unified sales endpoint |
| purchase_orders.py | 9 | PO CRUD, receiving, payments |
| dashboard.py | 2 | Stats, branch summary |
| accounting.py | 18 | Fund wallets, expenses, AR/AP |
| daily_operations.py | 4 | Daily log, report, close day |
| suppliers.py | 5 | Supplier CRUD |
| employees.py | 5 | Employee management |
| sync.py | 2 | Offline POS sync |
| settings.py | 3 | Invoice prefixes, terms |
| **TOTAL** | **~95** | |

## Multi-Branch Data Isolation

### Branch Access Control
- **Admin/Owner**: Can view all branches or filter by specific branch
- **Regular Users**: Only see data from their assigned `branch_id`

### Data Scope
| Scope | Collections |
|-------|-------------|
| Branch-Specific | invoices, sales, inventory, purchase_orders, expenses, receivables, fund_wallets, movements, sales_log, customers |
| Global | products, price_schemes, settings |

### Key Utilities (`utils/branch.py`)
- `get_user_branches(user)` - Get list of accessible branch IDs
- `get_branch_filter(user, branch_id)` - Build MongoDB query filter
- `apply_branch_filter(query, filter)` - Merge branch filter into query
- `ensure_branch_access(user, branch_id)` - Verify access, raises 403

### Dashboard Endpoints
- `GET /dashboard/stats?branch_id=` - Stats with optional branch filter
- `GET /dashboard/branch-summary` - Summary for all accessible branches

## API Prefix Convention
All routes use the `/api` prefix:
- Auth: `/api/auth/*`
- Branches: `/api/branches/*`
- Products: `/api/products/*`
- Customers: `/api/customers/*`
- Inventory: `/api/inventory/*`
- Price Schemes: `/api/price-schemes/*`
- Users: `/api/users/*`
- Permissions: `/api/permissions/*`
- Invoices: `/api/invoices/*`
- Purchase Orders: `/api/purchase-orders/*`
- Dashboard: `/api/dashboard/*`
- Fund Wallets: `/api/fund-wallets/*`
- Expenses: `/api/expenses/*`
- Receivables/Payables: `/api/receivables/*`, `/api/payables/*`
- Daily Ops: `/api/daily-log`, `/api/daily-report`, `/api/daily-close`
- Suppliers: `/api/suppliers/*`
- Employees: `/api/employees/*`
- Sync: `/api/sync/*`
- Settings: `/api/settings/*`

## Migration Status (COMPLETE)

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Foundation (config, utils, models) |
| Phase 2 | ✅ Complete | Core routes (auth, users, products, invoices, sales) |
| Phase 3 | ✅ Complete | Remaining routes (accounting, daily ops, employees, sync) |

## Testing
- Unit tests in `/app/backend/tests/`
- Integration tests via testing agent
- API testing with curl commands

## Environment Variables
```
MONGO_URL=mongodb://...
DB_NAME=agripos
JWT_SECRET=your_secret
CORS_ORIGINS=*
```
