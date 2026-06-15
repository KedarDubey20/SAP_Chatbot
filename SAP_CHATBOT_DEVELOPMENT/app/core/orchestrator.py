"""
Orchestrator - Main business logic coordinator
Coordinates between AI, data, cache, and SAP services
"""
from typing import Dict, List, Optional, Any
from loguru import logger


class Orchestrator:
    """
    Central orchestrator for all business operations
    Coordinates AI, data loading, caching, and query execution
    """
    
    def __init__(
        self,
        ai_service,
        data_service,
        cache_service,
        schema_loader,
        auto_loader
    ):
        """
        Initialize orchestrator with all required services
        
        Args:
            ai_service: AzureOpenAIService instance
            data_service: DataService instance
            cache_service: CacheService instance
            schema_loader: SchemaLoaderService instance
            auto_loader: AutoLoaderService instance
        """
        self.ai = ai_service
        self.data = data_service
        self.cache = cache_service
        self.schema_loader = schema_loader
        self.auto_loader = auto_loader
        
        logger.info("✓ Orchestrator initialized")
    
    # ============================================================
    # MAIN QUERY ORCHESTRATION
    # ============================================================
    
    async def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Main orchestration flow for processing queries
        
        Flow:
        1. Analyze intent (AI)
        2. Check cache
        3. Generate SQL (AI)
        4. Execute query (Data)
        5. Cache result
        6. Format response (AI)
        
        Args:
            query: User's natural language query
            conversation_history: Previous messages
            
        Returns:
            Complete response dict
        """
        try:
            logger.info(f"🎯 Orchestrating query: {query}")
            
            # Step 1: Intent Analysis
            intent_result = self.ai.analyze_query_intent(
                query,
                conversation_history
            )
            intent = intent_result.get('intent', 'data_query')
            
            # Step 2: Handle conversational intents
            if intent in ['greeting', 'help', 'explanation_request']:
                response_text = self.ai.generate_conversational_response(
                    query,
                    conversation_history
                )
                
                return {
                    'success': True,
                    'query': query,
                    'intent': intent,
                    'response': response_text,
                    'is_conversational': True
                }
            
            # Step 3: Check cache for this query
            cache_key = f"query:{hash(query)}"
            if self.cache and self.cache.cache_enabled:
                cached = self.cache.get(cache_key)
                if cached:
                    logger.info("✓ Cache hit!")
                    cached['from_cache'] = True
                    return cached
            
            # Step 4: Get schema
            schema = self.schema_loader.export_schemas()
            
            # Step 5: Generate SQL
            sql_result = self.ai.generate_sql_from_query(
                query,
                schema['tables']
            )
            
            # Step 6: Execute SQL
            results = self.data.execute_sql(sql_result['sql'])
            
            # Step 7: Format response
            response = {
                'success': True,
                'query': query,
                'intent': intent,
                'response': f"Found {len(results)} results",
                'sql': sql_result['sql'],
                'results': results[:100],  # Limit
                'result_count': len(results),
                'from_cache': False,
                'is_conversational': False
            }
            
            # Step 8: Cache result
            if self.cache and self.cache.cache_enabled:
                self.cache.set(cache_key, response, ttl=3600)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Orchestration error: {e}")
            return {
                'success': False,
                'query': query,
                'error': str(e),
                'response': "I encountered an error processing your query."
            }
    
    # ============================================================
    # DATA ORCHESTRATION
    # ============================================================
    
    def orchestrate_data_load(self) -> Dict[str, Any]:
        """
        Orchestrate complete data loading process
        
        Flow:
        1. Discover schemas
        2. Auto-load data
        3. Sync to cache
        4. Return summary
        """
        try:
            logger.info("🔄 Orchestrating data load...")
            
            # Step 1: Discover schemas
            schemas = self.schema_loader.discover_all_schemas()
            logger.info(f"✓ Discovered {len(schemas)} schemas")
            
            # Step 2: Auto-load data
            load_summary = self.auto_loader.auto_load_all()
            logger.info(f"✓ Loaded {len(load_summary['loaded_tables'])} tables")
            
            # Step 3: Sync to cache
            if self.cache and self.cache.cache_enabled:
                self.data.sync_all_to_redis()
                logger.info("✓ Synced to Redis")
            
            return {
                'success': True,
                'schemas_discovered': len(schemas),
                'tables_loaded': len(load_summary['loaded_tables']),
                'summary': load_summary
            }
            
        except Exception as e:
            logger.error(f"❌ Data load orchestration error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ============================================================
    # CACHE ORCHESTRATION
    # ============================================================
    
    def orchestrate_cache_refresh(self) -> Dict[str, Any]:
        """
        Orchestrate complete cache refresh
        
        Flow:
        1. Clear existing cache
        2. Reload data
        3. Sync to cache
        """
        try:
            logger.info("🔄 Orchestrating cache refresh...")
            
            # Step 1: Clear cache
            if self.cache and self.cache.cache_enabled:
                self.cache.clear_pattern("sap:*")
                logger.info("✓ Cache cleared")
            
            # Step 2: Reload data
            load_result = self.auto_loader.force_reload_all()
            
            # Step 3: Sync to cache
            if self.cache and self.cache.cache_enabled:
                self.data.sync_all_to_redis()
                logger.info("✓ Re-synced to Redis")
            
            return {
                'success': True,
                'message': 'Cache refreshed successfully',
                'load_summary': load_result
            }
            
        except Exception as e:
            logger.error(f"❌ Cache refresh error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ============================================================
    # HEALTH ORCHESTRATION
    # ============================================================
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health status
        """
        try:
            return {
                'status': 'healthy',
                'components': {
                    'ai_service': 'connected' if self.ai else 'unavailable',
                    'data_service': 'connected' if self.data else 'unavailable',
                    'cache_service': 'connected' if self.cache and self.cache.cache_enabled else 'unavailable',
                    'schema_loader': 'connected' if self.schema_loader else 'unavailable',
                    'auto_loader': 'connected' if self.auto_loader else 'unavailable'
                },
                'tables_loaded': len(self.data.tables_loaded) if self.data else 0,
                'cache_enabled': self.cache.cache_enabled if self.cache else False
            }
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
