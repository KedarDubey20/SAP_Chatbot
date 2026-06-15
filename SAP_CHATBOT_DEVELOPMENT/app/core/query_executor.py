"""
Query Executor - Execute queries with fallback mechanisms
Handles SQL execution with multiple fallback strategies
"""
from typing import Dict, List, Any, Optional
from loguru import logger
import duckdb


class QueryExecutor:
    """
    Robust query executor with multiple execution strategies
    """
    
    def __init__(self, data_service, cache_service=None):
        """
        Initialize query executor
        
        Args:
            data_service: DataService instance
            cache_service: Optional CacheService for cached data
        """
        self.data = data_service
        self.cache = cache_service
        
        logger.info("✓ QueryExecutor initialized")
    
    # ============================================================
    # MAIN EXECUTION
    # ============================================================
    
    def execute(
        self,
        sql: str,
        use_cache: bool = True,
        fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query with fallback strategies
        
        Strategy priority:
        1. Try DuckDB on cached data (fastest)
        2. Try SQLite direct (reliable)
        3. Try simple filter fallback (safe)
        
        Args:
            sql: SQL query to execute
            use_cache: Whether to try cached data first
            fallback: Whether to use fallback strategies
            
        Returns:
            Query results as list of dicts
        """
        try:
            logger.info(f"⚡ Executing: {sql[:100]}...")
            
            # Strategy 1: DuckDB on cached data (if available)
            if use_cache and self.cache and self.cache.cache_enabled:
                try:
                    results = self._execute_on_cached_data(sql)
                    logger.info(f"✓ Executed on cached data ({len(results)} rows)")
                    return results
                except Exception as e:
                    logger.warning(f"Cached execution failed: {e}")
            
            # Strategy 2: SQLite direct execution
            try:
                results = self.data.execute_sql(sql)
                logger.info(f"✓ Executed on SQLite ({len(results)} rows)")
                return results
            except Exception as e:
                logger.warning(f"SQLite execution failed: {e}")
                
                if not fallback:
                    raise
            
            # Strategy 3: Simple filter fallback
            if fallback:
                logger.info("⚠️ Using fallback execution")
                results = self._fallback_execution(sql)
                logger.info(f"✓ Fallback executed ({len(results)} rows)")
                return results
            
            raise Exception("All execution strategies failed")
            
        except Exception as e:
            logger.error(f"❌ Execution error: {e}")
            raise
    
    # ============================================================
    # DUCKDB ON CACHED DATA
    # ============================================================
    
    def _execute_on_cached_data(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute SQL using DuckDB on Redis cached data
        Fastest option when data is in cache
        """
        import pandas as pd
        import numpy as np
        
        # Extract table names from SQL
        tables = self._extract_table_names(sql)
        
        if not tables:
            raise ValueError("No tables found in SQL")
        
        # Load data from cache
        dataframes = {}
        for table in tables:
            cache_key = f"sap:table:{table.upper()}"
            data = self.cache.get(cache_key)
            
            if not data:
                raise ValueError(f"Table {table} not in cache")
            
            df = pd.DataFrame(data)
            # Clean NaN values
            df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
            dataframes[table] = df
        
        # Execute with DuckDB
        con = duckdb.connect(':memory:')
        
        # Register dataframes
        for table_name, df in dataframes.items():
            con.register(table_name, df)
        
        # Execute query
        result_df = con.execute(sql).fetchdf()
        result_df = result_df.replace({np.nan: None, np.inf: None, -np.inf: None})
        
        con.close()
        
        return result_df.to_dict('records')
    
    # ============================================================
    # FALLBACK EXECUTION
    # ============================================================
    
    def _fallback_execution(self, sql: str) -> List[Dict[str, Any]]:
        """
        Simple fallback: Basic filtering without complex SQL
        """
        import pandas as pd
        import numpy as np
        import re
        
        # Extract table name
        table_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if not table_match:
            raise ValueError("Cannot extract table from SQL")
        
        table = table_match.group(1).upper()
        
        # Get data from cache or SQLite
        if self.cache and self.cache.cache_enabled:
            cache_key = f"sap:table:{table}"
            data = self.cache.get(cache_key)
            if data:
                df = pd.DataFrame(data)
            else:
                # Fallback to SQLite
                results = self.data.execute_sql(f"SELECT * FROM {table.lower()} LIMIT 100")
                df = pd.DataFrame(results)
        else:
            results = self.data.execute_sql(f"SELECT * FROM {table.lower()} LIMIT 100")
            df = pd.DataFrame(results)
        
        # Extract LIMIT
        limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        limit = int(limit_match.group(1)) if limit_match else 5
        
        # Apply simple WHERE filter if present
        where_match = re.search(r'WHERE\s+(.+?)\s+(?:LIMIT|ORDER|$)', sql, re.IGNORECASE)
        if where_match:
            condition = where_match.group(1).strip()
            # Simple = filter only
            eq_match = re.search(r'(\w+)\s*=\s*(\d+|\'[^\']+\')', condition)
            if eq_match:
                col = eq_match.group(1)
                val = eq_match.group(2).strip("'")
                
                # Find matching column
                for actual_col in df.columns:
                    if actual_col.lower().replace(' ', '_') == col.lower():
                        # Type conversion
                        try:
                            if df[actual_col].dtype in ['int64', 'float64']:
                                val = float(val)
                        except:
                            pass
                        df = df[df[actual_col] == val]
                        break
        
        # Apply limit
        df = df.head(limit)
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        
        return df.to_dict('records')
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        import re
        
        # Find FROM and JOIN clauses
        from_pattern = r'FROM\s+(\w+)'
        join_pattern = r'JOIN\s+(\w+)'
        
        tables = []
        
        # FROM tables
        from_matches = re.findall(from_pattern, sql, re.IGNORECASE)
        tables.extend(from_matches)
        
        # JOIN tables
        join_matches = re.findall(join_pattern, sql, re.IGNORECASE)
        tables.extend(join_matches)
        
        # Return unique, lowercase
        return list(set([t.lower() for t in tables]))
