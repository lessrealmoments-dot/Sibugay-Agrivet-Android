# AgriPOS Backend Architecture

## Overview
AgriPOS uses a modular FastAPI architecture with MongoDB for the backend. The refactoring is in progress, with core modules extracted and complex routes remaining in the monolith for safe incremental migration.

## Directory Structure

```
/app/backend/
├── server.py              # Main server (original monolith - still in use)
├── server_modular.py      # Target architecture template
├── server_backup.py       # Backup of original
├── config.py              # Database and environment configuration
├── requirements.txt       # Python dependencies
│
├── utils/
│   ├── __init__.py        # Exports all utilities
│   ├── auth.py            # Authentication: JWT, password hashing, permissions
│   └── helpers.py         # Common helpers: IDs, timestamps, logging
│
├── models/
│   ├── __init__.py        # Exports all models
│   └── permissions.py     # Permission modules and role presets
│
├── routes/                # Extracted route modules
│   ├── __init__.py        # Exports all routers
│   ├── auth.py            # Login, register, password, PIN verification
│   ├── branches.py        # Branch CRUD
│   ├── users.py           # User management and permissions
│   ├── products.py        # Products, repacks, pricing, search
│   ├── customers.py       # Customer CRUD, transactions
│   ├── inventory.py       # Stock levels, adjustments, transfers
│   └── price_schemes.py   # Price scheme management
│
└── tests/
    └── test_user_permissions.py
```

## Extracted Modules (Complete)

### Phase 1 - Foundation (Complete)
- config.py: MongoDB connection, JWT secret, logging
- utils/auth.py: Password hashing, JWT, permissions
- utils/helpers.py: Timestamps, IDs, logging utilities

### Phase 2 - Complex Routes (Complete)
**10 route modules extracted with 62 total endpoints:**

| Module | Endpoints | Description |
|--------|-----------|-------------|
| auth.py | 6 | Login, register, PIN verification |
| branches.py | 4 | Branch CRUD |
| users.py | 12 | User management, permissions |
| products.py | 11 | Products, repacks, search |
| customers.py | 5 | Customer CRUD, transactions |
| inventory.py | 4 | Stock levels, adjustments |
| price_schemes.py | 4 | Price tier management |
| invoices.py | 8 | Invoice CRUD, payments, editing |
| sales.py | 1 | Unified sales endpoint |
| purchase_orders.py | 8 | PO CRUD, receiving, payments |

## Remaining in server.py (Phase 3 - To Extract)

These routes are lower priority and can be extracted later:

| Route Section | Lines | Priority | Complexity |
|--------------|-------|----------|------------|
| Fund Management | ~100 | P2 | Medium |
| Accounting | ~200 | P2 | Medium |
| Dashboard | ~100 | P3 | Low |
| Daily Operations | ~180 | P3 | Medium |
| Suppliers | ~100 | P3 | Low |
| Employees | ~110 | P3 | Low |
| Sync Endpoints | ~90 | P3 | Low |
| Interest/Penalty | ~250 | P3 | Medium |

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

## Migration Strategy

1. **Phase 1 (Complete)**: Extract foundational modules
   - config, utils, models
   - Simple CRUD routes (branches, products, customers, inventory, price_schemes)
   - User management and permissions

2. **Phase 2 (Next)**: Extract complex routes
   - Invoices with edit history
   - Unified sales flow
   - Purchase orders

3. **Phase 3 (Future)**: Extract remaining
   - Accounting and fund management
   - Dashboard and reporting
   - Daily operations and employees
   - Sync endpoints

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
