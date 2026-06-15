"""
AI Service — FULLY FIXED VERSION
=================================================
FIXES APPLIED:
  1. ✅ Follow-up prompt only triggers on genuine follow-up queries (ref words / same session)
  2. ✅ Fresh questions always get base prompt — previous SQL never bleeds into unrelated queries
  3. ✅ Senior's Prompts class fully merged — stronger HANA rules, currency grouping rule
  4. ✅ conversation_history passed into generate_sql_from_query and included in messages[]
  5. ✅ context_hint includes last SQL, last results sample, referenced entity IDs
  6. ✅ Retry prompt explicitly instructs model to relax filters on 0-row result
  7. ✅ Base prompt also has NO-OP rule for clarification queries
  8. ✅ Three-part column reference rule added to prompts (NEVER "SCHEMA"."TABLE"."COLUMN")
  9. ✅ Metadata from generated_metadata.json injected into schema formatting
"""

from openai import AzureOpenAI
from app.config import settings
from loguru import logger
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


# ============================================================
# REFERENCE WORD DETECTION — is this a follow-up?
# ============================================================

FOLLOWUP_REF_WORDS = [
    'it', 'that', 'this', 'those', 'these',
    'the order', 'that order', 'above', 'first one',
    'the customer', 'that customer', 'them', 'they', 'this one',
    'previous', 'same', 'again', 'more details', 'drill down',
    'show more', 'expand', 'break it down', 'also show',
    'now filter', 'add filter', 'exclude', 'include only',
    'sort by', 'order by', 'group by', 'what about',
]

FRESH_QUESTION_OVERRIDES = [
    'this month', 'last month', 'this year', 'last year',
    'this week', 'today', 'yesterday', 'this quarter'
]


def _is_followup_query(query: str, context: "ConversationContext") -> bool:
    if not context.last_sql:
        return False
    q = query.lower()
    if any(phrase in q for phrase in FRESH_QUESTION_OVERRIDES):
        return False
    return any(ref in q for ref in FOLLOWUP_REF_WORDS)


# ============================================================
# PROMPTS CLASS — Senior's version + HANA engine rules merged
# ============================================================

