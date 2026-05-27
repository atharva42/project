# services/session_manager.py
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path

SESSIONS_DB = "./sessions/sessions.db"

Path("./sessions").mkdir(exist_ok=True)


class SessionManager:
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(SESSIONS_DB)
        # users — user accounts for authentication
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT
            )
        """)
        # sessions — core session lifecycle
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                db_path TEXT,
                schema TEXT,
                chroma_path TEXT,
                created_at TEXT,
                last_accessed TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Migration: add user_id column if it doesn't exist (for existing DBs)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # token_usage — per-query token tracking linked to session
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                session_id TEXT,
                query_id TEXT,
                tokens_question INTEGER,
                tokens_response INTEGER,
                timestamp TEXT
            )
        """)
        # conversations — chat history linked to session
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                first_query TEXT,
                timestamp TEXT,
                messages TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        conn.commit()
        return conn

    def create_session(self, user_id: int = None) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, db_path, schema, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, None, None, now, now)
            )
        return session_id

    def get_session(self, session_id: str) -> dict:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT session_id, user_id, db_path, schema, chroma_path, created_at, last_accessed FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Session {session_id} not found")
            conn.execute(
                "UPDATE sessions SET last_accessed = ? WHERE session_id = ?",
                (datetime.now().isoformat(), session_id)
            )
        return {
            "session_id": row[0],
            "user_id": row[1],
            "db_path": row[2],
            "schema": json.loads(row[3]) if row[3] else None,
            "chroma_path": row[4],
            "created_at": row[5],
            "last_accessed": row[6]
        }

    def update_session(self, session_id: str, data: dict):
        fields = []
        values = []
        if "db_path" in data:
            fields.append("db_path = ?")
            values.append(data["db_path"])
        if "schema" in data:
            fields.append("schema = ?")
            values.append(json.dumps(data["schema"]))
        if "chroma_path" in data:
            fields.append("chroma_path = ?")
            values.append(data["chroma_path"])
        if not fields:
            return
        values.append(session_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?",
                values
            )

    def delete_session(self, session_id: str):
        session = self.get_session(session_id)
        if session["db_path"] and Path(session["db_path"]).exists():
            Path(session["db_path"]).unlink()
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM token_usage WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------
    def create_user(self, username: str, password_hash: str) -> int:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, now)
            )
            return cursor.lastrowid

    def get_user_by_username(self, username: str) -> dict:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "created_at": row[3]
            }

    def get_user_by_id(self, user_id: int) -> dict:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "created_at": row[3]
            }

    # ------------------------------------------------------------------
    # Token usage
    # ------------------------------------------------------------------
    def log_token_usage(self, session_id: str, query_id: str, tokens_question: int, tokens_response: int):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO token_usage (session_id, query_id, tokens_question, tokens_response, timestamp) VALUES (?,?,?,?,?)",
                (session_id, query_id, tokens_question, tokens_response, datetime.utcnow().isoformat())
            )

    def get_token_usage(self, session_id: str) -> list:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT query_id, tokens_question, tokens_response, timestamp FROM token_usage WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            ).fetchall()
        return [
            {"query_id": r[0], "tokens_question": r[1], "tokens_response": r[2], "timestamp": r[3]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Conversations  (Phase 1 frontend will use these)
    # ------------------------------------------------------------------
    def save_conversation(self, session_id: str, conv_id: str, first_query: str, messages: list):
        timestamp = datetime.now().strftime("%b %d, %I:%M %p")
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO conversations (id, session_id, first_query, timestamp, messages)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    messages = excluded.messages,
                    timestamp = excluded.timestamp
            """, (conv_id, session_id, first_query, timestamp, json.dumps(messages)))

    def get_conversations(self, session_id: str) -> list:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, first_query, timestamp, messages FROM conversations WHERE session_id = ? ORDER BY rowid DESC",
                (session_id,)
            ).fetchall()
        return [
            {"id": r[0], "first_query": r[1], "timestamp": r[2], "messages": json.loads(r[3]), "session_id": session_id}
            for r in rows
        ]

    def get_all_conversations(self) -> list:
        """Get all conversations from all sessions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT c.id, c.session_id, c.first_query, c.timestamp, c.messages FROM conversations c JOIN sessions s ON c.session_id = s.session_id ORDER BY c.rowid DESC"
            ).fetchall()
        return [
            {"id": r[0], "session_id": r[1], "first_query": r[2], "timestamp": r[3], "messages": json.loads(r[4])}
            for r in rows
        ]

    def get_user_conversations(self, user_id: int) -> list:
        """Get all conversations for a specific user."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT c.id, c.session_id, c.first_query, c.timestamp, c.messages FROM conversations c JOIN sessions s ON c.session_id = s.session_id WHERE s.user_id = ? ORDER BY c.rowid DESC",
                (user_id,)
            ).fetchall()
        return [
            {"id": r[0], "session_id": r[1], "first_query": r[2], "timestamp": r[3], "messages": json.loads(r[4])}
            for r in rows
        ]

    def delete_all_conversations(self, session_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))


session_manager = SessionManager()
