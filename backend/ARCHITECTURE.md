# AgriPOS Backend Architecture

## Overview
The AgriPOS backend is a FastAPI application that provides REST APIs for a multi-branch inventory, POS, and accounting system designed for agricultural retail businesses.

## Technology Stack
- **Framework**: FastAPI (Python 3.10+)
- **Database**: MongoDB with Motor async driver
- **Authentication**: JWT tokens with bcrypt password hashing
- **CORS**: Enabled for frontend access

## File Structure
```
/app/backend/
├── server.py           # Main API server (monolithic, ~2200 lines)
├── server_backup.py    # Backup copy
├── .env                # Environment variables (MONGO_URL, DB_NAME, JWT_SECRET)
└── requirements.txt    # Python dependencies
```

## API Route Sections

### Authentication (`/api/auth/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | User login, returns JWT token |
| `/auth/register` | POST | Create new user (admin only) |
| `/auth/me` | GET | Get current user info |
| `/auth/change-password` | PUT | Change password |

### Branches (`/api/branches/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/branches` | GET | List all active branches |
| `/branches` | POST | Create new branch |
| `/branches/{id}` | PUT | Update branch |
| `/branches/{id}` | DELETE | Soft delete branch |

### Products (`/api/products/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/products` | GET | List products (paginated, filterable) |
| `/products` | POST | Create product |
| `/products/{id}` | PUT | Update product |
| `/products/{id}` | DELETE | Soft delete product + repacks |
| `/products/{id}/generate-repack` | POST | Create repack from parent |
| `/products/{id}/repacks` | GET | Get product repacks |
| `/products/{id}/update-price` | PUT | Update price scheme |
| `/products/categories/list` | GET | List unique categories |
| `/products/search-detail` | GET | Enhanced search with stock info |
| `/products/{id}` | GET | Full product detail with inventory |
| `/products/{id}/vendors` | GET/POST/DELETE | Product vendor management |
| `/products/{id}/order-history` | GET | Sales & purchase history |

### Invoices / Sales Orders (`/api/invoices/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/invoices` | GET | List invoices (filterable) |
| `/invoices` | POST | Create sales order/invoice |
| `/invoices/{id}` | GET | Get invoice detail |
| `/invoices/{id}/compute-interest` | POST | Compute overdue interest |
| `/invoices/{id}/payment` | POST | Record payment |

### Customer Payments (`/api/customers/{id}/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/{id}/invoices` | GET | Customer's open invoices |
| `/customers/{id}/payment-history` | GET | Payment history |
| `/customers/{id}/generate-interest` | POST | Generate interest invoice |
| `/customers/{id}/generate-penalty` | POST | Generate penalty invoice |
| `/customers/{id}/receive-payment` | POST | Smart payment allocation |

### Fund Wallets (`/api/fund-wallets/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/fund-wallets` | GET | List wallets (Cashier, Safe, Bank) |
| `/fund-wallets` | POST | Create wallet |
| `/fund-wallets/{id}/deposit` | POST | Deposit to wallet |
| `/fund-wallets/pay` | POST | Pay from wallet |
| `/safe-lots` | GET | List safe cash lots |
| `/fund-wallets/{id}/movements` | GET | Wallet transaction history |

### Purchase Orders (`/api/purchase-orders/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/purchase-orders` | GET | List POs |
| `/purchase-orders` | POST | Create PO (cash/credit) |
| `/purchase-orders/{id}` | PUT | Update PO |
| `/purchase-orders/{id}/receive` | POST | Receive PO (updates inventory) |
| `/purchase-orders/{id}` | DELETE | Cancel PO |
| `/purchase-orders/{id}/pay` | POST | Pay credit PO |
| `/purchase-orders/vendors` | GET | List unique vendors |
| `/purchase-orders/by-vendor` | GET | Get vendor's POs |

### Inventory (`/api/inventory/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/inventory` | GET | List inventory with stock levels |
| `/inventory/adjust` | POST | Adjust stock quantity |
| `/inventory/transfer` | POST | Transfer between branches |

### Customers (`/api/customers/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers` | GET | List customers |
| `/customers` | POST | Create customer |
| `/customers/{id}` | PUT | Update customer |
| `/customers/{id}` | DELETE | Soft delete customer |

### Price Schemes (`/api/price-schemes/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/price-schemes` | GET | List price schemes |
| `/price-schemes` | POST | Create scheme |
| `/price-schemes/{id}` | PUT | Update scheme |
| `/price-schemes/{id}` | DELETE | Soft delete scheme |