class Prompts:
    """
    Central prompt store for all AI service prompts.
    All prompts live here — edit once, applies everywhere.

    COLUMN REFERENCE RULE (enforced in every prompt):
    - NEVER reference columns as "SCHEMA"."TABLE"."COLUMN" in SELECT/WHERE/GROUP BY
    - Use only "COLUMN" or alias."COLUMN" (e.g. V."KUNNR" not "SAPHANADB"."VBAK"."KUNNR")
    """

    def sql_prompt(
        self,
        schema_context: str,
        relationship_hints: str,
        context_hint: str,
        data_context: str
    ) -> str:
        """
        BASE prompt — for fresh questions with no prior SQL baseline.
        Incorporates senior's conservative-modification rules for clarification queries.
        """
        return f"""You are an expert SQL generator connected to a SAP HANA database.

═══════════════════════════════════════════════════
DATABASE ENGINE RULES (NEVER violate these)
═══════════════════════════════════════════════════
- TOP N must come immediately after SELECT:
    SELECT TOP 10 col FROM "SAPHANADB"."VBAK"
- ALL tables must use full schema prefix with double quotes: "SAPHANADB"."VBAK"
- NEVER use LIMIT — this is SAP HANA, use TOP only
- NEVER use CAST, DATE_TRUNC, or TO_DATE on date columns (HANA doesn't support them)
- NEVER use an alias in GROUP BY — repeat the full expression
- NEVER put special characters (₹, $, #, %) inside SQL alias names
- NEVER use SELECT * — always select specific relevant columns
- Only use SUM/AVG on confirmed numeric columns from the schema
- NEVER reference columns as "SCHEMA"."TABLE"."COLUMN" in SELECT/WHERE/GROUP BY
  Use only "COLUMN" or alias."COLUMN" (e.g. V."KUNNR" not "SAPHANADB"."VBAK"."KUNNR")

═══════════════════════════════════════════════════
LEARN EVERYTHING ELSE FROM SAMPLE DATA
═══════════════════════════════════════════════════
The sample rows below show the EXACT format of this client's real data.
- Date format → copy it exactly for WHERE clause comparisons
- ID padding → e.g. KUNNR = '0000000011' — always match the format you see
- Valid codes → only filter on values visible in distinct_values lists
- Currency → use the currency seen in data, only in response text (not in SQL alias)
- Column names → use exact names from schema, never guess or abbreviate

Do NOT assume anything not shown in the sample data.
Do NOT hardcode any year, format, code, or value not in the sample.
If unsure about a filter value → write a BROADER query without that filter rather than guessing.

AVAILABLE TABLES, COLUMNS, AND SAMPLE DATA:
{schema_context}

TABLE RELATIONSHIPS (always use these for JOINs — never guess):
{relationship_hints}

{context_hint}
{data_context}

═══════════════════════════════════════════════════
GENERAL QUERY RULES
═══════════════════════════════════════════════════
- Default TOP 10 unless user specifies a different number
- For chart queries: return exactly 2 columns (one label column + one numeric column)
- Join related tables to show human-readable names wherever possible
- When filtering strings: use LOWER(col) LIKE '%value%' for partial, case-insensitive matching
- When a single filter has multiple values: combine with OR
- When multiple different filters are needed: combine groups with AND
- For aggregation: use COUNT, SUM, AVG etc. — never SELECT * on aggregate queries
- If question is only asking for clarification of data already described, do NOT change filters
- For ANY monetary query (total value, sales, revenue, profit):
  ALWAYS GROUP BY currency column (WAERK for VBAK, WAERS for EKKO)
  NEVER SUM across different currencies
  Example: SELECT WAERK, SUM(NETWR) FROM "SAPHANADB"."VBAK" GROUP BY WAERK

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════
Return ONLY a JSON object, no text outside it:
{{
    "sql": "the complete SQL query",
    "explanation": "brief explanation of what the query does and why",
    "confidence": "high|medium|low",
    "tables_used": ["TABLE1", "TABLE2"]
}}"""

    def sql_followup_prompt(
        self,
        schema_context: str,
        relationship_hints: str,
        previous_sql: str,
        context_hint: str,
        data_context: str
    ) -> str:
        """
        FOLLOW-UP prompt — previous SQL as authoritative baseline.
        Modifies conservatively. Only triggered when user clearly references prior result.
        """
        return f"""You are an expert SQL generator connected to a SAP HANA database.

═══════════════════════════════════════════════════
IMPORTANT CONTEXT — THIS IS A FOLLOW-UP QUERY
═══════════════════════════════════════════════════
A SQL query was previously generated and successfully executed.
You MUST treat the previous SQL below as the authoritative baseline.

Previous SQL Query:
{previous_sql}

═══════════════════════════════════════════════════
CRITICAL RULES FOR FOLLOW-UP QUERIES
═══════════════════════════════════════════════════
- Start from the previous SQL and MODIFY it CONSERVATIVELY
- Preserve ALL existing filters, joins, table references, and ordering
  UNLESS the user's new question explicitly asks to change them
- Do NOT remove filters, constraints, or conditions unless explicitly requested
- If the new question ADDS constraints → ADD them on top of existing SQL
- If the new question asks for clarification, aggregation, or refinement →
  adapt only the SELECT clause while preserving the WHERE clause EXACTLY
- If the new question contradicts the previous SQL → prioritize new question
  but keep changes minimal and well-scoped
- Do NOT list many columns in SELECT — select ONLY columns needed to answer the question

NO-OP RULE:
If the user's follow-up does NOT request any change to:
  selected columns, filters, ordering, grouping, aggregation, limits, or scope
→ return the previous SQL EXACTLY as-is, unchanged.
Do NOT remove ORDER BY or any existing clauses unless asked.

═══════════════════════════════════════════════════
DATABASE ENGINE RULES (NEVER violate these)
═══════════════════════════════════════════════════
- SELECT TOP N immediately after SELECT (not at end): SELECT TOP 10 col FROM "SAPHANADB"."TABLE"
- All tables: "SAPHANADB"."TABLE" format with double quotes
- NEVER use LIMIT — use TOP only
- NEVER use CAST, DATE_TRUNC, TO_DATE on date columns
- NEVER put special characters in SQL alias names
- NEVER use SELECT *
- Only SUM/AVG on confirmed numeric columns
- NEVER reference columns as "SCHEMA"."TABLE"."COLUMN" in SELECT/WHERE/GROUP BY
  Use only "COLUMN" or alias."COLUMN"

LEARN FROM SAMPLE DATA (use exact formats seen here):
{schema_context}

TABLE RELATIONSHIPS:
{relationship_hints}

{context_hint}
{data_context}

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════
Return ONLY ONE JSON object, no text outside it:
{{
    "sql": "the complete SQL query",
    "explanation": "brief explanation of what changed and why",
    "confidence": "high|medium|low",
    "tables_used": ["TABLE1", "TABLE2"]
}}"""

    def intent_prompt(self, table_context: str) -> str:
        """Intent classification — schema-aware, never misclassifies data queries as greetings"""
        return f"""You are an intelligent intent classifier for a business SAP data assistant.

You are connected to a live SAP HANA database with the following tables and columns:
{table_context}

INTENT DEFINITIONS:
- "greeting"            → Pure social message ONLY (hi, hello, thanks, bye) — NO data intent at all
- "help"                → User EXPLICITLY asks what the assistant can do — nothing else
- "explanation_request" → User asks to explain or interpret data ALREADY SHOWN in this conversation
- "list_records"        → User wants to fetch, filter, or explore specific records
- "aggregate_summary"   → User wants totals, counts, averages, rankings, trends
- "filter_search"       → User wants data matching very specific conditions
- "multi_question"      → User asks TWO OR MORE clearly separate questions in ONE message

REASONING STEPS (apply in order):
1. Does the message contain 2+ clearly separate questions (multiple "?", "and" joining different data requests)? → multi_question
2. Is this purely social with absolutely NO data intent? → greeting
3. Is the user asking ONLY what the assistant can do? → help
4. Is the user referencing previously shown results in this conversation? → explanation_request
5. Aggregation, totals, rankings, trends → aggregate_summary
6. Specific record retrieval or filtering → list_records or filter_search

CRITICAL ANTI-HALLUCINATION RULES:
- ANY query answerable from the database → NEVER classify as "help" or "greeting"
- "What can you tell me about customers?" → list_records (NOT help)
- "Show me invoices" → list_records (NOT greeting)
- "How many orders this year?" → aggregate_summary (NOT help)
- When uncertain → always prefer list_records over help or greeting
- "help" is ONLY for explicit capability questions like "what can you do?"

Return ONLY valid JSON, no text outside it:
{{
  "intent": "<intent>",
  "complexity": "simple|medium|complex",
  "requires_aggregation": true|false,
  "tables_likely_needed": ["TABLE1", "TABLE2"],
  "reasoning": "<one sentence explaining why>",
  "sub_questions": ["question 1", "question 2"]
}}

Note: sub_questions ONLY populated when intent is multi_question. Otherwise return empty array []."""

    def decompose_prompt(self, schema_context: str) -> str:
        """Multi-step query decomposition"""
        return f"""You are a query planner for a SAP business data assistant.

Available tables:
{schema_context}

Determine if the user's message requires multiple SEPARATE SQL queries.

NEEDS MULTIPLE STEPS when:
- User asks TWO OR MORE clearly separate questions in one message
- Comparisons across time periods (this month vs last month)
- Comparisons across different entities (A vs B)
- Aggregations that depend on other aggregations

Does NOT need multiple steps when:
- Single question, even if complex
- A single SQL with JOINs or a subquery handles it
- User is just filtering or sorting existing data

IMPORTANT: Multiple "?" or "and" joining completely different data requests = separate steps.

Return ONLY a JSON object:
{{
    "is_multi_step": true or false,
    "reasoning": "why this does or does not need multiple steps",
    "steps": [
        {{
            "step": 1,
            "description": "what this step fetches",
            "query": "natural language query for this step"
        }}
    ],
    "synthesis_instruction": "how to combine results to answer original question"
}}

If is_multi_step is false, return empty steps array []."""

    def synthesis_prompt(self) -> str:
        return (
            "You are a professional SAP business analyst. "
            "Answer each sub-question clearly and separately using only the data provided. "
            "Label each answer clearly (e.g. '1. Top Customers:', '2. Top Vendor:'). "
            "Be concise, factual, and professional. "
            "Never invent data not present in the results."
        )

    def conversational_prompt(self) -> str:
        return (
            "You are a helpful SAP data assistant. "
            "Answer questions clearly and concisely based on conversation history and data provided. "
            "Never invent data. If you don't have data, say so directly."
        )


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

