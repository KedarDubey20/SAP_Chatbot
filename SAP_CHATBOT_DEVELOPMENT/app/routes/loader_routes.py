"""
Data Loader Routes - Auto-loading and refresh management
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from loguru import logger

from ..dependencies import get_auto_loader

router = APIRouter(prefix="/api/v1/loader", tags=["Data Loader"])


@router.post("/load-all")
async def auto_load_all_data(
    force_reload: bool = Query(False, description="Force reload even if data hasn't changed"),
    auto_loader = Depends(get_auto_loader)
):
    """
    Auto-load data from all available sources
    Detects Excel, Redis, HANA, or RFC sources automatically
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        logger.info(f"🔄 Auto-loading all data (force={force_reload})")
        
        summary = auto_loader.auto_load_all(force_reload=force_reload)
        
        return {
            "success": True,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"❌ Auto-load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh/{table_name}")
async def refresh_table(
    table_name: str,
    force: bool = Query(False, description="Force refresh regardless of interval"),
    auto_loader = Depends(get_auto_loader)
):
    """
    Refresh a specific table
    Will check interval and only refresh if needed (unless force=True)
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        if force:
            # Get schema and reload
            from ..dependencies import get_schema_loader
            schema_loader = get_schema_loader()
            schema = schema_loader.get_schema(table_name)
            
            if not schema:
                raise HTTPException(
                    status_code=404,
                    detail=f"Table '{table_name}' not found"
                )
            
            result = auto_loader._load_from_excel(table_name, schema, force_reload=True)
        else:
            result = auto_loader.refresh_if_needed(table_name)
        
        if result:
            return {
                "success": True,
                "message": f"Table '{table_name}' refreshed",
                "result": result
            }
        else:
            return {
                "success": False,
                "message": f"Table '{table_name}' does not need refresh yet"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Refresh error for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_load_status(
    auto_loader = Depends(get_auto_loader)
):
    """
    Get current load status for all tables
    Shows last load time, age, and file hash
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        status = auto_loader.get_load_status()
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"❌ Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-reload-all")
async def force_reload_all_tables(
    auto_loader = Depends(get_auto_loader)
):
    """
    Force reload ALL tables (ignore change detection)
    Use this when you know data has changed externally
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        logger.info("🔄 Force reloading all tables")
        
        summary = auto_loader.force_reload_all()
        
        return {
            "success": True,
            "message": "All tables force reloaded",
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"❌ Force reload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-changes/{table_name}")
async def check_table_changes(
    table_name: str,
    auto_loader = Depends(get_auto_loader)
):
    """
    Check if a table has changed (file hash comparison)
    Does NOT reload data, just checks
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        from ..dependencies import get_schema_loader
        schema_loader = get_schema_loader()
        schema = schema_loader.get_schema(table_name)
        
        if not schema or schema['source'] != 'excel':
            raise HTTPException(
                status_code=400,
                detail=f"Table '{table_name}' not found or not from Excel source"
            )
        
        from pathlib import Path
        file_path = Path(schema['file_path'])
        current_hash = auto_loader._calculate_file_hash(file_path)
        
        old_hash = auto_loader.file_hashes.get(table_name)
        changed = (old_hash != current_hash) if old_hash else True
        
        return {
            "table": table_name,
            "changed": changed,
            "current_hash": current_hash,
            "previous_hash": old_hash,
            "file": file_path.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Change check error for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-redis/{table_name}")
async def verify_redis_data(
    table_name: str,
    auto_loader = Depends(get_auto_loader)
):
    """
    Verify Redis data integrity for a table
    Checks metadata exists, data exists, and record counts match
    """
    try:
        if not auto_loader:
            raise HTTPException(
                status_code=503,
                detail="Auto loader not available"
            )
        
        is_valid = auto_loader._verify_redis_data(table_name)
        
        return {
            "table": table_name,
            "valid": is_valid,
            "message": "Redis data is valid" if is_valid else "Redis data is invalid or missing"
        }
        
    except Exception as e:
        logger.error(f"❌ Redis verification error for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
