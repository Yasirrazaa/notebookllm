"""Tests for notebookllm.mcp.session — session management."""

import pytest

from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument


@pytest.fixture
def manager(tmp_path):
    db_path = tmp_path / "test_sessions.db"
    return SessionManager(db_path=db_path)


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

    def test_get_filepath_nonexistent(self, manager):
        with pytest.raises(KeyError, match="Session not found"):
            manager.get_filepath("missing")


class TestSQLitePersistence:
    """Tests that sessions persist across SessionManager instances."""

    def test_survives_manager_recreation(self, tmp_path):
        db_path = tmp_path / "persist.db"
        m1 = SessionManager(db_path=db_path)
        doc1 = NotebookDocument()
        doc1.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        m1.store("s1", doc1, filepath="/tmp/test.ipynb")

        # Destroy m1, create m2 pointing at same DB
        del m1
        m2 = SessionManager(db_path=db_path)

        assert "s1" in m2.list_sessions()
        restored = m2.get("s1")
        assert restored.cells[0].source == "x = 1"

    def test_mutiple_sessions(self, tmp_path):
        db_path = tmp_path / "multi.db"
        m1 = SessionManager(db_path=db_path)
        for i in range(3):
            d = NotebookDocument()
            d.add_cell(Cell(cell_type=CellType.CODE, source=f"cell_{i}"))
            m1.store(f"s{i}", d)
        del m1

        m2 = SessionManager(db_path=db_path)
        assert len(m2.list_sessions()) == 3
        assert m2.get("s2").cells[0].source == "cell_2"