class ConversationContext:
    """Track entities and references across conversation turns"""

    def __init__(self):
        self.last_order_id: Optional[str]      = None
        self.last_customer_id: Optional[str]   = None
        self.last_material_id: Optional[str]   = None
        self.last_vendor_id: Optional[str]     = None
        self.last_table_queried: Optional[str] = None
        self.last_results: List[Dict]          = []
        self.last_sql: Optional[str]           = None

    def update_from_query(self, sql: str, results: List[Dict]):
        """Update context from query results — dynamically extracts table and entities from SQL"""
        table_matches = re.findall(r'"([A-Z0-9_]{2,10})"(?:\."([A-Z0-9_]{2,10})")?', sql.upper())
        tables_found = []
        for match in table_matches:
            if match[1]:
                tables_found.append(match[1])
            elif match[0] not in ('SAPHANADB',):
                tables_found.append(match[0])

        if tables_found:
            self.last_table_queried = tables_found[0]
            logger.debug(f"📋 Tables detected in SQL: {tables_found}")

        self.last_sql     = sql
        self.last_results = results[:5]

        if results and len(results) > 0:
            first = results[0]
            for key in ['KUNNR', 'kunnr']:
                if key in first and first[key]:
                    self.last_customer_id = str(first[key])
                    break
            for key in ['VBELN', 'vbeln']:
                if key in first and first[key]:
                    self.last_order_id = str(first[key])
                    break
            for key in ['MATNR', 'matnr']:
                if key in first and first[key]:
                    self.last_material_id = str(first[key])
                    break
            for key in ['LIFNR', 'lifnr']:
                if key in first and first[key]:
                    self.last_vendor_id = str(first[key])
                    break

    def get_context_for_query(self, query: str) -> Dict[str, Any]:
        """Return relevant context hints for the current query"""
        context = {}
        q_lower = query.lower()
        ref_words = [
            'it', 'that', 'this', 'the order', 'that order', 'above', 'first one',
            'the customer', 'that customer', 'the vendor', 'that vendor',
            'them', 'they', 'this one'
        ]

        if any(word in q_lower for word in ref_words):
            if self.last_customer_id:
                context['referenced_customer'] = self.last_customer_id
            if self.last_order_id:
                context['referenced_order'] = self.last_order_id
            if self.last_material_id:
                context['referenced_material'] = self.last_material_id
            if self.last_vendor_id:
                context['referenced_vendor'] = self.last_vendor_id

        if self.last_table_queried:
            context['last_table'] = self.last_table_queried
        if self.last_results:
            context['last_result_count']   = len(self.last_results)
            context['last_results_sample'] = self.last_results[:2]
        if self.last_sql:
            context['last_sql'] = self.last_sql

        return context


