"""
AI Query Routes - Natural language processing endpoints (FIXED VERSION)
✅ Comprehensive error logging
✅ Proper Pydantic validation error handling
✅ Detailed error responses
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import ValidationError
from typing import Optional, List, Dict, Any
from loguru import logger
import traceback

from ..models import QueryRequest, QueryResponse
from ..dependencies import get_sap_service

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])


@router.post("/query", response_model=QueryResponse)
async def ai_query(
    request: QueryRequest,
    sap_service = Depends(get_sap_service)
):
    """
    Process natural language query using AI
    
    Examples:
    - "Show me all sales orders"
    - "Get details for order 1"
    - "What's the total value of all orders?"
    """
    try:
        logger.info(f"🤖 AI Query: {request.query}")
        
        result = await sap_service.process_ai_query(
            request.query,
            request.conversation_history,
            session_id=request.session_id or "default"
        )
        
        # Validate result has required fields for QueryResponse
        if not isinstance(result, dict):
            logger.error(f"❌ Invalid result type: {type(result)}")
            raise ValueError("Service returned non-dictionary result")
        
        # Check for required fields
        required_fields = ['success', 'query']
        missing_fields = [f for f in required_fields if f not in result]
        
        if missing_fields:
            logger.error(f"❌ Missing required fields in result: {missing_fields}")
            logger.error(f"   Result keys: {result.keys()}")
            
            # Add missing fields with defaults
            if 'success' not in result:
                result['success'] = False
            if 'query' not in result:
                result['query'] = request.query
            if 'response' not in result:
                result['response'] = result.get('error', 'Unknown error occurred')
        
        # Ensure 'response' field exists (required by Pydantic)
        if 'response' not in result:
            if result.get('success'):
                result['response'] = result.get('sql', 'Query executed successfully')
            else:
                result['response'] = result.get('error', 'An error occurred')
        
        try:
            return QueryResponse(**result)
            
        except ValidationError as ve:
            logger.error(f"❌ Pydantic Validation Error")
            logger.error(f"   Query: {request.query}")
            logger.error(f"   Validation Errors: {ve.errors()}")
            logger.error(f"   Result that failed validation:")
            for key, value in result.items():
                logger.error(f"      {key}: {type(value).__name__} = {str(value)[:100]}")
            
            # Create a valid response with error info
            error_response = {
                "success": False,
                "query": request.query,
                "response": f"Response validation failed: {', '.join([e['loc'][0] for e in ve.errors()])}",
                "error": "Internal response format error",
                "error_type": "ValidationError"
            }
            return QueryResponse(**error_response)
        
    except ValidationError as e:
        # Pydantic validation errors from request
        logger.error(f"❌ Request Validation Error")
        logger.error(f"   Validation Errors: {e.errors()}")
        logger.error(f"   Request Data: {request}")
        
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid request format",
                "validation_errors": e.errors(),
                "message": "Please check your request structure"
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except AttributeError as e:
        logger.error(f"❌ AttributeError in AI Query Route")
        logger.error(f"   Query: {request.query}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   → Likely missing method in sap_service")
        logger.error(f"   Stack Trace:", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Service configuration error",
                "error_type": "AttributeError",
                "message": "The SAP service is not properly configured. Please contact support.",
                "query": request.query
            }
        )
    
    except ValueError as e:
        logger.error(f"❌ ValueError in AI Query Route")
        logger.error(f"   Query: {request.query}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Stack Trace:", exc_info=True)
        
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid data",
                "error_type": "ValueError",
                "message": str(e),
                "query": request.query
            }
        )
    
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR in AI Query Route")
        logger.error(f"   Query: {request.query}")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Full Stack Trace:")
        logger.error(traceback.format_exc())
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "query": request.query,
                "message": "An unexpected error occurred. Please try again or contact support."
            }
        )


@router.post("/analyze")
async def analyze_intent(
    query: str,
    sap_service = Depends(get_sap_service)
):
    """
    Analyze query intent without executing
    Useful for debugging or understanding what AI will do
    """
    try:
        logger.info(f"🔍 Analyzing intent for: {query}")
        
        intent = sap_service.ai.analyze_query_intent(query)
        
        return {
            "query": query,
            "intent_analysis": intent,
            "success": True
        }
    
    except AttributeError as e:
        logger.error(f"❌ AttributeError in Intent Analysis")
        logger.error(f"   Query: {query}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   → AI service missing 'analyze_query_intent' method")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AI service method not found",
                "error_type": "AttributeError",
                "message": "The AI service is not properly configured."
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Intent analysis error")
        logger.error(f"   Query: {query}")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Stack Trace:", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "message": "Failed to analyze query intent"
            }
        )


@router.post("/sql/generate")
async def generate_sql(
    query: str,
    sap_service = Depends(get_sap_service)
):
    """
    Generate SQL from natural language without executing
    Useful for testing or validation
    """
    try:
        logger.info(f"🔧 Generating SQL for: {query}")
        
        schema = sap_service._get_schema()
        
        if not schema:
            logger.warning(f"⚠️ No schema available")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Database not ready",
                    "message": "No data schema available. Please ensure data is loaded."
                }
            )
        
        sql_result = sap_service.ai.generate_sql_from_query(query, schema)
        
        return {
            "query": query,
            "sql": sql_result.get("sql"),
            "explanation": sql_result.get("explanation"),
            "confidence": sql_result.get("confidence"),
            "tables_used": sql_result.get("tables_used"),
            "success": True
        }
    
    except KeyError as e:
        logger.error(f"❌ KeyError in SQL Generation")
        logger.error(f"   Query: {query}")
        logger.error(f"   Missing Key: {str(e)}")
        logger.error(f"   SQL Result: {sql_result if 'sql_result' in locals() else 'N/A'}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Incomplete SQL generation response",
                "error_type": "KeyError",
                "missing_field": str(e),
                "message": "AI service returned incomplete data"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ SQL generation error")
        logger.error(f"   Query: {query}")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Stack Trace:", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "message": "Failed to generate SQL query"
            }
        )


@router.get("/health")
async def ai_health_check(sap_service = Depends(get_sap_service)):
    """
    Health check for AI service
    Verifies all components are working
    """
    try:
        health = {
            "ai_service": "unknown",
            "database": "unknown",
            "cache": "unknown",
            "schema_available": False,
            "tables_count": 0
        }
        
        # Check AI service
        if hasattr(sap_service, 'ai') and sap_service.ai:
            health["ai_service"] = "healthy"
        else:
            health["ai_service"] = "missing"
        
        # Check database
        try:
            schema = sap_service._get_schema()
            if schema:
                health["database"] = "healthy"
                health["schema_available"] = True
                health["tables_count"] = len(schema)
                health["tables"] = list(schema.keys())
            else:
                health["database"] = "empty"
        except Exception as e:
            health["database"] = f"error: {str(e)}"
        
        # Check cache
        if hasattr(sap_service, 'cache') and sap_service.cache:
            if hasattr(sap_service.cache, 'cache_enabled'):
                health["cache"] = "enabled" if sap_service.cache.cache_enabled else "disabled"
            else:
                health["cache"] = "unknown"
        else:
            health["cache"] = "not configured"
        
        overall_status = "healthy" if (
            health["ai_service"] == "healthy" and
            health["database"] == "healthy" and
            health["schema_available"]
        ) else "degraded"
        
        health["status"] = overall_status
        
        return health
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/follow-ups")
async def generate_follow_ups(request: dict):
    try:
        from ..services.ai_service import azure_openai_service as ai

        response = ai.client.chat.completions.create(
            model=ai.deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate exactly 3 short follow-up question suggestions for an SAP data chatbot. "
                        "Questions must be relevant to the user's current query and data returned. "
                        "Return ONLY a JSON array of 3 strings, nothing else. "
                        "Example: [\"Show top vendors\", \"Filter by date\", \"Show as chart\"]"
                    )
                },
                {
                    "role": "user",
                    "content": f"User asked: {request.get('query')}\n{request.get('result_summary', '')}"
                }
            ],
            temperature=0.4,
            max_tokens=100
        )

        import json
        content = response.choices[0].message.content.strip()
        follow_ups = json.loads(content)
        return {"follow_ups": follow_ups[:3]}

    except Exception as e:
        return {"follow_ups": [
            "Show top 5 orders by value",
            "Which customer has the most orders?",
            "Give me a summary of all SAP data"
        ]}