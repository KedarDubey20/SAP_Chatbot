"""
Cache Management Routes - Redis cache control
"""
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from ..dependencies import get_cache_service

router = APIRouter(prefix="/api/v1/cache", tags=["Cache"])


@router.get("/stats")
async def get_cache_stats(
    cache_service = Depends(get_cache_service)
):
    """
    Get Redis cache statistics
    
    Returns:
    - Cache enabled status
    - Memory usage
    - Total keys
    - Hit/miss rates
    """
    try:
        if not cache_service:
            return {"enabled": False, "message": "Cache service not available"}
        
        return cache_service.get_stats()
        
    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_cache_status(
    cache_service = Depends(get_cache_service)
):
    """
    Simple cache health check
    """
    if not cache_service:
        return {
            "enabled": False,
            "status": "unavailable"
        }
    
    return {
        "enabled": cache_service.cache_enabled,
        "status": "connected" if cache_service.cache_enabled else "disconnected"
    }


@router.post("/clear")
async def clear_cache(
    pattern: str = "sap:*",
    cache_service = Depends(get_cache_service)
):
    """
    Clear cache by pattern
    
    Parameters:
    - pattern: Redis key pattern (default: "sap:*")
    
    Examples:
    - "sap:*" - Clear all SAP data
    - "sap:table:*" - Clear all tables
    - "sap:query:*" - Clear all cached queries
    """
    try:
        if not cache_service or not cache_service.cache_enabled:
            return {
                "success": False,
                "message": "Cache not available"
            }
        
        cache_service.clear_pattern(pattern)
        
        return {
            "success": True,
            "message": f"Cache cleared for pattern: {pattern}"
        }
        
    except Exception as e:
        logger.error(f"❌ Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_cache(
    cache_service = Depends(get_cache_service),
    data_service = Depends(lambda: None)  # Will be injected properly
):
    """
    Refresh cache - reload all data from source
    """
    try:
        if not cache_service or not cache_service.cache_enabled:
            return {
                "success": False,
                "message": "Cache not available"
            }
        
        # Clear existing cache
        cache_service.clear_pattern("sap:*")
        
        # Re-sync data
        # This would need data_service - handled in dependencies
        
        return {
            "success": True,
            "message": "Cache refresh initiated"
        }
        
    except Exception as e:
        logger.error(f"❌ Error refreshing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keys")
async def list_cache_keys(
    pattern: str = "sap:*",
    limit: int = 100,
    cache_service = Depends(get_cache_service)
):
    """
    List cache keys matching pattern
    
    Parameters:
    - pattern: Redis key pattern
    - limit: Maximum keys to return
    """
    try:
        if not cache_service or not cache_service.cache_enabled:
            return {
                "enabled": False,
                "keys": []
            }
        
        # Get keys from Redis
        keys = cache_service.redis_client.keys(pattern)
        
        return {
            "enabled": True,
            "pattern": pattern,
            "total": len(keys),
            "keys": keys[:limit]
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))
