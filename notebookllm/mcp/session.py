"""Session manager for MCP server — supports multi-user notebook editing."""
from __future__ import annotations

from dataclasses import dataclass

from notebookllm.models import NotebookDocument


@dataclass
class Session:
    """A single user session holding a notebook."""
    doc: NotebookDocument
    filepath: str | None = None


class SessionManager:
    """Manages notebook sessions for MCP connections."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def store(self, session_id: str, doc: NotebookDocument, filepath: str | None = None) -> None:
        """Store or replace a notebook session."""
        self._sessions[session_id] = Session(doc=doc, filepath=filepath)

    def get(self, session_id: str) -> NotebookDocument:
        """Get notebook for a session. Raises KeyError if not found."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self._sessions[session_id].doc

    def get_filepath(self, session_id: str) -> str | None:
        """Get filepath for a session, or None if not set."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self._sessions[session_id].filepath

    def delete(self, session_id: str) -> None:
        """Delete a session. Raises KeyError if not found."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        del self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return list(self._sessions.keys())