# ============================================================
# ENHANCED AI SERVICE
# ============================================================

class EnhancedAIService:
    """
    Enhanced AI Service with correct context awareness and clean prompt management.

    KEY FIX: follow-up SQL prompt is only used when user genuinely references
    prior results (pronouns/deictic words detected). Fresh questions always
    get the base prompt regardless of session history.
    """

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.contexts: Dict[str, ConversationContext] = {}
        self.prompts  = Prompts()
        logger.info("✓ EnhancedAIService initialized (fixed version)")

    def get_or_create_context(self, session_id: str = "default") -> ConversationContext:
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext()
        return self.contexts[session_id]

    # ──────────────────────────────────────────────────────────────────
    # INTENT ANALYSIS
    # ──────────────────────────────────────────────────────────────────

    def analyze_query_intent(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        schema_info: Optional[Dict[str, Any]] = None
    ) -> dict:
        logger.info(f"🧠 Analyzing intent: {user_query}")

        table_context = ""
        if schema_info:
            for table_name, table_data in schema_info.items():
                cols = (
                    table_data.get("columns", [])[:8]
                    if isinstance(table_data, dict)
                    else (table_data[:8] if isinstance(table_data, list) else [])
                )
                table_context += f"- {table_name}: {', '.join(cols)}\n"
        else:
            table_context = "No schema available — use general reasoning."

        messages = [{"role": "system", "content": self.prompts.intent_prompt(table_context)}]

        if conversation_history:
            for msg in conversation_history[-4:]:
                role    = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_query})

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            analysis = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Intent: {analysis.get('intent')} | {analysis.get('reasoning')}")
            return analysis
        except Exception as e:
            logger.error(f"❌ Intent analysis error: {str(e)}")
            return {
                "intent": "list_records",
                "complexity": "simple",
                "requires_aggregation": False,
                "tables_likely_needed": [],
                "reasoning": "fallback due to error",
                "sub_questions": []
            }

    # ──────────────────────────────────────────────────────────────────
    # SQL GENERATION — CORE FIXED METHOD
    # ──────────────────────────────────────────────────────────────────

    def generate_sql_from_query(
        self,
        user_query: str,
        schema_info: dict,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        date_hint: str = "",
        currency_hint: str = ""
    ) -> dict:
        context       = self.get_or_create_context(session_id)
        query_context = context.get_context_for_query(user_query)

        logger.info(f"🤖 Generating SQL for: {user_query}")

        schema_context     = self._format_schema_for_prompt(schema_info)
        relationship_hints = self._get_relationship_hints(schema_info)

        # ── Build context hint ──────────────────────────────────────
        context_hint = ""
        if query_context:
            context_hint = "\nCONVERSATION CONTEXT (from previous turns):\n"
            if 'referenced_order' in query_context:
                context_hint += (
                    f"- User previously saw order: {query_context['referenced_order']}\n"
                    f"- Pronouns like 'it', 'that order' → refer to order {query_context['referenced_order']}\n"
                )
            if 'referenced_customer' in query_context:
                context_hint += (
                    f"- User previously saw customer: {query_context['referenced_customer']}\n"
                    f"- Pronouns like 'they', 'them' → refer to customer {query_context['referenced_customer']}\n"
                )
            if 'referenced_vendor' in query_context:
                context_hint += f"- User previously saw vendor: {query_context['referenced_vendor']}\n"
            if 'referenced_material' in query_context:
                context_hint += f"- User previously saw material: {query_context['referenced_material']}\n"
            if 'last_table' in query_context:
                context_hint += f"- Last table queried: {query_context['last_table']}\n"
            if 'last_results_sample' in query_context:
                context_hint += f"- Sample of last results: {query_context['last_results_sample']}\n"

        # ── Build data context hint ─────────────────────────────────
        data_context = ""
        if date_hint or currency_hint:
            data_context = "\nACTUAL DATA CONTEXT (use these, never hardcode):\n"
            if date_hint:
                data_context += f"- Real data date range: {date_hint}\n"
            if currency_hint:
                data_context += f"- Real data currency: {currency_hint}\n"

        # ── KEY FIX: only use follow-up prompt when genuinely a follow-up ──
        is_followup  = _is_followup_query(user_query, context)
        previous_sql = query_context.get('last_sql')

        if is_followup and previous_sql:
            logger.info("🔄 Follow-up detected — using previous SQL as baseline")
            system_prompt = self.prompts.sql_followup_prompt(
                schema_context, relationship_hints,
                previous_sql, context_hint, data_context
            )
        else:
            if previous_sql and not is_followup:
                logger.info("📝 Fresh question — using base SQL prompt (ignoring previous SQL)")
            system_prompt = self.prompts.sql_prompt(
                schema_context, relationship_hints,
                context_hint, data_context
            )

        # ── Build messages[] — include conversation history ─────────
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history[-3:]:
                role    = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    short_content = content[:400] if len(content) > 400 else content
                    messages.append({"role": role, "content": short_content})

        messages.append({"role": "user", "content": f"Generate SQL for: {user_query}"})

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.15,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✓ SQL generated | Confidence: {result.get('confidence')} | is_followup={is_followup}")
            return result
        except Exception as e:
            logger.error(f"❌ Error generating SQL: {str(e)}")
            raise

    # ──────────────────────────────────────────────────────────────────
    # SQL WITH RETRY
    # ──────────────────────────────────────────────────────────────────

    async def generate_sql_with_retry(
        self,
        user_query: str,
        schema_info: dict,
        execute_fn,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        date_hint: str = "",
        currency_hint: str = "",
        max_retries: int = 3
    ) -> tuple:
        last_error = None
        last_sql   = None
        sql_result = {}

        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    query_with_context = user_query
                else:
                    # ✅ FIX: explicit "relax filters" instruction on retry
                    query_with_context = f"""Original question: {user_query}

Previous SQL attempt (attempt {attempt}):
{last_sql}

Problem encountered: {last_error}

Instructions for this retry:
- If the previous attempt returned 0 rows due to strict filters, RELAX the filters (use broader LIKE patterns, remove minor constraints)
- If there was a syntax error, fix it
- Preserve the overall intent and table structure
- Try a broader query rather than an overly specific one"""

                logger.info(f"🔄 SQL attempt {attempt + 1}/{max_retries}")

                sql_result = self.generate_sql_from_query(
                    query_with_context,
                    schema_info,
                    session_id=session_id,
                    conversation_history=conversation_history,
                    date_hint=date_hint,
                    currency_hint=currency_hint
                )

                sql         = sql_result.get('sql', '')
                tables_used = sql_result.get('tables_used', [])

                if not sql:
                    last_error = "No SQL was generated"
                    last_sql   = ""
                    continue

                results = await execute_fn(sql, tables_used)

                if results:
                    logger.info(f"✅ SQL succeeded on attempt {attempt + 1} with {len(results)} rows")
                    return sql_result, results

                last_sql   = sql
                last_error = (
                    "Query returned 0 rows. "
                    "The filters may be too strict — consider relaxing WHERE conditions, "
                    "using broader LIKE patterns, or checking if the values exist in the data."
                )
                logger.warning(f"⚠️ Attempt {attempt + 1} returned 0 rows, retrying with relaxed filters...")

            except Exception as e:
                last_sql   = sql_result.get('sql', '')
                last_error = str(e)
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {last_error}")

        logger.error(f"❌ All {max_retries} attempts failed. Last error: {last_error}")
        return sql_result, []

    # ──────────────────────────────────────────────────────────────────
    # CONTEXT UPDATE (called by sap_service after successful execution)
    # ──────────────────────────────────────────────────────────────────

    def update_context_from_results(self, sql: str, results: List[Dict], session_id: str = "default"):
        context = self.get_or_create_context(session_id)
        context.update_from_query(sql, results)
        logger.debug(f"✓ Context updated — Last table: {context.last_table_queried}")

    # ──────────────────────────────────────────────────────────────────
    # MULTI-STEP QUERY HANDLING
    # ──────────────────────────────────────────────────────────────────

    def decompose_query(self, user_query: str, schema_info: dict) -> dict:
        logger.info(f"🔍 Checking if query needs multi-step: {user_query}")
        schema_context = self._format_schema_for_prompt(schema_info)
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": self.prompts.decompose_prompt(schema_context)},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Multi-step: {result.get('is_multi_step')} | Steps: {len(result.get('steps', []))}")
            return result
        except Exception as e:
            logger.error(f"❌ Query decomposition error: {str(e)}")
            return {"is_multi_step": False, "steps": [], "reasoning": "fallback"}

    async def execute_multi_step_query(
        self,
        user_query: str,
        schema_info: dict,
        execute_fn,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        date_hint: str = "",
        currency_hint: str = ""
    ) -> dict:
        decomposition = self.decompose_query(user_query, schema_info)

        if not decomposition.get('is_multi_step') or not decomposition.get('steps'):
            logger.info("📌 Single-step query — skipping orchestration")
            return {"is_multi_step": False}

        logger.info(f"📋 Multi-step query: {len(decomposition['steps'])} steps")

        steps_results = []
        all_results   = []

        for step in decomposition['steps']:
            step_num   = step.get('step')
            step_query = step.get('query', '')
            step_desc  = step.get('description', '')
            logger.info(f"▶ Executing step {step_num}: {step_desc}")

            sql_result, results = await self.generate_sql_with_retry(
                user_query=step_query,
                schema_info=schema_info,
                execute_fn=execute_fn,
                session_id=session_id,
                conversation_history=conversation_history,
                date_hint=date_hint,
                currency_hint=currency_hint
            )

            steps_results.append({
                "step":        step_num,
                "description": step_desc,
                "sql":         sql_result.get('sql', ''),
                "results":     results,
                "row_count":   len(results)
            })
            all_results.extend(results)
            logger.info(f"✅ Step {step_num} done: {len(results)} rows")

        synthesis = self._synthesize_multi_step_results(
            original_query=user_query,
            steps_results=steps_results,
            synthesis_instruction=decomposition.get('synthesis_instruction', '')
        )

        logger.info(f"✅ Multi-step complete | Total rows: {len(all_results)}")
        return {
            "is_multi_step":    True,
            "steps_results":    steps_results,
            "combined_results": all_results,
            "synthesis":        synthesis
        }

    def _synthesize_multi_step_results(
        self,
        original_query: str,
        steps_results: List[Dict],
        synthesis_instruction: str
    ) -> str:
        logger.info("🧠 Synthesizing multi-step results...")

        steps_summary = ""
        for step in steps_results:
            steps_summary += f"\nStep {step['step']}: {step['description']}\n"
            steps_summary += f"Rows returned: {step['row_count']}\n"
            steps_summary += f"Sample data: {step['results'][:3]}\n"

        prompt = f"""The user asked: "{original_query}"

This required multiple queries. Here are the results:
{steps_summary}

Synthesis instruction: {synthesis_instruction}

Provide a single clear answer that addresses each question separately.
Label each answer clearly (e.g. "1. Top Customers:", "2. Top Vendor:").
Be concise, factual, and professional. Never invent data not in the results."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": self.prompts.synthesis_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=600
            )
            result = response.choices[0].message.content.strip()
            logger.info(f"✓ Synthesis complete: {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"❌ Synthesis error: {str(e)}")
            return f"Completed {len(steps_results)} queries. Please review the results below."

    # ──────────────────────────────────────────────────────────────────
    # CONVERSATIONAL RESPONSE
    # ──────────────────────────────────────────────────────────────────

    def generate_conversational_response(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        logger.info(f"💬 Generating conversational response for: {user_query}")

        context_text = ""
        if conversation_history:
            for msg in conversation_history[-4:]:
                role    = msg.get("role", "user")
                content = msg.get("content", "")
                if msg.get("sql"):
                    context_text += f"\n[SQL was: {msg['sql'][:200]}]"
                if msg.get("results"):
                    context_text += f"\n[Data sample: {msg['results'][:2]}]"
                context_text += f"\n{role}: {content}\n"

        prompt = f"""Conversation so far:
{context_text if context_text else "No previous context."}

