"""Shared fixtures for notebookllm tests."""
from pathlib import Path

import pytest

from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session_manager(tmp_path):
    """Fresh SessionManager backed by a temporary SQLite database."""
    db_path = tmp_path / "test_sessions.db"
    return SessionManager(db_path=db_path)


@pytest.fixture
def sample_doc():
    """A 3-cell NotebookDocument (code, markdown, code) for general testing."""
    doc = NotebookDocument()
    doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1", execution_count=1))
    doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
    doc.add_cell(Cell(cell_type=CellType.CODE, source="print('hello')", execution_count=2))
    return doc
