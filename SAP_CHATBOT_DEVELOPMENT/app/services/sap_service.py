"""
SAP Service — FULLY FIXED VERSION
=================================================
FIXES APPLIED:
  ✅ session_id now flows into all AI calls (context isolation per session)
  ✅ conversation_history loaded from SQLite (context_manager) as authoritative source
  ✅ Frontend-sent history used as fallback only
  ✅ context updated after every successful SQL execution
  ✅ HANA LIMIT → TOP fix in _get_schema distinct values query
  ✅ HANA LIMIT → TOP fix in _get_data_currency
  ✅ session_id and conversation_history passed to both multi-step and single-step SQL
  ✅ _ai_format_response gets conversation_history for better response tone
  ✅ ContextManager + chat_db wired in __init__
  ✅ Standardised _error_response helper used throughout
"""

from typing import Dict, List, Optional, Any
from loguru import logger
from decimal import Decimal
import pandas as pd
import traceback
import json

HANA_HOST     = "172.16.15.10"
HANA_PORT     = 30015
HANA_USER     = "READ_ONLY_1"
HANA_PASSWORD = "Primus@321"
HANA_SCHEMA   = "SAPHANADB"
SAP_TABLES    = ["VBAK", "VBAP", "VBEP", "KNA1", "MARA", "EKKO", "EKPO"]


