"""Cache Service - Redis caching layer for SAP data"""
import redis
import json
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import timedelta
from ..config import settings


class CacheService:
    """Redis cache service for SAP data"""
    
    def __init__(self):
        """Initialize Redis connection"""
        self.redis_client = None
        self.cache_enabled = False
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.cache_enabled = True
            print("✅ Redis cache connected")
        except Exception as e:
            print(f"⚠️  Redis not available: {e}. Running without cache.")
            self.cache_enabled = False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.cache_enabled:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default 1 hour, 0 = no expiration)
        """
        if not self.cache_enabled:
            return
        
        try:
            serialized_value = json.dumps(value, default=str)
            
            # Handle ttl=0 or negative (no expiration)
            if ttl <= 0:
                # No expiration - use SET instead of SETEX
                self.redis_client.set(key, serialized_value)
            else:
                # With expiration - use SETEX
                self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            print(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        if not self.cache_enabled:
            return
        
        try:
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Cache delete error: {e}")
    
    def clear_pattern(self, pattern: str):
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Redis key pattern (e.g., "sap:vbak:*")
        """
        if not self.cache_enabled:
            return
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                print(f"🗑️  Cleared {len(keys)} cache keys matching '{pattern}'")
        except Exception as e:
            print(f"Cache clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.cache_enabled:
            return {"enabled": False}
        
        try:
            info = self.redis_client.info()
            return {
                "enabled": True,
                "used_memory": info.get("used_memory_human"),
                "total_keys": self.redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            return {"enabled": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return round((hits / total * 100) if total > 0 else 0, 2)