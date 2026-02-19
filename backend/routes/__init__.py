"""
Routes package init - export all routers.
"""
from .auth import router as auth_router
from .branches import router as branches_router
from .users import router as users_router
from .products import router as products_router
from .customers import router as customers_router
from .inventory import router as inventory_router
from .price_schemes import router as price_schemes_router
from .invoices import router as invoices_router
from .sales import router as sales_router
from .purchase_orders import router as purchase_orders_router
from .dashboard import router as dashboard_router
from .accounting import router as accounting_router
from .daily_operations import router as daily_ops_router
from .suppliers import router as suppliers_router
from .sync import router as sync_router
from .employees import router as employees_router
from .settings import router as settings_router

__all__ = [
    'auth_router',
    'branches_router',
    'users_router',
    'products_router',
    'customers_router',
    'inventory_router',
    'price_schemes_router',
    'invoices_router',
    'sales_router',
    'purchase_orders_router',
    'dashboard_router',
    'accounting_router',
    'daily_ops_router',
    'suppliers_router',
    'sync_router',
    'employees_router',
    'settings_router',
]