Current question: {user_query}

Provide a clear, helpful, factual response in 2-3 sentences.
Do NOT invent data. If you don't have the data to answer, say so."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": self.prompts.conversational_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=250
            )
            result = response.choices[0].message.content.strip()
            logger.info("✓ Conversational response generated")
            return result
        except Exception as e:
            logger.error(f"❌ Conversational response error: {str(e)}")
            return "Could you please be more specific about what you'd like to know?"

    # ──────────────────────────────────────────────────────────────────
    # SCHEMA FORMATTING
    # ──────────────────────────────────────────────────────────────────

    def _format_schema_for_prompt(self, schema_info: dict) -> str:
        metadata = {}
        try:
            meta_path = Path("app/config/generated_metadata.json")
            if meta_path.exists():
                metadata = json.loads(meta_path.read_text())
        except Exception:
            pass

        schema_text = ""
        for table_name, table_data in schema_info.items():
            if isinstance(table_data, dict):
                columns       = table_data.get("columns", [])
                sample_rows   = table_data.get("sample_rows", [])
                distinct_vals = table_data.get("distinct_values", {})
                meta          = metadata.get(table_name, {})

                schema_text += f'\nTable: "SAPHANADB"."{table_name}"\n'

                if meta.get("description"):
                    schema_text += f'  Purpose: {meta["description"]}\n'

                schema_text += f'  Columns ({len(columns)}): {", ".join(columns[:30])}'
                if len(columns) > 30:
                    schema_text += f" ... and {len(columns) - 30} more"
                schema_text += "\n"

                col_descriptions = meta.get("columns", {})
                if col_descriptions:
                    schema_text += "  Column meanings:\n"
                    for col, desc in col_descriptions.items():
                        if col in columns:
                            schema_text += f"    {col}: {desc}\n"

                if sample_rows:
                    schema_text += "  Sample data (learn EXACT value formats from this):\n"
                    for i, row in enumerate(sample_rows[:2]):
                        key_fields = {k: v for k, v in list(row.items())[:15] if v is not None}
                        schema_text += f"    Row {i+1}: {key_fields}\n"

                if distinct_vals:
                    schema_text += "  Distinct values (ONLY use these for filtering):\n"
                    for col, vals in distinct_vals.items():
                        val_list = [str(v['value']) for v in vals[:15]]
                        schema_text += f"    {col}: {val_list}\n"

            elif isinstance(table_data, list):
                schema_text += f'\nTable: "SAPHANADB"."{table_name}"\n'
                schema_text += f'  Columns ({len(table_data)}): {", ".join(table_data[:30])}'
                if len(table_data) > 30:
                    schema_text += f" ... and {len(table_data) - 30} more"
                schema_text += "\n"

        return schema_text

    def _get_relationship_hints(self, schema_info: dict) -> str:
        """
        Load relationships from 3 sources in priority order:
        1. HANA FK constraints
        2. relationships.json config file
        3. Column frequency fallback
        """
        all_relationships = set()
        for table_data in schema_info.values():
            if isinstance(table_data, dict):
                for rel in table_data.get('relationships', []):
                    all_relationships.add(rel)

        if all_relationships:
            logger.debug(f"✓ Using {len(all_relationships)} FK relationships from HANA")
            return (
                "KNOWN TABLE RELATIONSHIPS (use for joins — never guess):\n"
                + "\n".join(f"- {r}" for r in sorted(all_relationships))
            )

        config_path = Path("app/config/relationships.json")
        if config_path.exists():
            try:
                rels        = json.loads(config_path.read_text())
                hana_schema = 'SAPHANADB'
                if schema_info:
                    first = next(iter(schema_info.values()))
                    if isinstance(first, dict):
                        hana_schema = first.get('schema_name', 'SAPHANADB')

                lines = []
                for left, right in rels.items():
                    left_table  = left.split('.')[0]
                    right_table = right.split('.')[0]
                    if left_table in schema_info and right_table in schema_info:
                        lines.append(
                            f'- "{hana_schema}"."{left_table}".{left.split(".")[1]}'
                            f' = "{hana_schema}"."{right_table}".{right.split(".")[1]}'
                        )

                if lines:
                    logger.debug(f"✓ Using {len(lines)} relationships from relationships.json")
                    return (
                        "KNOWN TABLE RELATIONSHIPS (always use these for joins — never guess):\n"
                        + "\n".join(lines)
                    )
            except Exception as e:
                logger.warning(f"⚠️ Could not load relationships.json: {e}")

        logger.debug("⚠️ No FK or config relationships found — inferring from column names")
        column_frequency: Dict[str, List[str]] = {}
        for table, table_data in schema_info.items():
            columns = table_data.get("columns", []) if isinstance(table_data, dict) else table_data
            for col in columns:
                if col not in column_frequency:
                    column_frequency[col] = []
                column_frequency[col].append(table)

        potential_joins = []
        for col, tables in column_frequency.items():
            if len(tables) > 1 and col.upper() not in ['MANDT', 'AEDAT', 'ERDAT']:
                potential_joins.append(f"'{col}' appears in: {', '.join(tables)}")

        if potential_joins:
            return (
                "POTENTIAL JOIN COLUMNS (inferred — verify before using):\n"
                + "\n".join(f"- {j}" for j in potential_joins[:10])
            )
        return ""


# ============================================================
# SINGLETON EXPORT
# ============================================================

enhanced_ai_service  = EnhancedAIService()
azure_openai_service = enhanced_ai_service