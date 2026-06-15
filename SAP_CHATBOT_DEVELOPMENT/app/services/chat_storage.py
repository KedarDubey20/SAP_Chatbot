"""
Chat Storage Service — UPDATED
Added:
  - summary TEXT column to sessions table
  - summary_up_to INTEGER column to sessions table
  - save_summary() method
  - get_session() now returns summary fields
"""
import sqlite3
import json
import uuid
import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from loguru import logger


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatStorageService:
    """
    SQLite-backed storage for chat sessions and messages.
    Now includes rolling summary support for long conversations.
    """

    def __init__(self, db_path: str = "./chat_history.db"):
        self.db_path = db_path
        self._lock   = threading.Lock()
        self._init_db()
        logger.info(f"✓ ChatStorageService ready — db: {db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Create tables if they don't exist. Adds summary columns if missing."""
        with self._lock:
            with self._connect() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id     TEXT PRIMARY KEY,
                        title          TEXT NOT NULL DEFAULT 'New Chat',
                        summary        TEXT,
                        summary_up_to  INTEGER DEFAULT 0,
                        created_at     TEXT NOT NULL,
                        updated_at     TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id   TEXT    NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                        role         TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
                        content      TEXT    NOT NULL,
                        sql_query    TEXT,
                        results_json TEXT,
                        created_at   TEXT    NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_messages_session
                        ON messages(session_id, created_at);
                """)

                # ── Migrate existing DBs that don't have summary columns ──
                try:
                    conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
                    logger.info("✓ Migrated: added summary column")
                except Exception:
                    pass  # column already exists

                try:
                    conn.execute("ALTER TABLE sessions ADD COLUMN summary_up_to INTEGER DEFAULT 0")
                    logger.info("✓ Migrated: added summary_up_to column")
                except Exception:
                    pass  # column already exists

        logger.debug("✓ SQLite schema verified")

    # ══════════════════════════════════════════════════════════════════
    # SESSION CRUD
    # ══════════════════════════════════════════════════════════════════

    def create_session(
        self,
        title: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        now = _utcnow()
        t   = title or "New Chat"
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?,?,?,?)",
                    (sid, t, now, now)
                )
        logger.info(f"✓ Session created: {sid} — '{t}'")
        return {
            "session_id": sid, "title": t,
            "created_at": now, "updated_at": now,
            "summary": None, "summary_up_to": 0
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       COUNT(m.id) AS message_count
                FROM   sessions s
                LEFT JOIN messages m ON m.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_session_title(self, session_id: str, title: str) -> bool:
        now = _utcnow()
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE sessions SET title=?, updated_at=? WHERE session_id=?",
                    (title, now, session_id)
                )
        return cur.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM sessions WHERE session_id=?", (session_id,)
                )
        existed = cur.rowcount > 0
        if existed:
            logger.info(f"🗑️  Session deleted: {session_id}")
        return existed

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return row is not None

    # ══════════════════════════════════════════════════════════════════
    # SUMMARY — new methods
    # ══════════════════════════════════════════════════════════════════

    def save_summary(self, session_id: str, summary: str, up_to_message_count: int) -> bool:
        """
        Save rolling summary to the session.
        Called by ContextManager after generating a new summary.

        Args:
            session_id:           target session
            summary:              the generated summary text
            up_to_message_count:  total message count at time of generation
        """
        now = _utcnow()
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    UPDATE sessions
                    SET summary=?, summary_up_to=?, updated_at=?
                    WHERE session_id=?
                    """,
                    (summary, up_to_message_count, now, session_id)
                )
        success = cur.rowcount > 0
        if success:
            logger.debug(f"✓ Summary saved for session {session_id} (up to msg {up_to_message_count})")
        return success

    def get_summary(self, session_id: str) -> Optional[str]:
        """Return the current summary for a session, or None."""
        session = self.get_session(session_id)
        return session.get("summary") if session else None

    # ══════════════════════════════════════════════════════════════════
    # MESSAGE CRUD
    # ══════════════════════════════════════════════════════════════════

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sql_query: Optional[str] = None,
        results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not self.session_exists(session_id):
            self.create_session(session_id=session_id)

        now          = _utcnow()
        results_json = json.dumps(results, default=str) if results is not None else None

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO messages (session_id, role, content, sql_query, results_json, created_at)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (session_id, role, content, sql_query, results_json, now)
                )
                msg_id = cur.lastrowid
                conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE session_id=?",
                    (now, session_id)
                )

        return {
            "id":         msg_id,
            "session_id": session_id,
            "role":       role,
            "content":    content,
            "sql_query":  sql_query,
            "results":    results,
            "created_at": now,
        }

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, sql_query, results_json, created_at
                FROM   messages
                WHERE  session_id = ?
                ORDER  BY created_at ASC, id ASC
                LIMIT  ? OFFSET ?
                """,
                (session_id, limit, offset)
            ).fetchall()

        msgs = []
        for r in rows:
            m           = dict(r)
            m["results"] = json.loads(m.pop("results_json")) if m.get("results_json") else None
            msgs.append(m)
        return msgs

    def get_conversation_history(self, session_id: str, last_n: int = 20) -> List[Dict[str, str]]:
        """Return last N messages as [{role, content}] for AI service."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM   messages
                WHERE  session_id = ?
                ORDER  BY created_at DESC, id DESC
                LIMIT  ?
                """,
                (session_id, last_n)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ══════════════════════════════════════════════════════════════════
    # UTILITY
    # ══════════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {
            "db_path":  self.db_path,
            "sessions": session_count,
            "messages": message_count,
        }

chat_db = ChatStorageService()
