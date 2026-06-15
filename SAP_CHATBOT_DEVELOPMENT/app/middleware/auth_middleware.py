"""
Auth Middleware - Authentication and authorization
Handles API key validation, JWT tokens, and multi-tenant credentials
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger
from typing import Optional, List


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware
    Validates API keys and JWT tokens
    """
    
    def __init__(
        self,
        app,
        enabled: bool = False,
        api_keys: Optional[List[str]] = None,
        excluded_paths: Optional[List[str]] = None
    ):
        """
        Initialize auth middleware
        
        Args:
            app: FastAPI application
            enabled: Whether to enforce authentication
            api_keys: List of valid API keys
            excluded_paths: Paths that don't require auth (e.g., /health)
        """
        super().__init__(app)
        self.enabled = enabled
        self.api_keys = api_keys or []
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/api/v1/health",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
        
        if self.enabled:
            logger.info("✓ Auth middleware enabled")
        else:
            logger.info("⚠️ Auth middleware disabled (development mode)")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with authentication"""
        
        # Skip auth for excluded paths
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Skip auth if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Extract credentials
        api_key = self._extract_api_key(request)
        
        # Validate API key
        if not api_key:
            return self._unauthorized_response("Missing API key")
        
        if not self._is_valid_api_key(api_key):
            return self._unauthorized_response("Invalid API key")
        
        # Log successful auth
        logger.debug(f"✓ Auth successful for {request.url.path}")
        
        # Process request
        return await call_next(request)
    
    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from auth"""
        return any(path.startswith(excluded) for excluded in self.excluded_paths)
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from request
        Checks: Authorization header, X-API-Key header, query param
        """
        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "")
        
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key
        
        return None
    
    def _is_valid_api_key(self, api_key: str) -> bool:
        """Validate API key"""
        return api_key in self.api_keys
    
    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Return 401 unauthorized response"""
        logger.warning(f"🔒 Unauthorized access attempt: {message}")
        
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Unauthorized",
                "message": message
            }
        )


class MultiTenantMiddleware(BaseHTTPMiddleware):
    """
    Multi-tenant middleware
    Allows credential override per request for multi-tenant deployments
    """
    
    def __init__(self, app, allow_override: bool = False):
        """
        Initialize multi-tenant middleware
        
        Args:
            app: FastAPI application
            allow_override: Whether to allow credential override
        """
        super().__init__(app)
        self.allow_override = allow_override
        
        if self.allow_override:
            logger.info("✓ Multi-tenant credential override enabled")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with tenant context"""
        
        if not self.allow_override:
            return await call_next(request)
        
        # Extract tenant credentials from headers
        tenant_id = request.headers.get("X-Tenant-ID")
        sap_user = request.headers.get("X-SAP-User")
        sap_password = request.headers.get("X-SAP-Password")
        
        if tenant_id:
            logger.info(f"🏢 Request for tenant: {tenant_id}")
            
            # Store tenant context in request state
            request.state.tenant_id = tenant_id
            request.state.sap_user = sap_user
            request.state.sap_password = sap_password
        
        # Process request
        return await call_next(request)
