"""
Context Manager
=================================================
Handles conversation memory with sliding window + rolling summary.

STRATEGY:
  Messages 1-10  → passed in full to GPT (exact SQL, results, questions)
  Message 11+    → summary of old messages + last 3 full messages
  Message 21+    → updated summary (rolling) + last 3 full messages

SUMMARY CONTAINS:
  - What tables/data the user was analyzing
  - Key entity IDs seen (customer, vendor, order numbers)
  - What SQL was run and what it returned
  - Any patterns or insights found

SURVIVES REBOOTS:
  Summary is stored in SQLite sessions table.
  On reboot, history + summary loaded from DB instantly.
"""

from typing import Dict, List, Any, Optional
from loguru import logger

FULL_WINDOW   = 10   # keep last N messages in full before summarizing
RECENT_KEEP   = 3    # always keep last N messages in full after summary kicks in
SUMMARY_EVERY = 10   # regenerate summary every N new messages


class ContextManager:
    """
    Manages conversation context with sliding window + rolling summary.
    Works with ChatStorageService for persistence.
    """

    def __init__(self, chat_db, ai_client, ai_deployment: str):
        self.chat_db       = chat_db
        self.ai_client     = ai_client
        self.ai_deployment = ai_deployment

    # ══════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT — called by sap_service.process_ai_query
    # ══════════════════════════════════════════════════════════════════

    async def get_context(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Returns the right messages list to pass to GPT depending on
        how long the conversation is.

        Returns a list ready to be used as GPT messages[]:
          - Short conversation: full history as user/assistant messages
          - Long conversation:  system message with summary + last 3 messages

        Args:
            session_id: the active chat session

        Returns:
            List of message dicts [{role, content}, ...]
        """
        if session_id == "default":
            return []

        all_messages = self.chat_db.get_messages(session_id)
        count        = len(all_messages)

        logger.debug(f"📚 Session {session_id}: {count} messages total")

        # ── Case 1: Within full window — pass everything ──────────────
        if count <= FULL_WINDOW:
            return self._format_messages(all_messages)

        # ── Case 2: Beyond window — use summary + recent ──────────────
        session          = self.chat_db.get_session(session_id)
        existing_summary = session.get("summary") if session else None
        summary_up_to    = session.get("summary_up_to", 0) if session else 0

        # Regenerate summary if enough new messages have arrived
        needs_update = count > (summary_up_to + RECENT_KEEP)
        if needs_update or not existing_summary:
            old_messages = all_messages[:-RECENT_KEEP]
            logger.info(f"🧠 Generating summary for {len(old_messages)} old messages...")
            new_summary = await self._generate_summary(old_messages, existing_summary)
            self.chat_db.save_summary(session_id, new_summary, count)
            active_summary = new_summary
        else:
            active_summary = existing_summary

        # Always use last RECENT_KEEP messages in full
        recent_messages = all_messages[-RECENT_KEEP:]

        # Build final messages list:
        # [summary as system msg] + [last 3 full messages]
        result = []
        if active_summary:
            result.append({
                "role":    "system",
                "content": (
                    f"CONVERSATION SUMMARY (earlier messages in this session):\n"
                    f"{active_summary}\n\n"
                    f"Use this as background context. "
                    f"The user may reference entities or data from these earlier exchanges."
                )
            })

        result.extend(self._format_messages(recent_messages))
        logger.debug(f"📋 Context: 1 summary + {len(recent_messages)} recent messages")
        return result

    # ══════════════════════════════════════════════════════════════════
    # SUMMARY GENERATION
    # ══════════════════════════════════════════════════════════════════

    async def _generate_summary(
        self,
        old_messages: List[Dict],
        existing_summary: Optional[str]
    ) -> str:
        """
        Summarize old messages into a compact context block.
        Builds on top of existing summary if present (rolling).
        """
        conversation_text = ""
        for msg in old_messages:
            role    = msg.get("role", "")
            content = msg.get("content", "")[:300]   # truncate long responses
            sql     = msg.get("sql_query", "")

            conversation_text += f"{role.upper()}: {content}\n"
            if sql:
                conversation_text += f"[SQL: {sql[:200]}]\n"
            conversation_text += "\n"

        base = ""
        if existing_summary:
            base = f"Existing summary (build on this, don't repeat):\n{existing_summary}\n\n"

        prompt = f"""{base}New conversation messages to add to the summary:
{conversation_text}

Create a concise rolling summary that captures:
- What SAP data/tables the user was analyzing
- Key entity IDs mentioned (customer numbers, vendor numbers, order numbers, material numbers)
- What SQL queries were run and what they returned (row counts, key values)
- Any patterns, insights, or comparisons the user made
- What the user seems to be trying to understand overall

Rules:
- Maximum 250 words
- Keep specific IDs and numbers — they are critical for follow-up questions
- Write in past tense
- This will be injected as context for future GPT calls, so be precise"""

        try:
            response = self.ai_client.chat.completions.create(
                model=self.ai_deployment,
                messages=[
                    {
                        "role":    "system",
                        "content": (
                            "You are a conversation summarizer for a SAP data assistant. "
                            "Preserve key data entities, SQL context, and user intent precisely. "
                            "Be concise but complete."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )
            summary = response.choices[0].message.content.strip()
            logger.info(f"✅ Summary generated: {summary[:80]}...")
            return summary

        except Exception as e:
            logger.error(f"❌ Summary generation failed: {e}")
            # Fallback — simple text join
            lines = []
            for msg in old_messages[-5:]:
                lines.append(f"{msg.get('role')}: {msg.get('content', '')[:100]}")
            return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _format_messages(self, messages: List[Dict]) -> List[Dict[str, str]]:
        """Convert DB message rows to GPT-compatible {role, content} dicts."""
        result = []
        for msg in messages:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                result.append({"role": role, "content": content})
        return result