# services/session_manager.py
import uuid
import json
import sqlite3
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure a simple file logger for session activities
logger = logging.getLogger('session_manager')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler('session_manager.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
                pdf_files TEXT,
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
        # Migration: add pdf_files column if it doesn't exist (for existing DBs)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN pdf_files TEXT")
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

    def get_session_logger(self, session_id: str) -> logging.Logger:
        """Return a logger that writes to a file inside the session directory.

        Each session gets its own ``session.log`` file located at
        ``./sessions/<session_id>/session.log``. The logger is created on first
        use and cached by the logging module, so subsequent calls return the
        same logger instance.
        """
        session_path = Path(f"./sessions/{session_id}")
        session_path.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"session_{session_id}")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.FileHandler(session_path / "session.log")
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def create_session(self, user_id: int = None) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, db_path, schema, chroma_path, pdf_files, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_id, None, None, None, None, now, now)
            )
        logger.info(f"Created new session {session_id} for user_id={user_id}")
        return session_id

    def get_session(self, session_id: str) -> dict:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT session_id, user_id, db_path, schema, chroma_path, pdf_files, created_at, last_accessed FROM sessions WHERE session_id = ?",
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
            "pdf_files": json.loads(row[5]) if row[5] else None,
            "created_at": row[6],
            "last_accessed": row[7]
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
        if "pdf_files" in data:
            fields.append("pdf_files = ?")
            values.append(json.dumps(data["pdf_files"]))
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
        # Delete session directory and all files in it (db.sqlite, schema.json, chroma, etc.)
        session_dir = Path(f"./sessions/{session_id}")
        if session_dir.exists():
            shutil.rmtree(session_dir)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM token_usage WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------
    def create_user(self, username: str, password_hash: str) -> int:
        """Create a new user and return its generated ID.

        SQLite connections opened via ``_get_conn`` are used as context
        managers, which close the connection without an explicit commit.
        The original implementation relied on the implicit commit
        behaviour of ``execute`` which does not persist the new row, causing
        the user record to disappear after the connection is closed.  As a
        result, a freshly‑registered user could not be retrieved during the
        subsequent login attempt, leading to the "Invalid credentials"
        error.

        The fix adds an explicit ``conn.commit()`` after the INSERT so the
        user is persisted correctly.
        """
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, now)
            )
            conn.commit()
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
        """Get all conversations from all sessions.
        
        ⚠️ DEPRECATED: This method returns conversations from ALL users without filtering.
        Use get_user_conversations(user_id) instead to ensure proper authorization.
        
        This method is kept for backward compatibility but should not be used in endpoints.
        """
        # This method should NOT be used - it returns all users' data!
        # Kept only for potential admin/debug purposes
        import warnings
        warnings.warn(
            "get_all_conversations() is deprecated and unsafe. Use get_user_conversations(user_id) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
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

    def delete_conversation(self, conv_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

    # ------------------------------------------------------------------
    # Session expiry and cleanup
    # ------------------------------------------------------------------
    def cleanup_expired_sessions(self, max_age_days: int = 30):
        """Delete sessions that haven't been accessed in max_age_days.
        
        This should be run periodically (e.g., daily) to clean up abandoned sessions.
        Removes both database records and session files.
        
        Args:
            max_age_days: Number of days after which inactive sessions are deleted
        """
        cutoff_date = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        
        with self._get_conn() as conn:
            # Find expired sessions
            rows = conn.execute(
                "SELECT session_id FROM sessions WHERE last_accessed < ?",
                (cutoff_date,)
            ).fetchall()
        
        # Delete each session and its files
        deleted_count = 0
        for (session_id,) in rows:
            try:
                self.delete_session(session_id)
                deleted_count += 1
                logger.info(f"Cleaned up expired session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_id}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Session cleanup completed: {deleted_count} expired sessions deleted")
        
        return deleted_count

    def invalidate_session(self, session_id: str):
        """Immediately invalidate a session (e.g., on logout).
        
        This completely removes the session and all its data.
        Use this when a user logs out to ensure the session cannot be reused.
        """
        try:
            self.delete_session(session_id)
            logger.info(f"Session invalidated: {session_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate session {session_id}: {e}")
            raise


session_manager = SessionManager()

# Global JSON log for all queries
QUERY_LOG_FILE = "query_log.json"

def log_query_entry(entry: dict):
    """Append a JSON entry to the global query log file.

    The file is created if it does not exist. Each entry is written on a new line
    to allow easy streaming and incremental parsing.
    """
    try:
        with open(QUERY_LOG_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f)
            f.write("\n")
    except Exception as e:
        # Fallback to logger if writing fails
        logger.error(f"Failed to write query log entry: {e}")
