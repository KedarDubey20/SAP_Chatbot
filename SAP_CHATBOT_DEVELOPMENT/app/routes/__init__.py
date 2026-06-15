"""
Routes Package
"""
from .ai_routes import router as ai_router
from .sap_routes import router as sap_router
from .cache_routes import router as cache_router
from .health_routes import router as health_router
from .schema_routes import router as schema_router
from .loader_routes import router as loader_router
from .session_routes import router as session_router
__all__ = [
    'ai_router',
    'sap_router',
    'cache_router',
    'health_router',
    'schema_router',
    'loader_router',
    'session_router'
]