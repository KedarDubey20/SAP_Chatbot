"""
Error Middleware - Global error handling
Catches all unhandled exceptions and returns structured responses
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger
import traceback
from datetime import datetime


class ErrorMiddleware(BaseHTTPMiddleware):
    """
    Global error handler middleware
    Catches all exceptions and returns JSON error responses
    """
    
    def __init__(self, app, debug: bool = False):
        """
        Initialize error middleware
        
        Args:
            app: FastAPI application
            debug: If True, include full traceback in response
        """
        super().__init__(app)
        self.debug = debug
    
    async def dispatch(self, request: Request, call_next):
        """Process request with error handling"""
        
        try:
            # Process request normally
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Log the error
            logger.error(f"❌ Unhandled exception: {str(e)}")
            logger.error(f"   Path: {request.method} {request.url.path}")
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            
            # Build error response
            error_response = {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
                "method": request.method
            }
            
            # Add traceback in debug mode
            if self.debug:
                error_response["traceback"] = traceback.format_exc()
            
            # Determine status code based on exception type
            status_code = self._get_status_code(e)
            
            # Return JSON error response
            return JSONResponse(
                status_code=status_code,
                content=error_response
            )
    
    def _get_status_code(self, exception: Exception) -> int:
        """
        Determine appropriate HTTP status code for exception
        
        Args:
            exception: The exception that was raised
            
        Returns:
            HTTP status code
        """
        # Map exception types to status codes
        exception_name = type(exception).__name__
        
        status_map = {
            'ValueError': 400,
            'ValidationError': 400,
            'KeyError': 400,
            'FileNotFoundError': 404,
            'PermissionError': 403,
            'NotImplementedError': 501,
            'TimeoutError': 504,
            'ConnectionError': 503,
        }
        
        return status_map.get(exception_name, 500)
