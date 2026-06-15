"""
Logging Middleware - Log all requests and responses
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from loguru import logger
import time
import json


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all incoming requests and outgoing responses
    Tracks response time and status codes
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log details"""
        
        # Start timer
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"→ {request.method} {request.url.path} "
            f"| Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Log query params if present
        if request.url.query:
            logger.debug(f"  Query: {request.url.query}")
        
        # Log request body for POST/PUT (careful with sensitive data)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Only log first 200 chars to avoid huge logs
                body = await request.body()
                if body:
                    body_preview = body.decode()[:200]
                    logger.debug(f"  Body: {body_preview}...")
            except:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        status_emoji = "✓" if response.status_code < 400 else "✗"
        logger.info(
            f"← {status_emoji} {response.status_code} "
            f"| {request.method} {request.url.path} "
            f"| {duration:.3f}s"
        )
        
        # Log slow requests (>2s)
        if duration > 2.0:
            logger.warning(f"⚠️ Slow request: {request.url.path} took {duration:.3f}s")
        
        # Log errors
        if response.status_code >= 500:
            logger.error(f"❌ Server error: {response.status_code} on {request.url.path}")
        elif response.status_code >= 400:
            logger.warning(f"⚠️ Client error: {response.status_code} on {request.url.path}")
        
        return response
