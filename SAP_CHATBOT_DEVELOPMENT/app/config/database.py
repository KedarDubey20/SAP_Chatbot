"""
Database Configuration
Handles SQLite, SAP HANA, and other database connections
"""
from typing import Optional
from loguru import logger


class DatabaseConfig:
    """Database connection configuration"""
    
    def __init__(self, settings):
        """
        Initialize database config
        
        Args:
            settings: Settings instance
        """
        self.settings = settings
        self.connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """
        Build database connection string based on settings
        
        Returns:
            Connection string for the configured database
        """
        # SQLite (default for demo)
        if self.settings.USE_SQLITE_MEMORY:
            return "sqlite:///:memory:"
        
        # SAP HANA
        if self.settings.HANA_HOST:
            return self._build_hana_connection_string()
        
        # Default to SQLite file
        return "sqlite:///./sap_data.db"
    
    def _build_hana_connection_string(self) -> str:
        """Build SAP HANA connection string"""
        if not all([
            self.settings.HANA_HOST,
            self.settings.HANA_PORT,
            self.settings.HANA_USER,
            self.settings.HANA_PASSWORD
        ]):
            logger.warning("⚠️ Incomplete HANA credentials, falling back to SQLite")
            return "sqlite:///:memory:"
        
        return (
            f"hana://{self.settings.HANA_USER}:{self.settings.HANA_PASSWORD}"
            f"@{self.settings.HANA_HOST}:{self.settings.HANA_PORT}"
        )
    
    def get_connection_params(self) -> dict:
        """
        Get connection parameters as dict
        
        Returns:
            Dict of connection parameters
        """
        if self.settings.USE_SQLITE_MEMORY:
            return {
                "type": "sqlite",
                "database": ":memory:",
                "check_same_thread": False
            }
        
        if self.settings.HANA_HOST:
            return {
                "type": "hana",
                "address": self.settings.HANA_HOST,
                "port": self.settings.HANA_PORT,
                "user": self.settings.HANA_USER,
                "password": self.settings.HANA_PASSWORD,
                "database": self.settings.HANA_DATABASE
            }
        
        return {
            "type": "sqlite",
            "database": "./sap_data.db",
            "check_same_thread": False
        }


class RedisConfig:
    """Redis cache configuration"""
    
    def __init__(self, settings):
        """
        Initialize Redis config
        
        Args:
            settings: Settings instance
        """
        self.settings = settings
        self.enabled = settings.ENABLE_CACHE
        self.url = settings.REDIS_URL
        self.ttl = settings.CACHE_TTL_SECONDS
    
    def get_connection_params(self) -> dict:
        """
        Get Redis connection parameters
        
        Returns:
            Dict of connection parameters
        """
        return {
            "url": self.url,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
            "health_check_interval": 30
        }
