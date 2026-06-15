"""
Health & System Status Routes
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger

from ..models import HealthResponse
from ..dependencies import get_sap_service, get_cache_service, get_data_service
from ..config import settings

router = APIRouter(tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def root(
    cache_service = Depends(get_cache_service),
    data_service = Depends(get_data_service)
):
    """
    Root endpoint - basic health check
    """
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        redis_connected=cache_service.cache_enabled if cache_service else False,
        tables_loaded=len(data_service.tables_loaded) if data_service else 0
    )


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check(
    cache_service = Depends(get_cache_service),
    data_service = Depends(get_data_service)
):
    """
    Detailed health check endpoint
    
    Returns:
    - Application status
    - Redis connection status
    - Number of tables loaded
    """
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        redis_connected=cache_service.cache_enabled if cache_service else False,
        tables_loaded=len(data_service.tables_loaded) if data_service else 0
    )


@router.get("/api/v1/status")
async def system_status(
    cache_service = Depends(get_cache_service),
    data_service = Depends(get_data_service)
):
    """
    Comprehensive system status
    
    Returns detailed information about all services
    """
    status = {
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
        "services": {
            "cache": {
                "enabled": cache_service.cache_enabled if cache_service else False,
                "type": "Redis" if cache_service and cache_service.cache_enabled else "None"
            },
            "database": {
                "type": "SQLite (in-memory)",
                "tables_loaded": len(data_service.tables_loaded) if data_service else 0,
                "tables": data_service.tables_loaded if data_service else []
            },
            "ai": {
                "provider": "Azure OpenAI",
                "model": settings.AZURE_OPENAI_DEPLOYMENT
            }
        }
    }
    
    return status


@router.get("/api/v1/ping")
async def ping():
    """
    Simple ping endpoint for uptime monitoring
    """
    return {"ping": "pong"}


@router.websocket("/ws/query")
async def websocket_query(
    websocket: WebSocket,
    sap_service = Depends(get_sap_service)
):
    """
    WebSocket endpoint for streaming AI responses
    Enables typewriter effect on frontend
    
    Client sends:
    {
        "query": "user question",
        "history": [...]
    }
    
    Server streams back:
    - {"type": "chunk", "content": "text chunk"}
    - {"type": "complete", "result": {...}}
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive query
            data = await websocket.receive_json()
            query = data.get("query", "")
            history = data.get("history", [])
            
            if not query:
                await websocket.send_json({
                    "type": "error",
                    "content": "No query provided"
                })
                continue
            
            logger.info(f"🔌 WebSocket query: {query}")
            
            # Process query
            result = await sap_service.process_ai_query(query, history)
            
            # Stream response for typewriter effect
            response_text = result.get("response", "")
            
            # Send chunks
            for i in range(0, len(response_text), 5):
                chunk = response_text[i:i+5]
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk
                })
            
            # Send complete result
            await websocket.send_json({
                "type": "complete",
                "result": result
            })
            
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except:
            pass
