"""
FastAPI Main Application - Clean route organization with auto-refresh
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import sys
import asyncio
from datetime import datetime

# Import configuration
from .config import settings

# Import services
from .services import CacheService, DataService, SAPService

# Import routes
from .routes import (
    ai_router,
    sap_router,
    cache_router,
    health_router,
    schema_router,
    loader_router,
    session_router
)

# Import dependencies manager
from . import dependencies


# ============================================================
# BACKGROUND TASKS
# ============================================================
background_tasks = set()


async def periodic_data_sync(
    data_service: DataService,
    cache_service: CacheService,
    interval_hours: int = 1
):
    interval_seconds = interval_hours * 3600

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Auto-refresh triggered at {current_time}")
            logger.info(f"{'='*60}")

            if cache_service.cache_enabled:
                data_service.sync_all_to_redis()
                logger.info(f"✅ Auto-refresh completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"⏰ Next refresh in {interval_hours} hour(s)")
            else:
                logger.warning("⚠️ Redis not available, skipping refresh")

            logger.info(f"{'='*60}\n")

        except Exception as e:
            logger.error(f"❌ Auto-refresh error: {e}")
            logger.warning(f"⚠️ Will retry in {interval_hours} hour(s)")


# ============================================================
# STARTUP/SHUTDOWN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize all services on boot"""
    logger.info("🚀 SAP AI Assistant starting...")

    data_svc  = None
    cache_svc = None

    try:
        # ── Core services ─────────────────────────────────────────────
        cache_svc = CacheService()
        data_svc  = DataService(settings.SAP_DATA_PATH, cache_svc)

        # ── AI service ────────────────────────────────────────────────
        from .services.ai_service import azure_openai_service
        ai_svc = azure_openai_service

        # ── Schema loader ─────────────────────────────────────────────
        from .services import SchemaLoaderService, AutoLoaderService
        schema_loader = SchemaLoaderService(
            data_path    = settings.SAP_DATA_PATH,
            cache_service = cache_svc,
            config        = settings
        )

        # ── Auto loader ───────────────────────────────────────────────
        auto_loader = AutoLoaderService(
            data_service  = data_svc,
            cache_service = cache_svc,
            schema_loader = schema_loader,
            config        = settings
        )

        # ── Load data ─────────────────────────────────────────────────
        logger.info("📊 Auto-loading data from all sources...")
        load_summary = auto_loader.auto_load_all()
        logger.info(f"✓ Loaded {len(load_summary['loaded_tables'])} tables")

        # ── Redis sync + background refresh ───────────────────────────
        if cache_svc.cache_enabled:
            logger.info("📊 Initial data sync to Redis...")
            data_svc.sync_all_to_redis()

            refresh_interval = 1  # hours
            task = asyncio.create_task(
                periodic_data_sync(data_svc, cache_svc, interval_hours=refresh_interval)
            )
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

            logger.info(f"⏰ Auto-refresh enabled: Every {refresh_interval} hour(s)")
            logger.info(f"💡 Manual refresh: POST /api/v1/cache/sync/refresh")
        else:
            logger.warning("⚠️ Redis not available — auto-refresh disabled")

        # ── SAP service ───────────────────────────────────────────────
        sap_svc = SAPService(data_svc, cache_svc, ai_svc)

        # ── Metadata + relationships auto-generation ──────────────────
        # Runs once on boot. Only processes NEW tables — skips existing.
        # Survives reboots: generated_metadata.json + relationships.json
        # are persisted to app/config/ and reloaded on next boot.
        try:
            from .services.metadata_service import MetadataService
            from .services.sap_service import (
                HANA_HOST, HANA_PORT, HANA_USER,
                HANA_PASSWORD, HANA_SCHEMA, SAP_TABLES
            )

            metadata_svc = MetadataService(
                hana_host     = HANA_HOST,
                hana_port     = HANA_PORT,
                hana_user     = HANA_USER,
                hana_password = HANA_PASSWORD,
                hana_schema   = HANA_SCHEMA,
                ai_client     = ai_svc.client,
                ai_deployment = ai_svc.deployment
            )

            # Use already-cached schema — no extra HANA call
            schema_info = sap_svc._get_schema()
            await metadata_svc.run(SAP_TABLES, schema_info)
            logger.info("✅ Metadata + relationships ready")

        except Exception as e:
            # Non-fatal — bot still works, just without rich metadata
            logger.warning(f"⚠️ Metadata generation failed (non-fatal): {e}")

        # ── Register all services in dependency injection ─────────────
        dependencies.set_services(
            cache_svc,
            data_svc,
            ai_svc,
            sap_svc,
            schema_loader,
            auto_loader
        )

        logger.info("✅ SAP AI Assistant ready!")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("🛑 Stopping background tasks...")
    for task in background_tasks:
        task.cancel()

    logger.info("👋 Shutting down...")
    if data_svc:
        data_svc.close()


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title       = settings.APP_NAME,
    description = "AI-powered SAP data query assistant with automatic data synchronization",
    version     = "2.0.0",
    lifespan    = lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ============================================================
# REGISTER ROUTES
# ============================================================
app.include_router(health_router)
app.include_router(ai_router)
app.include_router(sap_router)
app.include_router(cache_router)
app.include_router(schema_router)
app.include_router(loader_router)
app.include_router(session_router)


# ============================================================
# ERROR HANDLING
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}")
    return {
        "error":  "Internal server error",
        "detail": str(exc) if settings.DEBUG else "An error occurred"
    }


# ============================================================
# ROOT ENDPOINT
# ============================================================
@app.get("/")
async def root():
    return {
        "message":          "SAP AI Assistant API",
        "version":          "2.0.0",
        "auto_refresh":     "enabled" if CacheService().cache_enabled else "disabled",
        "refresh_interval": "1 hour"
    }


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host   = settings.API_HOST,
        port   = settings.API_PORT,
        reload = settings.DEBUG
    )