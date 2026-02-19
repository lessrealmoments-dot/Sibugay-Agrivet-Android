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

### config.py
- MongoDB connection (MONGO_URL, DB_NAME)
- JWT secret configuration
- Logging setup

### utils/auth.py
- `hash_password()` - bcrypt hashing
- `verify_password()` - bcrypt verification
- `create_token()` - JWT generation
- `get_current_user()` - FastAPI dependency
- `check_perm()` - Permission enforcement (raises exception)
- `has_perm()` - Permission check (returns boolean)

### utils/helpers.py
- `now_iso()` - Current UTC timestamp
- `new_id()` - UUID generation
- `log_movement()` - Product movement logging
- `log_sale_items()` - Sales log entries
- `get_active_date()` - Active business date
- `update_cashier_wallet()` - Wallet balance updates

### models/permissions.py
- `PERMISSION_MODULES` - 12 modules with actions
- `ROLE_PRESETS` - Admin, Manager, Cashier, Inventory Clerk
- `DEFAULT_PERMISSIONS` - Legacy mapping

### routes/ (7 modules extracted)
1. **auth.py** - Authentication endpoints
2. **branches.py** - Branch management
3. **users.py** - User CRUD + permission management
4. **products.py** - Product CRUD, repacks, search
5. **customers.py** - Customer CRUD, transactions
6. **inventory.py** - Stock management
7. **price_schemes.py** - Price tier management

## Remaining in server.py (To Extract)

These routes are more complex with interdependencies:

| Route Section | Lines | Priority | Complexity |
|--------------|-------|----------|------------|
| Unified Sales | ~230 | P1 | High - complex workflows |
| Invoices | ~600 | P1 | High - edit history, interest |
| Purchase Orders | ~150 | P2 | Medium |
| Fund Management | ~100 | P2 | Medium |
| Accounting | ~400 | P2 | High - multiple flows |
| Dashboard | ~100 | P3 | Low |
| Daily Operations | ~180 | P3 | Medium |
| Employees | ~110 | P3 | Low |
| Sync Endpoints | ~90 | P3 | Low |

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
