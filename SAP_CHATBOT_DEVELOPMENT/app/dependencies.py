"""
Dependency Injection - FastAPI dependencies
"""
from functools import lru_cache
from loguru import logger

# Global service instances (initialized in main.py)
_cache_service = None
_data_service = None
_ai_service = None
_sap_service = None
_schema_loader = None
_auto_loader = None


def set_services(cache, data, ai, sap, schema=None, auto=None):
    """
    Set global service instances (called from main.py on startup)
    """
    global _cache_service, _data_service, _ai_service, _sap_service, _schema_loader, _auto_loader
    _cache_service = cache
    _data_service = data
    _ai_service = ai
    _sap_service = sap
    _schema_loader = schema
    _auto_loader = auto
    logger.info("✓ Services registered in dependencies")


def get_cache_service():
    """Get CacheService instance"""
    return _cache_service


def get_data_service():
    """Get DataService instance"""
    return _data_service


def get_ai_service():
    """Get AzureOpenAIService instance"""
    return _ai_service


def get_sap_service():
    """Get SAPService instance"""
    return _sap_service


def get_schema_loader():
    """Get SchemaLoaderService instance"""
    return _schema_loader


def get_auto_loader():
    """Get AutoLoaderService instance"""
    return _auto_loader
