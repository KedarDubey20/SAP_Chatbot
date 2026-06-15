"""
Pydantic Models - Request/Response schemas for all endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ============================================================
# AI QUERY MODELS
# ============================================================

class QueryRequest(BaseModel):
    """Request for AI natural language query"""
    query: str = Field(..., description="Natural language query")
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session ID for context tracking"
    )
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Previous conversation messages"
    )
class QueryResponse(BaseModel):
    """Response for AI query"""
    success: bool = True
    query: str
    intent: Optional[str] = None
    response: str
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    result_count: int = 0
    data_source: Optional[str] = None
    from_cache: bool = False
    is_conversational: Optional[bool] = False
    message: Optional[str] = None
    show_chart: Optional[bool] = False
    chart_type: Optional[str] = "bar"
    is_multi_step: Optional[bool] = False
    steps_results: Optional[List[Dict[str, Any]]] = None
    thinking_steps: Optional[List[str]] = None


# ============================================================
# SAP DATA MODELS
# ============================================================

class OrderRequest(BaseModel):
    """Request for order details"""
    order_id: int = Field(..., description="Sales document number")


class OrderResponse(BaseModel):
    """Response with order details"""
    success: bool = True
    order_number: int
    header: Dict[str, Any]
    items: List[Dict[str, Any]] = []
    schedule_lines: Optional[List[Dict[str, Any]]] = []
    item_count: int = 0
    from_cache: bool = False
    data_source: Optional[str] = None
    error: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response with summary statistics"""
    success: bool = True
    total_tables: int = 0
    tables: Dict[str, Dict[str, Any]] = {}
    from_cache: bool = False


# ============================================================
# CACHE MODELS
# ============================================================

class CacheStatsResponse(BaseModel):
    """Cache statistics response"""
    enabled: bool
    used_memory: Optional[str] = None
    total_keys: Optional[int] = None
    hits: Optional[int] = None
    misses: Optional[int] = None
    hit_rate: Optional[float] = None


class CacheClearRequest(BaseModel):
    """Request to clear cache"""
    pattern: str = Field(default="sap:*", description="Redis key pattern to clear")


# ============================================================
# SCHEMA MODELS
# ============================================================

class TableSchema(BaseModel):
    """Schema information for a table"""
    source: str = Field(..., description="Data source: redis, excel, hana, rfc")
    table_name: str
    columns: List[str]
    column_count: int
    record_count: Optional[int] = None
    data_types: Optional[Dict[str, str]] = None
    file_path: Optional[str] = None
    file_source: Optional[str] = None
    schema_name: Optional[str] = None
    last_updated: Optional[str] = None


class SchemaDiscoveryResponse(BaseModel):
    """Response from schema discovery"""
    success: bool = True
    total_tables: int
    tables: List[str]
    schemas: Dict[str, TableSchema]


class TableListResponse(BaseModel):
    """Response with list of tables"""
    total: int
    tables: List[str]


class TableSchemaResponse(BaseModel):
    """Response with table schema details"""
    table: str
    schema: TableSchema


class TableColumnsResponse(BaseModel):
    """Response with table columns"""
    table: str
    column_count: int
    columns: List[str]


class TableTypesResponse(BaseModel):
    """Response with column data types"""
    table: str
    data_types: Dict[str, str]


class SchemaExportResponse(BaseModel):
    """Response with exported schemas"""
    total_tables: int
    tables: Dict[str, TableSchema]
    summary: Dict[str, Dict[str, Any]]


class AIFormattedSchemaResponse(BaseModel):
    """Response with AI-formatted schemas"""
    format: str = "ai_context"
    content: str


# ============================================================
# LOADER MODELS
# ============================================================

class LoadedTableInfo(BaseModel):
    """Information about a loaded table"""
    table: str
    loaded: bool
    source: Optional[str] = None
    file: Optional[str] = None
    records: Optional[int] = None
    hash: Optional[str] = None
    timestamp: Optional[str] = None
    reason: Optional[str] = None


class LoadSummary(BaseModel):
    """Summary of data loading operation"""
    timestamp: str
    force_reload: bool
    loaded_tables: List[LoadedTableInfo]
    skipped_tables: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


class AutoLoadResponse(BaseModel):
    """Response from auto-load operation"""
    success: bool = True
    summary: LoadSummary


class RefreshTableResponse(BaseModel):
    """Response from table refresh"""
    success: bool
    message: str
    result: Optional[LoadedTableInfo] = None


class LoadStatusResponse(BaseModel):
    """Response with load status"""
    success: bool = True
    status: Dict[str, Any]


class FileChangeResponse(BaseModel):
    """Response for file change check"""
    table: str
    changed: bool
    current_hash: str
    previous_hash: Optional[str] = None
    file: str


class RedisVerifyResponse(BaseModel):
    """Response from Redis verification"""
    table: str
    valid: bool
    message: str


# ============================================================
# HEALTH MODELS
# ============================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    app_name: str = "SAP AI Assistant"
    redis_connected: bool = False
    tables_loaded: int = 0


class SystemStatusResponse(BaseModel):
    """Detailed system status"""
    app: str
    version: str
    environment: str
    debug: bool
    services: Dict[str, Any]


# ============================================================
# ERROR MODELS
# ============================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: Optional[str] = None


# ============================================================
# UTILITY MODELS
# ============================================================

class MessageResponse(BaseModel):
    """Simple message response"""
    success: bool = True
    message: str


class StatusResponse(BaseModel):
    """Generic status response"""
    status: str
    details: Optional[Dict[str, Any]] = None


# ============================================================
# SESSION / CHAT HISTORY MODELS
# ============================================================

class TitleGenerateRequest(BaseModel):
    """Request to generate a session title from first message"""
    message: str = Field(
        ...,
        min_length=1,
        description="The user's first chat message used to derive the session title.",
        examples=["What are the key risks in the ValueStream risk register?"],
    )


class TitleGenerateResponse(BaseModel):
    """Response with generated session title"""
    title: str = Field(
        ...,
        description="A concise 3-4 word title summarising the user's intent.",
        examples=["ValueStream Risk Analysis"],
    )


class SessionCreateRequest(BaseModel):
    """Request to create a new chat session"""
    title: Optional[str] = None
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    """Single session response"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = 0


class SessionListResponse(BaseModel):
    """List of sessions"""
    success: bool = True
    sessions: List[SessionResponse]
    total: int


class MessageSaveRequest(BaseModel):
    """Request to save a message to a session"""
    role: str = Field(..., description="user or assistant")
    content: str
    sql_query: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None


class MessageSaveResponse(BaseModel):
    """Response after saving a message"""
    success: bool = True
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


class MessagesListResponse(BaseModel):
    """List of messages for a session"""
    success: bool = True
    session_id: str
    messages: List[Dict[str, Any]]
    total: int