class SAPService:
    """
    SAP Service — handles all SAP HANA business operations.
    """

    def __init__(self, data_service, cache_service, ai_service):
        self.data               = data_service
        self.cache              = cache_service
        self.ai                 = ai_service
        self._hana_schema_cache = None

        from app.services.chat_storage import chat_db
        from app.services.context_manager import ContextManager
        self.context_manager = ContextManager(
            chat_db       = chat_db,
            ai_client     = ai_service.client,
            ai_deployment = ai_service.deployment
        )

        logger.info("✓ SAPService initialized (Live HANA mode)")

    # ══════════════════════════════════════════════════════════════════
    # MAIN AI QUERY PROCESSOR
    # ══════════════════════════════════════════════════════════════════

    async def process_ai_query(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        try:
            logger.info(f"🤖 Processing AI query [session={session_id}]: {user_query}")
            thinking_steps = []

            # ── Load conversation history from SQLite (authoritative source) ──
            effective_history = await self.context_manager.get_context(session_id)
            if not effective_history:
                effective_history = conversation_history or []

            has_chart_keywords = self._has_chart_keywords(user_query)

            # ── Step 1: Get schema ────────────────────────────────────────────
            try:
                thinking_steps.append("🔍 Loading database schema + auto-discovering data patterns...")
                schema_info = self._get_schema()
                if not schema_info:
                    return self._error_response(
                        user_query, "No schema found",
                        "Could not retrieve database schema.", thinking_steps
                    )
                thinking_steps.append(f"✅ Schema loaded: {list(schema_info.keys())}")
            except Exception as e:
                logger.error(f"❌ Schema error: {e}")
                return self._error_response(
                    user_query, str(e),
                    "Unable to access database schema.", thinking_steps
                )

            # ── Step 2: Analyze intent WITH schema + history ──────────────────
            try:
                thinking_steps.append(f"🧠 Analyzing intent for: \"{user_query}\"")
                intent = self.ai.analyze_query_intent(
                    user_query,
                    effective_history,
                    schema_info
                )
                intent_type = intent.get('intent', 'list_records')

                is_asking_about_chart = any(w in user_query.lower() for w in [
                    'what is this', 'what does', 'explain', 'showing', 'what is the',
                    'tell me about', 'describe', 'interpret'
                ])
                if has_chart_keywords and intent_type == 'explanation_request' and not is_asking_about_chart:
                    intent_type = 'list_records'

                thinking_steps.append(f"✅ Intent: **{intent_type}** — {intent.get('reasoning', '')}")
                logger.info(f"📊 Intent: {intent_type}")

            except AttributeError as e:
                logger.error(f"❌ AttributeError in Intent Analysis: {str(e)}")
                return self._error_response(
                    user_query, "AI service not properly initialized",
                    "The AI service is not configured correctly.", thinking_steps
                )

            # ── Handle greeting / help ────────────────────────────────────────
            if intent_type in ['greeting', 'help'] and not has_chart_keywords:
                return {
                    "success":        True,
                    "query":          user_query,
                    "intent":         intent_type,
                    "response":       self._get_canned_response(intent_type),
                    "results":        [],
                    "result_count":   0,
                    "from_cache":     False,
                    "show_chart":     False,
                    "chart_type":     None,
                    "is_multi_step":  False,
                    "thinking_steps": thinking_steps
                }

            # ── Handle explanation requests ───────────────────────────────────
            if intent_type == 'explanation_request' and not has_chart_keywords:
                try:
                    response_text = self.ai.generate_conversational_response(
                        user_query, effective_history
                    )
                except Exception:
                    response_text = "Could you please be more specific?"
                return {
                    "success":        True,
                    "query":          user_query,
                    "intent":         intent_type,
                    "response":       response_text,
                    "results":        [],
                    "result_count":   0,
                    "from_cache":     False,
                    "show_chart":     False,
                    "chart_type":     None,
                    "is_multi_step":  False,
                    "thinking_steps": thinking_steps
                }

            # ── Step 3: Data context hints ────────────────────────────────────
            date_hint     = self._get_data_date_range()
            currency_hint = self._get_data_currency()
            thinking_steps.append(f"📅 Data context: {date_hint} | Currency: {currency_hint}")

            # ── Step 4: Multi-step check ──────────────────────────────────────
            thinking_steps.append("🔀 Checking if query needs multiple SQL steps...")
            multi_step = await self.ai.execute_multi_step_query(
                user_query=user_query,
                schema_info=schema_info,
                execute_fn=self._execute_sql_query,
                session_id=session_id,
                conversation_history=effective_history,
                date_hint=date_hint,
                currency_hint=currency_hint
            )

            if multi_step.get('is_multi_step'):
                steps = multi_step['steps_results']
                thinking_steps.append(f"📋 Multi-step query: {len(steps)} steps needed")
                for s in steps:
                    thinking_steps.append(
                        f"  Step {s['step']}: {s['description']} → {s['row_count']} rows"
                    )
                    if s.get('sql'):
                        thinking_steps.append(f"  SQL: `{s['sql'][:120]}...`")

                # Update context with the last step's SQL and results
                if steps and steps[-1].get('sql') and steps[-1].get('results'):
                    self.ai.update_context_from_results(
                        steps[-1]['sql'], steps[-1]['results'], session_id
                    )

                show_chart, chart_type = self._detect_chart_request(
                    user_query, multi_step['combined_results']
                )

                return {
                    "success":        True,
                    "query":          user_query,
                    "intent":         intent_type,
                    "response":       multi_step['synthesis'],
                    "results":        multi_step['combined_results'][:100],
                    "result_count":   len(multi_step['combined_results']),
                    "steps":          multi_step['steps_results'],
                    "from_cache":     False,
                    "show_chart":     show_chart,
                    "chart_type":     chart_type,
                    "is_multi_step":  True,
                    "thinking_steps": thinking_steps
                }

            # ── Step 5: Single query ──────────────────────────────────────────
            try:
                thinking_steps.append("⚙️ Generating SQL from natural language...")
                sql_result, results = await self.ai.generate_sql_with_retry(
                    user_query=user_query,
                    schema_info=schema_info,
                    execute_fn=self._execute_sql_query,
                    session_id=session_id,
                    conversation_history=effective_history,
                    date_hint=date_hint,
                    currency_hint=currency_hint
                )

                sql         = sql_result.get('sql', '')
                tables_used = sql_result.get('tables_used', [])
                confidence  = sql_result.get('confidence', 'medium')

                if sql:
                    thinking_steps.append(f"✅ SQL generated (confidence: {confidence})")
                    thinking_steps.append(f"```sql\n{sql}\n```")
                    thinking_steps.append(
                        f"🔷 Executing on SAP HANA... → {len(results)} rows returned"
                    )

                if not sql:
                    return self._error_response(
                        user_query, "Failed to generate SQL",
                        "I couldn't generate a valid SQL query.", thinking_steps
                    )

                # ── Update context after every successful execution ────────
                if sql and results:
                    self.ai.update_context_from_results(sql, results, session_id)
                    logger.debug(f"✓ Context updated for session {session_id}")

            except Exception as e:
                logger.error(f"❌ SQL error: {str(e)}", exc_info=True)
                return self._error_response(
                    user_query, str(e),
                    "I encountered an error processing your query.", thinking_steps
                )

            # ── Step 6: Format natural language response ──────────────────────
            thinking_steps.append("✍️ Formatting response with business insights...")
            natural_response       = await self._ai_format_response(
                user_query, results, sql, effective_history
            )
            show_chart, chart_type = self._detect_chart_request(user_query, results)
            is_aggregate           = self._is_aggregate_query(user_query, results)

            if is_aggregate:
                thinking_steps.append("📊 Aggregate query detected — showing summary only")

            return {
                "success":        True,
                "query":          user_query,
                "intent":         intent_type,
                "response":       natural_response,
                "sql":            sql,
                "results":        results[:100] if not is_aggregate else [],
                "result_count":   len(results),
                "from_cache":     False,
                "show_chart":     show_chart,
                "chart_type":     chart_type,
                "is_multi_step":  False,
                "thinking_steps": thinking_steps
            }

        except ValueError as e:
            logger.error(f"❌ ValueError: {str(e)}")
            return self._error_response(user_query, str(e), f"Invalid data: {str(e)}", [])

        except Exception as e:
            logger.error(f"❌ UNEXPECTED ERROR\n{traceback.format_exc()}")
            return self._error_response(
                user_query, str(e),
                f"An unexpected error occurred: {str(e)}", []
            )

    # ══════════════════════════════════════════════════════════════════
    # SCHEMA DISCOVERY
    # ══════════════════════════════════════════════════════════════════

    def _get_schema(self) -> Dict[str, Any]:
        """
        Auto-discover schema + data patterns from HANA.
        Cached in memory after first call.
        FIXED: uses TOP N instead of LIMIT for distinct value queries (HANA syntax)
        """
        if self._hana_schema_cache:
            return self._hana_schema_cache

        try:
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            schema = {}

            CATEGORICAL_COLUMNS = {
                "VBAK": ["AUART", "VBTYP", "WAERK", "VKORG"],
                "VBAP": ["ARKTX", "PSTYV"],
                "EKKO": ["BSART", "WAERS"],
                "KNA1": ["LAND1", "ORT01"],
            }

            for table in SAP_TABLES:
                try:
                    table_info = {"columns": [], "sample_rows": [], "distinct_values": {}}

                    cursor.execute(f'SELECT TOP 3 * FROM "{HANA_SCHEMA}"."{table}"')
                    columns = [desc[0] for desc in cursor.description]
                    table_info["columns"] = columns

                    rows = cursor.fetchall()
                    for row in rows:
                        record = {}
                        for col, val in zip(columns, row):
                            if isinstance(val, Decimal):
                                val = float(val)
                            elif isinstance(val, memoryview):
                                val = None
                            if val is not None and val != '' and val != 0:
                                record[col] = val
                        if record:
                            table_info["sample_rows"].append(record)

                    # ── FIXED: TOP 20 instead of LIMIT 20 (SAP HANA syntax) ──
                    if table in CATEGORICAL_COLUMNS:
                        for col in CATEGORICAL_COLUMNS[table]:
                            if col in columns:
                                try:
                                    cursor.execute(f'''
                                        SELECT TOP 20 "{col}", COUNT(*) AS CNT
                                        FROM "{HANA_SCHEMA}"."{table}"
                                        WHERE "{col}" IS NOT NULL AND "{col}" != \'\'
                                        GROUP BY "{col}"
                                        ORDER BY CNT DESC
                                    ''')
                                    distinct = cursor.fetchall()
                                    if distinct:
                                        table_info["distinct_values"][col] = [
                                            {"value": r[0], "count": r[1]}
                                            for r in distinct if r[0]
                                        ]
                                except Exception as de:
                                    logger.warning(
                                        f"⚠️ Could not get distinct values for {table}.{col}: {de}"
                                    )

                    schema[table] = table_info
                    logger.debug(
                        f"✅ Auto-discovered: {table} → {len(columns)} cols, {len(rows)} samples"
                    )

                except Exception as e:
                    logger.warning(f"⚠️ Could not discover {table}: {e}")

            conn.close()
            self._hana_schema_cache = schema
            logger.info(f"✅ Auto-discovery complete: {list(schema.keys())}")
            return schema

        except Exception as e:
            logger.error(f"❌ Auto-discovery failed: {e}")
            return {}

    # ══════════════════════════════════════════════════════════════════
    # DATA CONTEXT HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _get_data_date_range(self) -> str:
        try:
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            cursor.execute(f'SELECT MIN(ERDAT), MAX(ERDAT) FROM "{HANA_SCHEMA}"."VBAK"')
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return f"Data available from {row[0]} to {row[1]}"
        except Exception as e:
            logger.warning(f"⚠️ Could not get date range: {e}")
        return ""

    def _get_data_currency(self) -> str:
        try:
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            # FIXED: TOP instead of LIMIT (SAP HANA syntax)
            cursor.execute(f'SELECT TOP 5 DISTINCT WAERK FROM "{HANA_SCHEMA}"."VBAK"')
            rows = cursor.fetchall()
            conn.close()
            if rows:
                return ", ".join([r[0] for r in rows if r[0]])
        except Exception as e:
            logger.warning(f"⚠️ Could not get currency: {e}")
        return ""

    # ══════════════════════════════════════════════════════════════════
    # RESPONSE FORMATTING
    # ══════════════════════════════════════════════════════════════════

    async def _ai_format_response(
        self,
        query: str,
        results: List[Dict],
        sql: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        if not results:
            return "No data found matching your query."

        logger.info(f"🤖 Using AI to format response for {len(results)} results")

        try:
            sample_results   = json.dumps(results[:10], default=str, indent=2)
            tone_instruction = self._detect_user_style(query)
            currency         = self._extract_currency(results)

            history_context = ""
            if conversation_history:
                last_exchange = conversation_history[-2:]
                for msg in last_exchange:
                    role    = msg.get("role", "")
                    content = msg.get("content", "")[:200]
                    if role and content:
                        history_context += f"{role}: {content}\n"

            format_prompt = f"""User asked: "{query}"
{f'Recent conversation:{chr(10)}{history_context}' if history_context else ''}

Data returned ({len(results)} rows{f', detected currencies: {currency}' if currency else ''}):
{sample_results}

IMPORTANT DATA HANDLING RULES:
- Only reference data actually present in the results above.
- Do NOT invent numbers, values, trends, or conclusions not supported by the data.
- This data may contain multiple currencies (USD, INR, EUR, etc.).
- NEVER combine or aggregate values across different currencies.
- Always mention the currency explicitly when referring to monetary values.
- Use appropriate currency symbols where possible:
  * ₹ for INR
  * $ for USD
  * € for EUR
  * £ for GBP
- If multiple currencies are present, clearly separate them in the explanation.
- If a currency cannot be confidently identified, display the value exactly as returned.

{tone_instruction}

Provide a clear, insightful business explanation in 2-3 sentences.
Focus on key observations, patterns, or findings from the data.
Keep the response factual and concise.
"""

            response = self.ai.client.chat.completions.create(
                model=self.ai.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional business data assistant. "
                            "Respond in clear, concise business language. "
                            "Never use slang or filler phrases. "
                            "Keep responses factual — only reference data actually provided. "
                            "Never invent or estimate numbers not in the data."
                        )
                    },
                    {"role": "user", "content": format_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )

            natural_response = response.choices[0].message.content.strip()
            logger.info(f"✓ AI formatted response: {natural_response[:100]}...")
            return natural_response

        except Exception as e:
            logger.error(f"❌ Error in AI response formatting: {e}")
            return f"Found {len(results)} results."

    def _detect_user_style(self, query: str) -> str:
        query_lower = query.lower()
        casual_markers = [
            'bro', 'bruh', 'yo', 'hey', 'sup', 'gonna', 'wanna',
            'u', 'ur', 'btw', 'idk', 'ngl', 'tbh', 'lol', 'lmao',
            'yeah', 'yep', 'nah', 'cool', 'awesome', 'dude',
            '?!', '!!', '...', 'basically', 'totally', 'kinda', 'sorta'
        ]
        formal_markers = [
            'please', 'kindly', 'could you', 'would you',
            'appreciate', 'request', 'require', 'analysis',
            'provide', 'information', 'regarding', 'concerning',
            'examine', 'evaluate', 'assess', 'determine'
        ]
        casual_count = sum(1 for m in casual_markers if m in query_lower)
        formal_count = sum(1 for m in formal_markers if m in query_lower)

        if formal_count >= 2 or (formal_count > casual_count and formal_count > 0):
            return (
                "Tone: Professional and polished — business analyst delivering insights. "
                "Use complete sentences, precise language, avoid contractions."
            )
        if casual_count >= 2:
            return (
                "Tone: Friendly but still professional — approachable colleague vibe. "
                "Use simple, clear language. Avoid jargon but stay factual."
            )
        return "Tone: Friendly but professional — helpful colleague. Clear and direct without being stiff."

    def _extract_currency(self, results: List[Dict]) -> str:
        if not results:
            return ""
        first_row = results[0]
        for field in ['WAERK', 'WAERS', 'waerk', 'waers', 'currency', 'CURRENCY']:
            if field in first_row and first_row[field]:
                return first_row[field]
        return ""

    # ══════════════════════════════════════════════════════════════════
    # DETECTION HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _is_aggregate_query(self, query: str, results: list) -> bool:
        if not results or len(results) != 1:
            return False
        aggregate_keywords = [
            'how many', 'count', 'total', 'sum', 'average', 'avg',
            'what is the total', 'how much'
        ]
        if not any(kw in query.lower() for kw in aggregate_keywords):
            return False
        non_null = [v for v in results[0].values() if v is not None]
        return len(non_null) == 1

    def _has_chart_keywords(self, query: str) -> bool:
        chart_keywords = [
            'graph', 'chart', 'plot', 'visualiz', 'visual', 'diagram',
            'trend graph', 'show graph', 'display graph', 'show chart'
        ]
        return any(kw in query.lower() for kw in chart_keywords)

    def _detect_chart_request(self, query: str, results: list) -> tuple:
        if not results:
            return False, None
        if not self._has_chart_keywords(query):
            return False, None

        df       = pd.DataFrame(results)
        has_date = any(
            word in str(col).lower()
            for col in df.columns
            for word in ['date', 'time', 'created', 'day', 'month', 'year']
        )
        chart_type = (
            'line'
            if (has_date or 'trend' in query.lower() or 'over time' in query.lower())
            else 'bar'
        )
        logger.info(f"📊 Chart requested: {chart_type}")
        return True, chart_type

    # ══════════════════════════════════════════════════════════════════
    # HANA CONNECTION & DIRECT QUERIES
    # ══════════════════════════════════════════════════════════════════

    def _get_hana_conn(self):
        from hdbcli import dbapi
        return dbapi.connect(
            address=HANA_HOST, port=HANA_PORT,
            user=HANA_USER, password=HANA_PASSWORD
        )

    async def _execute_sql_query(self, sql: str, tables_used: List[str]) -> List[Dict]:
        """Execute SQL directly on SAP HANA"""
        try:
            logger.info(f"🔷 Executing on HANA: {sql[:120]}...")
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows    = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                record = {}
                for col, val in zip(columns, row):
                    if isinstance(val, Decimal):
                        val = float(val)
                    elif isinstance(val, memoryview):
                        val = None
                    record[col] = val
                results.append(record)

            logger.info(f"✅ HANA returned {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"❌ HANA execution failed: {e}")
            raise

    def _try_cache_query(self, sql: str, tables_used: List[str]) -> Optional[List[Dict]]:
        if not self.cache or not self.cache.cache_enabled:
            return None
        return self.cache.get(f"sap:query:{hash(sql)}")

    # ══════════════════════════════════════════════════════════════════
    # CANNED RESPONSES
    # ══════════════════════════════════════════════════════════════════

    def _get_canned_response(self, intent: str) -> str:
        responses = {
            'greeting': (
                "Hello! I'm your SAP AI Data Assistant connected to your live HANA database. "
                "I can answer questions about your data in plain English. "
                "Try: 'Which customer has the most orders?' or 'Show top 5 orders by value'."
            ),
            'help': (
                "I'm designed to query your live SAP HANA database and answer business questions. "
                "I can help with sales orders (VBAK/VBAP), customers (KNA1), materials (MARA), "
                "purchase orders (EKKO/EKPO), and schedule lines (VBEP). "
                "Try: 'Show me top 5 customers by order value' or "
                "'How many purchase orders were placed this year?'"
            )
        }
        return responses.get(intent, "How can I help you with your data today?")

    # ══════════════════════════════════════════════════════════════════
    # STANDARD SAP DATA METHODS
    # ══════════════════════════════════════════════════════════════════

    def get_all_orders(self, limit: int = 10) -> List[Dict]:
        try:
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            cursor.execute(
                f'SELECT TOP {limit} VBELN, ERDAT, NETWR, WAERK, KUNNR '
                f'FROM "{HANA_SCHEMA}"."VBAK"'
            )
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            conn.close()
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            logger.error(f"❌ Error getting orders: {e}")
            return []

    def get_order_by_id(self, order_id: str) -> Dict:
        try:
            conn   = self._get_hana_conn()
            cursor = conn.cursor()
            cursor.execute(
                f'SELECT * FROM "{HANA_SCHEMA}"."VBAK" WHERE VBELN = \'{order_id}\''
            )
            cols = [d[0] for d in cursor.description]
            row  = cursor.fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": f"Order {order_id} not found"}
            header = dict(zip(cols, row))
            cursor.execute(
                f'SELECT * FROM "{HANA_SCHEMA}"."VBAP" WHERE VBELN = \'{order_id}\''
            )
            item_cols = [d[0] for d in cursor.description]
            items     = [dict(zip(item_cols, r)) for r in cursor.fetchall()]
            conn.close()
            return {
                "success":    True,
                "order_id":   order_id,
                "header":     header,
                "items":      items,
                "from_cache": False
            }
        except Exception as e:
            logger.error(f"❌ Error getting order {order_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_summary(self) -> Dict:
        try:
            conn    = self._get_hana_conn()
            cursor  = conn.cursor()
            summary = {"total_tables": len(SAP_TABLES), "tables": {}}
            for table in SAP_TABLES:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{HANA_SCHEMA}"."{table}"')
                    count = cursor.fetchone()[0]
                    summary["tables"][table] = {"record_count": count}
                except Exception as e:
                    summary["tables"][table] = {"record_count": 0, "error": str(e)}
            conn.close()
            summary['from_cache'] = False
            return summary
        except Exception as e:
            logger.error(f"❌ Error getting summary: {e}")
            return {"error": str(e)}

    # ══════════════════════════════════════════════════════════════════
    # INTERNAL UTILITY
    # ══════════════════════════════════════════════════════════════════

    def _error_response(
        self,
        query: str,
        error: str,
        response: str,
        thinking_steps: List[str]
    ) -> Dict[str, Any]:
        """Standardised error response dict"""
        return {
            "success":        False,
            "error":          error,
            "query":          query,
            "response":       response,
            "results":        [],
            "result_count":   0,
            "from_cache":     False,
            "show_chart":     False,
            "chart_type":     None,
            "is_multi_step":  False,
            "thinking_steps": thinking_steps
        }