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

__all__ = [
    'auth_router',
    'branches_router',
    'users_router',
    'products_router',
    'customers_router',
    'inventory_router',
    'price_schemes_router',
]
