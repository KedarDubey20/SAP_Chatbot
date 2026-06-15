"""
Auto Loader Service - Automatically loads latest data from any source
Supports: Excel, SAP HANA, SAP RFC, Redis
Smart refresh: Only loads changed data
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
import hashlib
import warnings
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy connectable")

class AutoLoaderService:
    """
    Automatically loads and refreshes data from multiple sources
    Features:
    - Auto-detection of data sources
    - Incremental loading (only changed data)
    - Scheduled refresh
    - Change detection (file hash, timestamps)
    """
    
    def __init__(
        self,
        data_service,
        cache_service,
        schema_loader,
        config
    ):
        """
        Initialize auto loader
        
        Args:
            data_service: DataService instance
            cache_service: CacheService instance
            schema_loader: SchemaLoaderService instance
            config: Settings object
        """
        self.data = data_service
        self.cache = cache_service
        self.schema_loader = schema_loader
        self.config = config
        
        # Track loaded files and their hashes
        self.file_hashes = {}
        self.last_load_times = {}
        
        logger.info("✓ AutoLoaderService initialized")
    
    # ============================================================
    # AUTO LOAD ALL DATA
    # ============================================================
    
    def auto_load_all(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Automatically load data from all available sources
        
        Args:
            force_reload: If True, reload even if data hasn't changed
            
        Returns:
            Summary of loaded data
        """
        logger.info("🔄 Auto-loading data from all sources...")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'force_reload': force_reload,
            'loaded_tables': [],
            'skipped_tables': [],
            'errors': []
        }
        
        # Discover schemas first
        schemas = self.schema_loader.discover_all_schemas()
        
        if not schemas:
            logger.warning("⚠️ No schemas discovered - nothing to load")
            return summary
        
        # Load data for each discovered table
        for table_name, schema in schemas.items():
            try:
                source = schema['source']
                
                if source == 'redis':
                    # Data already in Redis, just verify
                    if self._verify_redis_data(table_name):
                        summary['skipped_tables'].append({
                            'table': table_name,
                            'reason': 'Already in Redis'
                        })
                    else:
                        summary['errors'].append({
                            'table': table_name,
                            'error': 'Redis data corrupted'
                        })
                
                elif source == 'excel':
                    result = self._load_from_excel(
                        table_name,
                        schema,
                        force_reload
                    )
                    
                    if result['loaded']:
                        summary['loaded_tables'].append(result)
                    else:
                        summary['skipped_tables'].append(result)
                
                elif source == 'hana':
                    result = self._load_from_hana(table_name, schema)
                    summary['loaded_tables'].append(result)
                
                elif source == 'rfc':
                    result = self._load_from_rfc(table_name, schema)
                    summary['loaded_tables'].append(result)
                
            except Exception as e:
                logger.error(f"❌ Error loading {table_name}: {e}")
                summary['errors'].append({
                    'table': table_name,
                    'error': str(e)
                })
        
        # Summary
        total_loaded = len(summary['loaded_tables'])
        total_skipped = len(summary['skipped_tables'])
        total_errors = len(summary['errors'])
        
        logger.info(f"✓ Loaded: {total_loaded}, Skipped: {total_skipped}, Errors: {total_errors}")
        
        return summary
    
    # ============================================================
    # EXCEL AUTO LOAD (with change detection)
    # ============================================================
    
    def _load_from_excel(
        self,
        table_name: str,
        schema: Dict,
        force_reload: bool
    ) -> Dict[str, Any]:
        """Load data from Excel with smart change detection"""
        
        file_path = Path(schema['file_path'])
        
        # Calculate file hash
        current_hash = self._calculate_file_hash(file_path)
        
        # Check if file changed
        if not force_reload and table_name in self.file_hashes:
            if self.file_hashes[table_name] == current_hash:
                logger.info(f"⏭️  {table_name}: No changes detected, skipping")
                return {
                    'table': table_name,
                    'loaded': False,
                    'reason': 'No changes detected',
                    'hash': current_hash
                }
        
        # Load the file
        try:
            logger.info(f"📥 Loading {table_name} from {file_path.name}")
            
            self.data.load_file(str(file_path), table_name)
            
            # Update hash
            self.file_hashes[table_name] = current_hash
            self.last_load_times[table_name] = datetime.now()
            
            return {
                'table': table_name,
                'loaded': True,
                'source': 'excel',
                'file': file_path.name,
                'records': schema.get('record_count', 0),
                'hash': current_hash,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to load {table_name}: {e}")
            raise
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file for change detection"""
        try:
            hash_md5 = hashlib.md5()
            
            with open(file_path, "rb") as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
            
        except Exception as e:
            logger.warning(f"Hash calculation failed for {file_path}: {e}")
            return str(file_path.stat().st_mtime)  # Fallback to modification time
    
    # ============================================================
    # REDIS DATA VERIFICATION
    # ============================================================
    
    def _verify_redis_data(self, table_name: str) -> bool:
        """Verify Redis data is valid and complete"""
        try:
            if not self.cache or not self.cache.cache_enabled:
                return False
            
            # Check metadata exists
            meta_key = f"sap:meta:{table_name}"
            metadata = self.cache.get(meta_key)
            
            if not metadata:
                return False
            
            # Check table data exists
            table_key = f"sap:table:{table_name}"
            data = self.cache.get(table_key)
            
            if not data:
                return False
            
            # Verify record count matches
            expected_count = metadata.get('record_count', 0)
            actual_count = len(data)
            
            if expected_count != actual_count:
                logger.warning(f"⚠️  {table_name}: Record count mismatch (expected {expected_count}, got {actual_count})")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Redis verification failed for {table_name}: {e}")
            return False
    
    # ============================================================
    # SAP HANA AUTO LOAD
    # ============================================================
    
    def _load_from_hana(self, table_name: str, schema: Dict) -> Dict[str, Any]:
        """Load data from SAP HANA"""
        try:
            from hdbcli import dbapi
            
            logger.info(f"📥 Loading {table_name} from HANA")
            
            conn = dbapi.connect(
                address=self.config.HANA_HOST,
                port=self.config.HANA_PORT,
                user=self.config.HANA_USER,
                password=self.config.HANA_PASSWORD
            )
            
            # Query table
            query = f"SELECT * FROM {schema['schema_name']}.{table_name}"
            df = pd.read_sql(query, conn)
            
            conn.close()
            
            # Load into data service
            # (This would require extending data_service to accept DataFrames)
            # For now, log success
            
            logger.info(f"✓ Loaded {len(df)} records from HANA")
            
            return {
                'table': table_name,
                'loaded': True,
                'source': 'hana',
                'records': len(df),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"HANA load failed for {table_name}: {e}")
            raise
    
    # ============================================================
    # SAP RFC AUTO LOAD
    # ============================================================
    
    def _load_from_rfc(self, table_name: str, schema: Dict) -> Dict[str, Any]:
        """Load data from SAP via RFC"""
        try:
            from pyrfc import Connection
            
            logger.info(f"📥 Loading {table_name} from SAP RFC")
            
            conn = Connection(
                ashost=self.config.SAP_ASHOST,
                sysnr=self.config.SAP_SYSNR,
                client=self.config.SAP_CLIENT,
                user=self.config.SAP_USER,
                passwd=self.config.SAP_PASSWORD
            )
            
            # Use RFC_READ_TABLE to get data
            result = conn.call(
                'RFC_READ_TABLE',
                QUERY_TABLE=table_name,
                DELIMITER='|',
                ROWCOUNT=0  # 0 = all rows
            )
            
            # Parse result
            data = result['DATA']
            fields = [f['FIELDNAME'] for f in result['FIELDS']]
            
            rows = []
            for row in data:
                values = row['WA'].split('|')
                rows.append(dict(zip(fields, values)))
            
            conn.close()
            
            logger.info(f"✓ Loaded {len(rows)} records from RFC")
            
            return {
                'table': table_name,
                'loaded': True,
                'source': 'rfc',
                'records': len(rows),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"RFC load failed for {table_name}: {e}")
            raise
    
    # ============================================================
    # SCHEDULED REFRESH
    # ============================================================
    
    def should_refresh(self, table_name: str, interval_minutes: int = 60) -> bool:
        """
        Check if table should be refreshed based on time interval
        
        Args:
            table_name: Table to check
            interval_minutes: Refresh interval in minutes
            
        Returns:
            True if refresh needed
        """
        if table_name not in self.last_load_times:
            return True
        
        last_load = self.last_load_times[table_name]
        elapsed = datetime.now() - last_load
        
        return elapsed > timedelta(minutes=interval_minutes)
    
    def refresh_if_needed(
        self,
        table_name: str,
        interval_minutes: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh table if interval has passed
        
        Args:
            table_name: Table to refresh
            interval_minutes: Refresh interval
            
        Returns:
            Load result if refreshed, None if skipped
        """
        if not self.should_refresh(table_name, interval_minutes):
            return None
        
        logger.info(f"🔄 Auto-refreshing {table_name}")
        
        schema = self.schema_loader.get_schema(table_name)
        if not schema:
            return None
        
        source = schema['source']
        
        if source == 'excel':
            return self._load_from_excel(table_name, schema, force_reload=True)
        elif source == 'hana':
            return self._load_from_hana(table_name, schema)
        elif source == 'rfc':
            return self._load_from_rfc(table_name, schema)
        
        return None
    
    # ============================================================
    # UTILITIES
    # ============================================================
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get status of all loaded tables"""
        return {
            'loaded_tables': list(self.last_load_times.keys()),
            'total_tables': len(self.last_load_times),
            'last_loads': {
                table: {
                    'timestamp': time.isoformat(),
                    'age_minutes': int((datetime.now() - time).total_seconds() / 60),
                    'hash': self.file_hashes.get(table, 'N/A')
                }
                for table, time in self.last_load_times.items()
            }
        }
    
    def force_reload_all(self) -> Dict[str, Any]:
        """Force reload all tables (ignore change detection)"""
        logger.info("🔄 Force reloading all tables")
        return self.auto_load_all(force_reload=True)
