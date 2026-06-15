"""
SAP Data Routes - Direct data access endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from loguru import logger

from ..models import OrderResponse, QueryResponse, SummaryResponse
from ..dependencies import get_sap_service

router = APIRouter(prefix="/api/v1/sap", tags=["SAP Data"])


@router.get("/orders", response_model=QueryResponse)
async def get_all_orders(
    limit: int = Query(10, ge=1, le=100),
    sap_service = Depends(get_sap_service)
):
    """
    Get all sales orders
    
    Parameters:
    - limit: Maximum number of orders to return (1-100)
    """
    try:
        results = sap_service.get_all_orders(limit=limit)
        
        return QueryResponse(
            success=True,
            query=f"Get all orders (limit {limit})",
            response=f"Found {len(results)} orders",
            results=results,
            result_count=len(results),
            from_cache=False
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order_by_id(
    order_id: int,
    sap_service = Depends(get_sap_service)
):
    """
    Get specific order with items
    
    Parameters:
    - order_id: Sales document number
    """
    try:
        result = sap_service.get_order_by_id(order_id)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        
        return OrderResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    sap_service = Depends(get_sap_service)
):
    """
    Get summary statistics for all SAP data
    
    Returns:
    - Total tables loaded
    - Record counts per table
    - Column counts per table
    """
    try:
        result = sap_service.get_summary()
        
        return SummaryResponse(**result)
        
    except Exception as e:
        logger.error(f"❌ Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def get_available_tables(
    sap_service = Depends(get_sap_service)
):
    """
    Get list of available SAP tables with schema info
    """
    try:
        schema = sap_service._get_schema()
        
        return {
            "tables": list(schema.keys()),
            "count": len(schema),
            "schema": schema
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/schema")
async def get_table_schema(
    table_name: str,
    sap_service = Depends(get_sap_service)
):
    """
    Get schema (column list) for a specific table
    """
    try:
        schema = sap_service._get_schema()
        
        if table_name.lower() not in schema:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )
        
        return {
            "table": table_name,
            "columns": schema[table_name.lower()],
            "column_count": len(schema[table_name.lower()])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
