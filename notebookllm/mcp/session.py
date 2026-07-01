"""Session manager for MCP server — SQLite-backed persistent notebook sessions."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from notebookllm.models import NotebookDocument


@dataclass
class Session:
    """A single user session holding a notebook."""
    doc: NotebookDocument
    filepath: str | None = None
    kernel_manager: Any = None
    kernel_client: Any = None


def _get_db_path() -> Path:
    """Get the SQLite database path using XDG data directory."""
    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    db_dir = Path(xdg_data) / "notebookllm"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "sessions.db"


class SessionManager:
    """Manages notebook sessions for MCP connections.

    Sessions are persisted in SQLite (documents serialized via
    NotebookDocument.to_json / from_json) and cached in memory for
    fast access.  In-memory state (kernel_client, filepath) is NOT
    persisted to SQLite — only the NotebookDocument is.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._db_path = Path(db_path) if db_path else _get_db_path()
        self._cache: dict[str, Session] = {}
        self._init_db()
        self._load_from_db()

    # ------------------------------------------------------------------
    # DB lifecycle
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the sessions table if it doesn't exist."""
        with self._conn_ctx() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    notebook_id TEXT PRIMARY KEY,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    doc         TEXT NOT NULL,
                    metadata    TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

    # ------------------------------------------------------------------
    # Connection lifecycle — each call creates a new connection,
    # automatically commits on success, rolls back on error, and
    # always closes the connection.
    # ------------------------------------------------------------------

    @contextmanager
    def _conn_ctx(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_from_db(self) -> None:
        """Load all sessions from SQLite into in-memory cache."""
        with self._conn_ctx() as conn:
            rows = conn.execute(
                "SELECT notebook_id, doc, metadata FROM sessions ORDER BY updated_at ASC"
            ).fetchall()
        for row in rows:
            session_id = row["notebook_id"]
            try:
                doc = NotebookDocument.from_json(row["doc"])
            except Exception:
                continue  # skip corrupt entries
            meta = json.loads(row["metadata"])
            self._cache[session_id] = Session(
                doc=doc,
                filepath=meta.get("filepath"),
            )

    def _persist(self, session_id: str, session: Session) -> None:
        """Write a session to SQLite."""
        now = datetime.now(UTC).isoformat()
        doc_json = session.doc.to_json()
        meta = json.dumps({"filepath": session.filepath})
        with self._conn_ctx() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (notebook_id, created_at, updated_at, doc, metadata)
                VALUES (?, COALESCE((SELECT created_at FROM sessions WHERE notebook_id = ?), ?), ?, ?, ?)
                """,
                (session_id, session_id, now, now, doc_json, meta),
            )

    def _remove_from_db(self, session_id: str) -> None:
        """Delete a session from SQLite."""
        with self._conn_ctx() as conn:
            conn.execute("DELETE FROM sessions WHERE notebook_id = ?", (session_id,))

    # ------------------------------------------------------------------
    # Public API (unchanged interface)
    # ------------------------------------------------------------------

    def store(self, session_id: str, doc: NotebookDocument, filepath: str | None = None) -> None:
        """Store or replace a notebook session (persisted to SQLite)."""
        with self._lock:
            session = self._cache.get(session_id)
            if session is None:
                session = Session(doc=doc, filepath=filepath)
            else:
                session.doc = doc
                session.filepath = filepath
            self._cache[session_id] = session
            self._persist(session_id, session)

    def get(self, session_id: str) -> NotebookDocument:
        """Get notebook for a session. Raises KeyError if not found."""
        session = self.get_session(session_id)
        return session.doc

    def get_session(self, session_id: str) -> Session:
        """Get the full session object. Raises KeyError if not found."""
        with self._lock:
            if session_id not in self._cache:
                # Fallback: try loading from SQLite
                with self._conn_ctx() as conn:
                    row = conn.execute(
                        "SELECT doc, metadata FROM sessions WHERE notebook_id = ?",
                        (session_id,),
                    ).fetchone()
                if row is None:
                    raise KeyError(f"Session not found: {session_id}")
                try:
                    doc = NotebookDocument.from_json(row["doc"])
                except Exception as exc:
                    raise KeyError(f"Session not found: {session_id}") from exc
                meta = json.loads(row["metadata"])
                session = Session(doc=doc, filepath=meta.get("filepath"))
                self._cache[session_id] = session
            return self._cache[session_id]

    def get_filepath(self, session_id: str) -> str | None:
        """Get filepath for a session, or None if not set."""
        session = self.get_session(session_id)
        return session.filepath

    def delete(self, session_id: str) -> None:
        """Delete a session from memory and SQLite. Raises KeyError if not found."""
        with self._lock:
            if session_id not in self._cache:
                raise KeyError(f"Session not found: {session_id}")

            session = self._cache[session_id]
            # Shut down kernel if it exists
            if session.kernel_manager is not None:
                try:
                    session.kernel_manager.shutdown_kernel()
                except Exception:
                    pass

            del self._cache[session_id]
            self._remove_from_db(session_id)

    def list_sessions(self) -> list[str]:
        """List all session IDs (from cache, ordered by creation time)."""
        with self._lock:
            return list(self._cache.keys())
