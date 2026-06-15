"""
Configuration - All settings in one place
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Optional

# Get root directory
ROOT_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings"""
    
    # ============================================================
    # APPLICATION
    # ============================================================
    APP_NAME: str = "SAP AI Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    # ============================================================
    # AZURE OPENAI
    # ============================================================
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"
    
    # ============================================================
    # SAP DATA SOURCE
    # ============================================================
    DATA_SOURCE: str = "excel"  # Options: excel, hana, rfc
    SAP_DATA_PATH: str = "data"
    SAP_USE_RFC: bool = False
    
    # SAP HANA Connection (when DATA_SOURCE=hana)
    HANA_HOST: Optional[str] = ""
    HANA_PORT: Optional[int] = 30015
    HANA_USER: Optional[str] = ""
    HANA_PASSWORD: Optional[str] = ""
    HANA_DATABASE: Optional[str] = ""
    HANA_SCHEMA: Optional[str] = "SAPHANADB"
    HANA_TABLES: Optional[str] = ""
    USE_SQLITE_MEMORY: bool = True
    
    # SAP RFC Connection (when DATA_SOURCE=rfc or SAP_USE_RFC=True)
    SAP_ASHOST: Optional[str] = ""
    SAP_SYSNR: str = "00"
    SAP_CLIENT: str = "100"
    SAP_USER: Optional[str] = ""
    SAP_PASSWORD: Optional[str] = ""
    SAP_LANG: str = "EN"
    
    # ============================================================
    # REDIS CACHE
    # ============================================================
    REDIS_URL: str = "redis://localhost:6379/0"
    ENABLE_CACHE: bool = True
    ENABLE_QUERY_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600
    
    # ============================================================
    # CORS
    # ============================================================
    CORS_ORIGINS: List[str] = ["*"]
    
    # ============================================================
    # MULTI-TENANT
    # ============================================================
    ALLOW_CREDENTIAL_OVERRIDE: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Singleton instance
settings = Settings()
