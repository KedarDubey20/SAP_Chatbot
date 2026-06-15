"""
Rate Limit Middleware - Prevent API abuse
Implements token bucket algorithm for rate limiting
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm
    Limits requests per IP address
    """
    
    def __init__(
        self,
        app,
        enabled: bool = False,
        requests_per_minute: int = 60,
        burst_size: int = 100
    ):
        """
        Initialize rate limit middleware
        
        Args:
            app: FastAPI application
            enabled: Whether to enforce rate limiting
            requests_per_minute: Max requests per minute per IP
            burst_size: Max burst requests allowed
        """
        super().__init__(app)
        self.enabled = enabled
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        
        # Token bucket storage: {ip: (tokens, last_update)}
        self.buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (burst_size, time.time())
        )
        
        # Cleanup old buckets periodically
        self.last_cleanup = time.time()
        
        if self.enabled:
            logger.info(
                f"✓ Rate limiting enabled: {requests_per_minute}/min, "
                f"burst: {burst_size}"
            )
        else:
            logger.info("⚠️ Rate limiting disabled")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        
        # Skip if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check rate limit
        allowed, remaining = self._check_rate_limit(client_ip)
        
        if not allowed:
            logger.warning(f"🚫 Rate limit exceeded for {client_ip}")
            
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute}/min",
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60"
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(remaining))
        
        # Cleanup old buckets periodically (every 5 minutes)
        current_time = time.time()
        if current_time - self.last_cleanup > 300:
            self._cleanup_buckets()
            self.last_cleanup = current_time
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address
        Checks X-Forwarded-For header first (for proxies)
        """
        # Check X-Forwarded-For header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in the chain
            return forwarded.split(",")[0].strip()
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _check_rate_limit(self, client_ip: str) -> Tuple[bool, float]:
        """
        Check if request is allowed (token bucket algorithm)
        
        Args:
            client_ip: Client IP address
            
        Returns:
            (allowed, remaining_tokens)
        """
        current_time = time.time()
        
        # Get or create bucket
        tokens, last_update = self.buckets[client_ip]
        
        # Calculate tokens to add (based on time elapsed)
        time_elapsed = current_time - last_update
        tokens_to_add = time_elapsed * (self.requests_per_minute / 60.0)
        
        # Update tokens (capped at burst_size)
        tokens = min(self.burst_size, tokens + tokens_to_add)
        
        # Check if request allowed
        if tokens >= 1.0:
            # Allow request, consume 1 token
            tokens -= 1.0
            self.buckets[client_ip] = (tokens, current_time)
            return True, tokens
        else:
            # Deny request
            self.buckets[client_ip] = (tokens, current_time)
            return False, 0.0
    
    def _cleanup_buckets(self):
        """Remove old bucket entries (inactive for >1 hour)"""
        current_time = time.time()
        to_remove = []
        
        for ip, (tokens, last_update) in self.buckets.items():
            if current_time - last_update > 3600:  # 1 hour
                to_remove.append(ip)
        
        for ip in to_remove:
            del self.buckets[ip]
        
        if to_remove:
            logger.debug(f"🧹 Cleaned up {len(to_remove)} old rate limit buckets")
