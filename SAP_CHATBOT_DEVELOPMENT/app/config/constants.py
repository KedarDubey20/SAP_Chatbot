"""
Application Constants
Centralized constants and enums
"""
from enum import Enum


# ============================================================
# DATA SOURCES
# ============================================================

class DataSource(str, Enum):
    """Available data sources"""
    EXCEL = "excel"
    HANA = "hana"
    RFC = "rfc"
    REDIS = "redis"


# ============================================================
# QUERY INTENTS
# ============================================================

class QueryIntent(str, Enum):
    """Query intent classifications"""
    GREETING = "greeting"
    HELP = "help"
    DATA_QUERY = "data_query"
    EXPLANATION_REQUEST = "explanation_request"
    GENERAL_QUESTION = "general_question"


# ============================================================
# SAP TABLES
# ============================================================

class SAPTable(str, Enum):
    """Standard SAP table names"""
    VBAK = "VBAK"  # Sales Document Header
    VBAP = "VBAP"  # Sales Document Items
    VBEP = "VBEP"  # Sales Document Schedule Lines
    KNA1 = "KNA1"  # Customer Master
    MARA = "MARA"  # Material Master
    EKKO = "EKKO"  # Purchasing Document Header
    EKPO = "EKPO"  # Purchasing Document Items


# ============================================================
# CACHE KEYS
# ============================================================

class CacheKey:
    """Redis cache key patterns"""
    TABLE = "sap:table:{table_name}"
    METADATA = "sap:meta:{table_name}"
    ORDER = "sap:order:{order_id}"
    ITEMS = "sap:items:{order_id}"
    SCHEDULE = "sap:schedule:{order_id}"
    QUERY = "sap:query:{query_hash}"
    SCHEMA = "sap:schema:{table_name}"


# ============================================================
# FILE PATTERNS
# ============================================================

class FilePattern:
    """Excel file naming patterns"""
    VBAK_PATTERN = r".*VBAK.*Header.*\.(xlsx|XLSX)"
    VBAP_PATTERN = r".*VBAP.*Item.*\.(xlsx|XLSX)"
    VBEP_PATTERN = r".*VBEP.*Schedule.*\.(xlsx|XLSX)"


# ============================================================
# API LIMITS
# ============================================================

class APILimits:
    """API request limits"""
    MAX_RESULTS = 1000
    DEFAULT_LIMIT = 10
    MAX_QUERY_LENGTH = 500
    MAX_CONVERSATION_HISTORY = 10


# ============================================================
# HTTP STATUS CODES
# ============================================================

class StatusCode:
    """Common HTTP status codes"""
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    RATE_LIMIT = 429
    SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# ============================================================
# ERROR MESSAGES
# ============================================================

class ErrorMessage:
    """Standard error messages"""
    UNAUTHORIZED = "Authentication required"
    INVALID_API_KEY = "Invalid API key"
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded. Please try again later."
    TABLE_NOT_FOUND = "Table '{table_name}' not found"
    ORDER_NOT_FOUND = "Order {order_id} not found"
    INVALID_QUERY = "Invalid query format"
    DATABASE_ERROR = "Database error occurred"
    CACHE_UNAVAILABLE = "Cache service unavailable"
    AI_SERVICE_ERROR = "AI service error"


# ============================================================
# SUCCESS MESSAGES
# ============================================================

class SuccessMessage:
    """Standard success messages"""
    DATA_LOADED = "Data loaded successfully"
    CACHE_CLEARED = "Cache cleared successfully"
    SCHEMA_DISCOVERED = "Schema discovered successfully"
    QUERY_EXECUTED = "Query executed successfully"
