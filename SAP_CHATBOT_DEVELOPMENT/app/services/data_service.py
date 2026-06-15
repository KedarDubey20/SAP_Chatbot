"""
Unified Data Service - Handles ALL data loading (FIXED VERSION)
✅ Comprehensive error logging
✅ Column name normalization (hyphens → underscores)
✅ Detailed error messages with suggestions
"""
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
import re

try:
    import openpyxl
    logger.info("✓ openpyxl available for Excel loading")
except ImportError:
    logger.warning("⚠️ openpyxl not installed - Excel loading will fail")


class DataService:
    """
    Unified service for loading and managing SAP data
    Supports: Excel, CSV, SQLite in-memory, Redis sync
    """
    
    def __init__(self, data_path: str, cache_service=None):
        """
        Initialize data service
        
        Args:
            data_path: Path to data files (Excel/CSV)
            cache_service: Optional CacheService for Redis sync
        """
        self.data_path = Path(data_path)
        self.cache = cache_service
        
        # SQLite in-memory database
        self.conn = sqlite3.connect(':memory:', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        self.tables_loaded = []
        logger.info("✓ DataService initialized")
    
    # ============================================================
    # LOAD DATA (Excel/CSV → SQLite)
    # ============================================================
    
    def load_sap_tables(self):
        """Load all SAP tables from Excel files"""
        table_files = {
            'VBAK': 'CSV Dump VBAK Header data .XLSX',
            'VBAP': 'CSV Dump VBAP Item Data.XLSX',
            'VBEP': 'CSV DUMP VBEP Schedule Line Data.XLSX'
        }
        
        for table_name, filename in table_files.items():
            filepath = self.data_path / filename
            if filepath.exists():
                try:
                    self.load_file(str(filepath), table_name)
                except Exception as e:
                    logger.error(f"❌ Failed to load {filename}: {e}")
            else:
                logger.warning(f"⚠️ File not found: {filepath}")
                logger.warning(f"   → Expected location: {self.data_path}")
                logger.warning(f"   → Filename: {filename}")
    
    def load_file(self, filepath: str, table_name: str):
        """
        Load a single file (Excel or CSV) into SQLite
        
        Args:
            filepath: Path to file
            table_name: Table name in database
        """
        try:
            logger.info(f"📂 Loading file: {filepath}")
            
            # Load data
            if filepath.lower().endswith('.csv'):
                try:
                    df = pd.read_csv(filepath)
                    logger.info(f"   ✓ CSV loaded: {len(df)} rows")
                except Exception as e:
                    logger.error(f"❌ CSV Loading Error")
                    logger.error(f"   File: {filepath}")
                    logger.error(f"   Error: {str(e)}")
                    logger.error(f"   → Check if file is valid CSV format")
                    raise
            else:
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    logger.info(f"   ✓ Excel loaded: {len(df)} rows, {len(df.columns)} columns")
                except Exception as e:
                    logger.error(f"❌ Excel Loading Error")
                    logger.error(f"   File: {filepath}")
                    logger.error(f"   Error: {str(e)}")
                    logger.error(f"   Error Type: {type(e).__name__}")
                    
                    if "openpyxl" in str(e).lower():
                        logger.error(f"   → openpyxl not installed or incompatible")
                        logger.error(f"   → Try: pip install openpyxl --upgrade")
                    elif "permission" in str(e).lower():
                        logger.error(f"   → File may be open in Excel")
                        logger.error(f"   → Close the file and try again")
                    else:
                        logger.error(f"   → File may be corrupted or invalid")
                    
                    raise
            
            # ✅ FIX: Clean column names (normalize hyphens, spaces, etc.)
            original_columns = df.columns.tolist()
            df.columns = self._clean_column_names(df.columns)
            
            logger.info(f"   ✓ Normalized {len(df.columns)} column names")
            logger.debug(f"   Sample columns: {df.columns.tolist()[:5]}")
            
            # Check for duplicate columns
            duplicates = df.columns[df.columns.duplicated()].tolist()
            if duplicates:
                logger.warning(f"   ⚠️ Found duplicate columns after normalization: {duplicates}")
            
            # Safe table name
            safe_name = self._safe_table_name(table_name)
            
            # Replace NaN with None for JSON compatibility
            df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
            
            # Load into SQLite
            try:
                df.to_sql(safe_name, self.conn, index=False, if_exists='replace')
                self.tables_loaded.append(safe_name)
                logger.info(f"   ✓ Loaded into SQLite as '{safe_name}'")
                
            except sqlite3.OperationalError as e:
                logger.error(f"❌ SQLite Operational Error")
                logger.error(f"   Table: {safe_name}")
                logger.error(f"   Error: {str(e)}")
                logger.error(f"   Columns: {df.columns.tolist()}")
                logger.error(f"   → Check for invalid column names or data types")
                raise
            
            # Sync to Redis if cache available
            if self.cache:
                try:
                    self._sync_to_redis(table_name, df)
                except Exception as e:
                    logger.warning(f"⚠️ Redis sync failed (continuing anyway): {e}")
            
        except FileNotFoundError as e:
            logger.error(f"❌ File Not Found")
            logger.error(f"   Path: {filepath}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   → Check if file exists and path is correct")
            raise
            
        except PermissionError as e:
            logger.error(f"❌ Permission Denied")
            logger.error(f"   Path: {filepath}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   → File may be open in another program")
            logger.error(f"   → Close Excel/other programs and try again")
            raise
            
        except Exception as e:
            logger.error(f"❌ UNEXPECTED Error Loading File")
            logger.error(f"   File: {filepath}")
            logger.error(f"   Table: {table_name}")
            logger.error(f"   Error Type: {type(e).__name__}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Stack Trace:", exc_info=True)
            raise
    
    # ============================================================
    # REDIS SYNC
    # ============================================================
    
    def _sync_to_redis(self, table_name: str, df: pd.DataFrame):
        """Sync table data to Redis cache"""
        try:
            # Store full table
            table_key = f"sap:table:{table_name}"
            table_data = df.to_dict('records')
            self.cache.set(table_key, table_data, ttl=0)
            
            # Store metadata (with ORIGINAL column names for display)
            meta_key = f"sap:meta:{table_name}"
            metadata = {
                'table_name': table_name,
                'record_count': len(df),
                'columns': list(df.columns)  # These are already normalized
            }
            self.cache.set(meta_key, metadata, ttl=0)
            
            # Index by order number for fast lookup
            if table_name == 'VBAK' and 'sales_document' in df.columns:
                for _, row in df.iterrows():
                    order_num = row.get('sales_document')
                    if pd.notna(order_num):
                        try:
                            key = f"sap:order:{int(order_num)}"
                            self.cache.set(key, row.to_dict(), ttl=0)
                        except (ValueError, TypeError):
                            logger.debug(f"Skipping invalid order number: {order_num}")
            
            logger.info(f"   ✓ Synced {table_name} to Redis")
            
        except Exception as e:
            logger.warning(f"⚠️ Redis sync failed for {table_name}: {e}")
            # Don't raise - Redis sync is optional
    
    def sync_all_to_redis(self):
        """Sync all loaded tables to Redis"""
        if not self.cache:
            logger.warning("⚠️ No cache service - skipping Redis sync")
            return
        
        from datetime import datetime
        
        logger.info("🔄 Syncing all tables to Redis...")
        
        for table in self.tables_loaded:
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", self.conn)
                table_upper = table.upper().replace('_', ' ')
                self._sync_to_redis(table_upper, df)
            except Exception as e:
                logger.error(f"❌ Failed to sync {table}: {e}")
        
        # Store sync metadata
        try:
            self.cache.set('sap:sync:metadata', {
                'last_sync': datetime.now().isoformat(),
                'tables': self.tables_loaded
            }, ttl=0)
        except Exception as e:
            logger.warning(f"⚠️ Failed to store sync metadata: {e}")
        
        logger.info("✅ Redis sync complete")
    
    # ============================================================
    # QUERY EXECUTION
    # ============================================================
    
    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute SQL query on SQLite database
        
        Args:
            sql: SQL query string
            
        Returns:
            List of dictionaries (results)
        """
        try:
            sql = sql.strip().rstrip(';')
            logger.info(f"Executing SQL: {sql[:100]}...")
            
            cursor = self.conn.cursor()
            cursor.execute(sql)
            
            if sql.lower().startswith('select'):
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
                
                # Clean NaN values
                for row in results:
                    for key, val in row.items():
                        if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                            row[key] = None
                
                logger.info(f"✓ Returned {len(results)} rows")
                return results
            else:
                self.conn.commit()
                affected = cursor.rowcount
                logger.info(f"✓ Modified {affected} rows")
                return [{"rows_affected": affected}]
        
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            
            logger.error(f"❌ SQLite Operational Error")
            logger.error(f"   SQL: {sql}")
            logger.error(f"   Error: {str(e)}")
            
            # Provide helpful suggestions based on error type
            if "no such table" in error_msg:
                # Extract table name
                match = re.search(r"no such table: (\w+)", error_msg)
                table_name = match.group(1) if match else "unknown"
                
                logger.error(f"   → Table '{table_name}' does not exist")
                logger.error(f"   → Available tables: {self.tables_loaded}")
                logger.error(f"   → Suggestion: Check if data files are loaded")
                logger.error(f"   → Suggestion: Verify table name spelling")
                
            elif "no such column" in error_msg:
                logger.error(f"   → Column does not exist in table")
                logger.error(f"   → Suggestion: Use get_schema_info() to see available columns")
                logger.error(f"   → Suggestion: Check column name spelling")
                
            elif "syntax error" in error_msg:
                logger.error(f"   → SQL syntax is invalid")
                logger.error(f"   → Suggestion: Verify SQL query structure")
                
            else:
                logger.error(f"   → Unknown operational error")
            
            raise
        
        except sqlite3.IntegrityError as e:
            logger.error(f"❌ SQLite Integrity Error")
            logger.error(f"   SQL: {sql}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   → Data constraint violated (e.g., duplicate key)")
            raise
        
        except sqlite3.ProgrammingError as e:
            logger.error(f"❌ SQLite Programming Error")
            logger.error(f"   SQL: {sql}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   → Database usage error (e.g., closed cursor)")
            raise
        
        except Exception as e:
            logger.error(f"❌ UNEXPECTED SQL Error")
            logger.error(f"   SQL: {sql}")
            logger.error(f"   Error Type: {type(e).__name__}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Stack Trace:", exc_info=True)
            raise
    
    def get_schema_info(self) -> Dict[str, List[str]]:
        """Get schema information for all tables"""
        try:
            schema = {}
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            if not tables:
                logger.warning("⚠️ No tables found in database")
                return schema
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = [col[1] for col in cursor.fetchall()]
                schema[table_name] = columns
                logger.debug(f"Schema for {table_name}: {len(columns)} columns")
            
            return schema
            
        except Exception as e:
            logger.error(f"❌ Error getting schema info: {e}")
            return {}
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    def _clean_column_names(self, columns) -> List[str]:
        """
        ✅ FIX: Clean column names for SQL compatibility
        Converts: "Sold-to Party" → "sold_to_party"
        """
        cleaned = (
            pd.Series(columns)
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(' ', '_', regex=False)
            .str.replace('.', '_', regex=False)
            .str.replace('/', '_', regex=False)
            .str.replace('-', '_', regex=False)  # ← CRITICAL FIX
            .str.replace('(', '', regex=False)
            .str.replace(')', '', regex=False)
            .str.replace('\'', '', regex=False)
            .str.replace('"', '', regex=False)
        )
        
        # Handle duplicates
        seen = {}
        final = []
        for col in cleaned:
            if col not in seen:
                seen[col] = 0
                final.append(col)
            else:
                seen[col] += 1
                final.append(f"{col}_{seen[col]}")
        
        return final
    
    def _safe_table_name(self, name: str) -> str:
        """Generate safe SQL table name"""
        return (
            name.strip()
            .lower()
            .replace(' ', '_')
            .replace('-', '_')
            .replace('.', '_')
        )
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")