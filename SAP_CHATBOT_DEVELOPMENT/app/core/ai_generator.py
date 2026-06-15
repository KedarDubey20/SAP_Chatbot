"""
AI Generator - SQL generation and response formatting using AI
Combines SQL generation + response formatting in one place
"""
from typing import Dict, List, Optional, Any
from openai import AzureOpenAI
from loguru import logger
import json


class AIGenerator:
    """
    AI-powered SQL and response generation
    Uses Azure OpenAI GPT-4o-mini for:
    - SQL generation from natural language
    - Response formatting
    - Intent classification
    """
    
    def __init__(self, api_key: str, endpoint: str, deployment: str, api_version: str):
        """
        Initialize AI Generator
        
        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            deployment: Deployment name (e.g., gpt-4o-mini)
            api_version: API version
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.deployment = deployment
        logger.info(f"✓ AIGenerator initialized with {deployment}")
    
    # ============================================================
    # SQL GENERATION
    # ============================================================
    
    def generate_sql(
        self,
        query: str,
        schema: Dict[str, List[str]],
        conversation_context: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language query
        
        Args:
            query: Natural language query
            schema: Dict of table_name -> [columns]
            conversation_context: Optional conversation history
            
        Returns:
            Dict with: sql, explanation, confidence, tables_used
        """
        try:
            logger.info(f"🔮 Generating SQL for: {query}")
            
            # Build schema context
            schema_text = self._format_schema(schema)
            
            # Build system prompt
            system_prompt = f"""You are an expert SQL query generator for SAP data in SQLite.

Available tables and columns:
{schema_text}

IMPORTANT RULES:
1. Generate SQLite-compatible queries only
2. Column names are lowercase with underscores
3. Table names are lowercase with underscores
4. Always use LIMIT 5 unless user asks for more
5. Use proper JOINs when querying multiple tables
6. Return ONLY valid JSON with: sql, explanation, confidence, tables_used

Example output:
{{
    "sql": "SELECT * FROM vbak LIMIT 5",
    "explanation": "Retrieving first 5 sales orders",
    "confidence": "high",
    "tables_used": ["vbak"]
}}
"""
            
            # Call GPT
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate SQL for: {query}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"✓ SQL generated | Confidence: {result.get('confidence')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ SQL generation error: {e}")
            raise
    
    # ============================================================
    # RESPONSE FORMATTING
    # ============================================================
    
    def format_response(
        self,
        query: str,
        results: List[Dict],
        sql: Optional[str] = None
    ) -> str:
        """
        Format query results into natural language response
        
        Args:
            query: Original user query
            results: Query results
            sql: Optional SQL query for context
            
        Returns:
            Natural language response
        """
        try:
            if not results:
                return "No results found for your query."
            
            # Build context
            context = f"""User asked: {query}

Results: {len(results)} records found
Sample data (first 3 rows):
{json.dumps(results[:3], indent=2, default=str)}
"""
            
            if sql:
                context += f"\n\nSQL executed: {sql}"
            
            # Call GPT for formatting
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that formats database query results into clear, concise natural language responses."
                    },
                    {
                        "role": "user",
                        "content": f"{context}\n\nProvide a brief, natural language summary of these results."
                    }
                ],
                temperature=0.5,
                max_tokens=200
            )
            
            formatted = response.choices[0].message.content.strip()
            logger.info("✓ Response formatted")
            
            return formatted
            
        except Exception as e:
            logger.error(f"❌ Response formatting error: {e}")
            return f"Found {len(results)} results."
    
    # ============================================================
    # INTENT CLASSIFICATION
    # ============================================================
    
    def classify_intent(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Classify user query intent
        
        Args:
            query: User query
            conversation_history: Optional chat history
            
        Returns:
            Dict with: intent, confidence, entities
        """
        try:
            logger.info(f"🧠 Classifying intent: {query}")
            
            system_prompt = """Classify the user's query intent.

Return JSON with:
- "intent": greeting | help | data_query | explanation_request | general_question
- "confidence": high | medium | low
- "entities": dict of extracted entities

Intent definitions:
- greeting: Just saying hi/hello
- help: Asking what the system can do
- data_query: Requesting data from database
- explanation_request: Asking to explain previous results
- general_question: Other questions
"""
            
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-3:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            messages.append({"role": "user", "content": query})
            
            # Call GPT
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            # Parse result
            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"✓ Intent: {result.get('intent')} ({result.get('confidence')})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Intent classification error: {e}")
            return {
                'intent': 'data_query',
                'confidence': 'low',
                'entities': {}
            }
    
    # ============================================================
    # CONVERSATIONAL RESPONSE
    # ============================================================
    
    def generate_conversational_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        context_data: Optional[Dict] = None
    ) -> str:
        """
        Generate conversational response (for greetings, help, etc.)
        
        Args:
            query: User query
            conversation_history: Chat history
            context_data: Optional context (e.g., available tables)
            
        Returns:
            Conversational response
        """
        try:
            system_prompt = """You are a helpful SAP AI Assistant.

You help users query SAP sales data including:
- Sales orders (VBAK)
- Order items (VBAP)
- Schedule lines (VBEP)

Be friendly, concise, and helpful."""
            
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            if conversation_history:
                for msg in conversation_history[-5:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add context if provided
            if context_data:
                context_msg = f"\n\nAvailable data: {json.dumps(context_data, default=str)}"
                messages.append({"role": "system", "content": context_msg})
            
            messages.append({"role": "user", "content": query})
            
            # Call GPT
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            logger.info("✓ Conversational response generated")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Conversational response error: {e}")
            return "Hello! I'm here to help you query SAP data. What would you like to know?"
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    def _format_schema(self, schema: Dict[str, List[str]]) -> str:
        """Format schema for AI prompt"""
        lines = []
        for table, columns in schema.items():
            lines.append(f"\nTable: {table}")
            lines.append(f"Columns: {', '.join(columns[:20])}")
            if len(columns) > 20:
                lines.append(f"... and {len(columns) - 20} more")
        
        return "\n".join(lines)
