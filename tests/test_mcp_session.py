"""Tests for notebookllm.mcp.session — session management."""
import pytest
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument


@pytest.fixture
def manager():
    return SessionManager()


class TestSessionManager:
    def test_store_and_get(self, manager):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        manager.store("session-1", doc, filepath="/tmp/test.ipynb")
        result = manager.get("session-1")
        assert result is doc
        assert len(result.cells) == 1

    def test_get_nonexistent(self, manager):
        with pytest.raises(KeyError):
            manager.get("missing")

    def test_delete(self, manager):
        doc = NotebookDocument()
        manager.store("session-1", doc)
        manager.delete("session-1")
        with pytest.raises(KeyError):
            manager.get("session-1")

    def test_delete_nonexistent(self, manager):
        with pytest.raises(KeyError):
            manager.delete("missing")

    def test_list_sessions(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc)
        manager.store("s2", doc)
        sessions = manager.list_sessions()
        assert "s1" in sessions
        assert "s2" in sessions
        assert len(sessions) == 2

    def test_store_replaces_existing(self, manager):
        doc1 = NotebookDocument()
        doc1.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc2 = NotebookDocument()
        doc2.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        manager.store("s1", doc1)
        manager.store("s1", doc2)
        result = manager.get("s1")
        assert result.cells[0].source == "y = 2"

    def test_get_filepath(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc, filepath="/tmp/test.ipynb")
        assert manager.get_filepath("s1") == "/tmp/test.ipynb"

    def test_get_filepath_none(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc)
        assert manager.get_filepath("s1") is None
