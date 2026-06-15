"""
CORS Middleware - Cross-Origin Resource Sharing
Custom CORS handler with advanced options
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger
from typing import List


class CORSMiddleware(BaseHTTPMiddleware):
    """
    Custom CORS middleware with detailed logging
    """
    
    def __init__(
        self,
        app,
        allow_origins: List[str] = ["*"],
        allow_methods: List[str] = ["*"],
        allow_headers: List[str] = ["*"],
        allow_credentials: bool = True,
        max_age: int = 3600
    ):
        """
        Initialize CORS middleware
        
        Args:
            app: FastAPI application
            allow_origins: Allowed origins (["*"] for all)
            allow_methods: Allowed HTTP methods
            allow_headers: Allowed headers
            allow_credentials: Whether to allow credentials
            max_age: Preflight cache duration
        """
        super().__init__(app)
        self.allow_origins = allow_origins
        self.allow_methods = allow_methods
        self.allow_headers = allow_headers
        self.allow_credentials = allow_credentials
        self.max_age = max_age
        
        logger.info(f"✓ CORS configured: Origins={allow_origins}")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with CORS headers"""
        
        # Get origin
        origin = request.headers.get("Origin")
        
        # Handle preflight request (OPTIONS)
        if request.method == "OPTIONS":
            logger.debug(f"🔀 CORS preflight: {origin} → {request.url.path}")
            
            response = Response()
            self._add_cors_headers(response, origin)
            return response
        
        # Process normal request
        response = await call_next(request)
        
        # Add CORS headers
        self._add_cors_headers(response, origin)
        
        return response
    
    def _add_cors_headers(self, response: Response, origin: str = None):
        """Add CORS headers to response"""
        
        # Allow-Origin
        if "*" in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        
        # Allow-Methods
        if "*" in self.allow_methods:
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        else:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        
        # Allow-Headers
        if "*" in self.allow_headers:
            response.headers["Access-Control-Allow-Headers"] = "*"
        else:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        
        # Allow-Credentials
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # Max-Age (preflight cache)
        response.headers["Access-Control-Max-Age"] = str(self.max_age)