### Sales / POS (`/api/sales/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sales` | POST | Create POS sale |
| `/sales` | GET | List sales history |
| `/sales/{id}` | GET | Get sale detail |
| `/sales/{id}/void` | POST | Void sale (restores inventory) |
| `/sales/{id}/release` | POST | Release reserved sale |
| `/sales/sync` | POST | Sync offline sales |

### Accounting (`/api/expenses/*`, `/api/receivables/*`, `/api/payables/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/expenses` | GET/POST | Expense management |
| `/expenses/{id}` | DELETE | Delete expense |
| `/expenses/farm` | POST | Farm expense (creates receivable) |
| `/expenses/employee-advance` | POST | Employee advance |
| `/receivables` | GET | List receivables |
| `/receivables/{id}/payment` | POST | Record receivable payment |
| `/payables` | GET/POST | Payable management |
| `/payables/{id}/payment` | POST | Record payable payment |

### Dashboard (`/api/dashboard/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard/stats` | GET | KPIs, sales, top products |

### Daily Operations (`/api/daily-*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/daily-log` | GET | Daily sales log |
| `/daily-report` | GET | Daily profit report |
| `/daily-close/{date}` | GET | Get close record |
| `/daily-close` | POST | Close day (cash counting) |

### User Management (`/api/users/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | GET | List users |
| `/users/{id}` | PUT | Update user |
| `/users/{id}/permissions` | PUT | Update permissions |
| `/users/{id}/reset-password` | PUT | Reset user password |

### Employees (`/api/employees/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/employees` | GET | List employees |
| `/employees` | POST | Create employee |
| `/employees/{id}` | PUT | Update employee |

### Sync / Offline (`/api/sync/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sync/pos-data` | GET | Bulk data for offline POS |

## Database Collections

| Collection | Purpose |
|------------|---------|
| `users` | User accounts and permissions |
| `branches` | Business locations |
| `products` | Product catalog (parent + repacks) |
| `inventory` | Stock levels per branch |
| `inventory_movements` | Stock change audit log |
| `customers` | Customer records |
| `price_schemes` | Pricing tiers |
| `sales` | POS sales transactions |
| `sales_log` | Daily sales log entries |
| `invoices` | Sales orders / invoices |
| `purchase_orders` | Purchase orders from suppliers |
| `expenses` | Expense records |
| `receivables` | Money owed to business |
| `payables` | Money owed by business |
| `fund_wallets` | Cash wallets (Cashier, Safe, Bank) |
| `wallet_movements` | Wallet transaction log |
| `safe_lots` | Safe cash lots by date |
| `daily_closes` | Daily close records |
| `employees` | Employee records |
| `product_vendors` | Product-vendor relationships |

## Key Business Logic

### Cash Flow System
All cash transactions update the `cashier_wallet` in real-time:
- POS cash sales → Cashier +
- Invoice payments → Cashier +
- Cash PO payments → Cashier -
- Expenses → Cashier -

### Interest Calculation
- Pro-rated monthly interest based on days overdue
- Applied to oldest invoices first
- Interest invoices created separately

### Inventory Management
- Parent/Repack system with auto stock deduction
- Stock movements logged for audit trail
- Reserved stock for delivery sales

## Future Refactoring Notes

For full modular refactoring, the recommended structure would be:
```
/app/backend/
├── main.py              # FastAPI app entry point
├── config.py            # Configuration & settings
├── database.py          # Database connection
├── auth.py              # Auth helpers & middleware
├── routes/
│   ├── __init__.py
│   ├── auth.py          # Auth routes
│   ├── branches.py      # Branch routes
│   ├── products.py      # Product routes
│   ├── inventory.py     # Inventory routes
│   ├── customers.py     # Customer routes
│   ├── sales.py         # Sales/POS routes
│   ├── invoices.py      # Invoice routes
│   ├── purchase_orders.py
│   ├── accounting.py    # Expenses, receivables, payables
│   ├── fund_wallets.py  # Fund management
│   ├── daily_ops.py     # Daily operations
│   └── users.py         # User management
├── services/
│   ├── __init__.py
│   ├── inventory_service.py
│   ├── payment_service.py
│   └── wallet_service.py
└── models/
    ├── __init__.py
    └── schemas.py       # Pydantic models
```

## Environment Variables
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=agripos
JWT_SECRET=your_secret_key
CORS_ORIGINS=*
```

## Default Credentials
- Username: `admin`
- Password: `admin123`
