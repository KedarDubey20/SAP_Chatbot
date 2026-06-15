"""
Schema Management Routes - Schema discovery and inspection
"""
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from ..dependencies import get_schema_loader, get_auto_loader

router = APIRouter(prefix="/api/v1/schema", tags=["Schema"])


@router.get("/discover")
async def discover_schemas(
    schema_loader = Depends(get_schema_loader)
):
    """
    Auto-discover schemas from all available sources
    Priority: Redis > Excel > HANA > RFC
    """
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        schemas = schema_loader.discover_all_schemas()
        
        return {
            "success": True,
            "total_tables": len(schemas),
            "tables": list(schemas.keys()),
            "schemas": schemas
        }
        
    except Exception as e:
        logger.error(f"❌ Schema discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def get_all_tables(
    schema_loader = Depends(get_schema_loader)
):
    """Get list of all discovered tables"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        tables = schema_loader.get_all_tables()
        
        return {
            "total": len(tables),
            "tables": tables
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}")
async def get_table_schema(
    table_name: str,
    schema_loader = Depends(get_schema_loader)
):
    """Get detailed schema for a specific table"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        schema = schema_loader.get_schema(table_name)
        
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )
        
        return {
            "table": table_name,
            "schema": schema
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/columns")
async def get_table_columns(
    table_name: str,
    schema_loader = Depends(get_schema_loader)
):
    """Get column list for a specific table"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        columns = schema_loader.get_columns(table_name)
        
        if not columns:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found or has no columns"
            )
        
        return {
            "table": table_name,
            "column_count": len(columns),
            "columns": columns
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting columns for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/types")
async def get_table_types(
    table_name: str,
    schema_loader = Depends(get_schema_loader)
):
    """Get data types for all columns in a table"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        data_types = schema_loader.get_data_types(table_name)
        
        if not data_types:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found or no type info"
            )
        
        return {
            "table": table_name,
            "data_types": data_types
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting types for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_all_schemas(
    schema_loader = Depends(get_schema_loader)
):
    """Export all schemas in JSON format"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        return schema_loader.export_schemas()
        
    except Exception as e:
        logger.error(f"❌ Error exporting schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-format")
async def get_ai_formatted_schema(
    schema_loader = Depends(get_schema_loader)
):
    """Get schemas formatted for AI/LLM consumption"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        formatted = schema_loader.format_for_ai()
        
        return {
            "format": "ai_context",
            "content": formatted
        }
        
    except Exception as e:
        logger.error(f"❌ Error formatting schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_schemas(
    schema_loader = Depends(get_schema_loader)
):
    """Force refresh schema discovery"""
    try:
        if not schema_loader:
            raise HTTPException(
                status_code=503,
                detail="Schema loader not available"
            )
        
        schemas = schema_loader.discover_all_schemas()
        
        return {
            "success": True,
            "message": "Schemas refreshed",
            "total_tables": len(schemas)
        }
        
    except Exception as e:
        logger.error(f"❌ Schema refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
