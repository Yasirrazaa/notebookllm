"""Tests for notebookllm.mcp.server — MCP server tools."""
import pytest
from notebookllm.mcp.server import create_app
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session_manager():
    return SessionManager()


@pytest.fixture
def app(session_manager):
    return create_app(session_manager)


class TestMCPServerTools:
    """Test MCP server tool functions directly (not via MCP protocol)."""

    def test_load_notebook(self, app, session_manager):
        from notebookllm.loaders import load_file
        doc = load_file(FIXTURES / "sample_percent.py")
        session_manager.store("test", doc)
        assert session_manager.get("test") is doc

    def test_session_lifecycle(self, session_manager):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        session_manager.store("s1", doc)
        assert len(session_manager.get("s1").cells) == 1
        session_manager.delete("s1")
        with pytest.raises(KeyError):
            session_manager.get("s1")


class TestMCPAppCreation:
    def test_create_app(self, session_manager):
        app = create_app(session_manager)
        assert app is not None
