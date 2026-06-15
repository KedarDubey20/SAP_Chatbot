"""
Models Package - All Pydantic schemas
"""
from .model import (
    # AI Query Models
    QueryRequest,
    QueryResponse,

    # SAP Data Models
    OrderRequest,
    OrderResponse,
    SummaryResponse,

    # Cache Models
    CacheStatsResponse,
    CacheClearRequest,

    # Schema Models
    TableSchema,
    SchemaDiscoveryResponse,
    TableListResponse,
    TableSchemaResponse,
    TableColumnsResponse,
    TableTypesResponse,
    SchemaExportResponse,
    AIFormattedSchemaResponse,

    # Loader Models
    LoadedTableInfo,
    LoadSummary,
    AutoLoadResponse,
    RefreshTableResponse,
    LoadStatusResponse,
    FileChangeResponse,
    RedisVerifyResponse,

    # Health Models
    HealthResponse,
    SystemStatusResponse,

    # Error Models
    ErrorResponse,

    # Utility Models
    MessageResponse,
    StatusResponse,

    # Session / Chat Models
    TitleGenerateRequest,
    TitleGenerateResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionListResponse,
    MessageSaveRequest,
    MessageSaveResponse,
    MessagesListResponse,
)

__all__ = [
    # AI Query
    'QueryRequest',
    'QueryResponse',

    # SAP Data
    'OrderRequest',
    'OrderResponse',
    'SummaryResponse',

    # Cache
    'CacheStatsResponse',
    'CacheClearRequest',

    # Schema
    'TableSchema',
    'SchemaDiscoveryResponse',
    'TableListResponse',
    'TableSchemaResponse',
    'TableColumnsResponse',
    'TableTypesResponse',
    'SchemaExportResponse',
    'AIFormattedSchemaResponse',

    # Loader
    'LoadedTableInfo',
    'LoadSummary',
    'AutoLoadResponse',
    'RefreshTableResponse',
    'LoadStatusResponse',
    'FileChangeResponse',
    'RedisVerifyResponse',

    # Health
    'HealthResponse',
    'SystemStatusResponse',

    # Error
    'ErrorResponse',

    # Utility
    'MessageResponse',
    'StatusResponse',

    # Session / Chat
    'TitleGenerateRequest',
    'TitleGenerateResponse',
    'SessionCreateRequest',
    'SessionResponse',
    'SessionListResponse',
    'MessageSaveRequest',
    'MessageSaveResponse',
    'MessagesListResponse',
]