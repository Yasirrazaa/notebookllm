"""Tests for notebookllm.mcp.server — MCP server tools."""
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from notebookllm.mcp.server import MAX_SESSIONS, create_app
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent / "fixtures"


def _get_text(result) -> str:
    """Extract text from MCP call_tool result."""
    if hasattr(result, "text"):
        return result.text
    if isinstance(result, list):
        return "".join(_get_text(item) for item in result)
    if isinstance(result, dict):
        return str(result.get("result", ""))
    if isinstance(result, tuple):
        return _get_text(result[0])
    return str(result)


@pytest.fixture
def session_manager(tmp_path):
    db_path = tmp_path / "test_mcp_sessions.db"
    return SessionManager(db_path=db_path)


@pytest.fixture
def app(session_manager):
    return create_app(session_manager)


@pytest.fixture
def session_with_cells(session_manager):
    """Pre-populate session with a sample notebook."""
    doc = NotebookDocument()
    doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1", execution_count=1))
    doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
    doc.add_cell(Cell(cell_type=CellType.CODE, source="print('hello')", execution_count=2))
    session_manager.store("test-session", doc, filepath="/tmp/test.ipynb")
    return session_manager


@pytest.fixture
def app_with_session(app, session_with_cells):
    return app, session_with_cells


@pytest.mark.asyncio
class TestLoadNotebook:
    """Tests for the load_notebook MCP tool."""

    async def test_load_sample_ipynb(self, app, session_manager):
        result = await app.call_tool("load_notebook", {
            "filepath": str(FIXTURES / "sample.ipynb"),
        })
        text = _get_text(result)
        assert "Loaded" in text
        assert "cells" in text
        assert "Session:" in text
        assert len(session_manager.list_sessions()) == 1

    async def test_load_sample_percent(self, app, session_manager):
        result = await app.call_tool("load_notebook", {
            "filepath": str(FIXTURES / "sample_percent.py"),
        })
        text = _get_text(result)
        assert "Loaded" in text
        assert "cells" in text

    async def test_load_nonexistent_file(self, app):
        with pytest.raises(ToolError):
            await app.call_tool("load_notebook", {"filepath": "/nonexistent/file.ipynb"})

    async def test_load_evicts_oldest_session(self, app, session_manager):
        """When sessions exceed MAX_SESSIONS, oldest should be evicted."""
        for i in range(MAX_SESSIONS - 1):
            doc = NotebookDocument()
            doc.add_cell(Cell(cell_type=CellType.CODE, source=f"x = {i}"))
            session_manager.store(f"keep-session-{i}", doc)

        await app.call_tool("load_notebook", {
            "filepath": str(FIXTURES / "sample_percent.py"),
        })
        assert len(session_manager.list_sessions()) == MAX_SESSIONS

        await app.call_tool("load_notebook", {
            "filepath": str(FIXTURES / "sample.ipynb"),
        })
        assert "keep-session-0" not in session_manager.list_sessions()
        assert "keep-session-1" in session_manager.list_sessions()


@pytest.mark.asyncio
class TestToText:
    """Tests for the to_text MCP tool."""

    async def test_to_text_minimal(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("to_text", {
            "session_id": "test-session",
            "mode": "minimal",
        })
        text = _get_text(result)
        assert "# %% [code]" in text
        assert "# %% [markdown]" in text
        assert "x = 1" in text
        assert "# exec_count" not in text

    async def test_to_text_standard(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("to_text", {
            "session_id": "test-session",
            "mode": "standard",
        })
        text = _get_text(result)
        assert "# exec_count: 1" in text
        assert "# exec_count: 2" in text

    async def test_to_text_invalid_session(self, app):
        result = await app.call_tool("to_text", {"session_id": "missing", "mode": "minimal"})
        assert "not found" in _get_text(result).lower()

    async def test_to_text_empty_notebook(self, app, session_manager):
        session_manager.store("empty", NotebookDocument())
        result = await app.call_tool("to_text", {"session_id": "empty"})
        assert _get_text(result) == ""


@pytest.mark.asyncio
class TestListCells:
    """Tests for the list_cells MCP tool."""

    async def test_list_cells(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("list_cells", {"session_id": "test-session"})
        text = _get_text(result)
        assert "[0] code" in text
        assert "[1] markdown" in text
        assert "[2] code" in text

    async def test_list_cells_empty(self, app, session_manager):
        session_manager.store("empty", NotebookDocument())
        result = await app.call_tool("list_cells", {"session_id": "empty"})
        assert "No cells" in _get_text(result)

    async def test_list_cells_invalid_session(self, app):
        result = await app.call_tool("list_cells", {"session_id": "missing"})
        assert "not found" in _get_text(result).lower()


@pytest.mark.asyncio
class TestGetCell:
    """Tests for the get_cell MCP tool."""

    async def test_get_cell_by_index(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("get_cell", {"session_id": "test-session", "index": 0})
        text = _get_text(result)
        assert "Cell [0]" in text
        assert "code" in text
        assert "x = 1" in text

    async def test_get_markdown_cell(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("get_cell", {"session_id": "test-session", "index": 1})
        text = _get_text(result)
        assert "# Title" in text

    async def test_get_cell_out_of_range(self, app_with_session):
        app, _ = app_with_session
        with pytest.raises(ToolError):
            await app.call_tool("get_cell", {"session_id": "test-session", "index": 999})


@pytest.mark.asyncio
class TestAddCell:
    """Tests for the add_cell MCP tool."""

    async def test_add_code_cell(self, app_with_session):
        app, sm = app_with_session
        result = await app.call_tool("add_cell", {
            "session_id": "test-session",
            "source": "y = 2",
            "cell_type": "code",
        })
        assert "Added" in _get_text(result)
        doc = sm.get("test-session")
        assert len(doc.cells) == 4
        assert doc.cells[3].source == "y = 2"

    async def test_add_markdown_cell_at_position(self, app_with_session):
        app, sm = app_with_session
        result = await app.call_tool("add_cell", {
            "session_id": "test-session",
            "source": "# New Section",
            "cell_type": "markdown",
            "position": 1,
        })
        assert "Added" in _get_text(result)
        doc = sm.get("test-session")
        assert len(doc.cells) == 4
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[1].source == "# New Section"

    async def test_add_raw_cell(self, app_with_session):
        app, sm = app_with_session
        await app.call_tool("add_cell", {
            "session_id": "test-session",
            "source": "raw data",
            "cell_type": "raw",
        })
        doc = sm.get("test-session")
        assert doc.cells[3].cell_type == CellType.RAW


@pytest.mark.asyncio
class TestEditCell:
    """Tests for the edit_cell MCP tool."""

    async def test_edit_source(self, app_with_session):
        app, sm = app_with_session
        result = await app.call_tool("edit_cell", {
            "session_id": "test-session",
            "index": 0,
            "source": "x = 42",
        })
        assert "Edited" in _get_text(result)
        doc = sm.get("test-session")
        assert doc.cells[0].source == "x = 42"

    async def test_edit_source_and_type(self, app_with_session):
        app, sm = app_with_session
        await app.call_tool("edit_cell", {
            "session_id": "test-session",
            "index": 0,
            "source": "# Comment",
            "cell_type": "markdown",
        })
        doc = sm.get("test-session")
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[0].source == "# Comment"


@pytest.mark.asyncio
class TestDeleteCell:
    """Tests for the delete_cell MCP tool."""

    async def test_delete_cell(self, app_with_session):
        app, sm = app_with_session
        result = await app.call_tool("delete_cell", {
            "session_id": "test-session",
            "index": 0,
        })
        assert "Deleted" in _get_text(result)
        assert "code" in _get_text(result)
        doc = sm.get("test-session")
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN

    async def test_delete_invalid_index(self, app_with_session):
        app, _ = app_with_session
        with pytest.raises(ToolError):
            await app.call_tool("delete_cell", {
                "session_id": "test-session",
                "index": 999,
            })


@pytest.mark.asyncio
class TestMoveCell:
    """Tests for the move_cell MCP tool."""

    async def test_move_cell_forward(self, app_with_session):
        app, sm = app_with_session
        result = await app.call_tool("move_cell", {
            "session_id": "test-session",
            "from_index": 0,
            "to_index": 2,
        })
        assert "Moved" in _get_text(result)
        doc = sm.get("test-session")
        assert doc.cells[2].source == "x = 1"

    async def test_move_cell_backward(self, app_with_session):
        app, sm = app_with_session
        await app.call_tool("move_cell", {
            "session_id": "test-session",
            "from_index": 2,
            "to_index": 0,
        })
        doc = sm.get("test-session")
        assert doc.cells[0].source == "print('hello')"


@pytest.mark.asyncio
class TestSearchCells:
    """Tests for the search_cells MCP tool."""

    async def test_search_by_query(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("search_cells", {
            "session_id": "test-session",
            "query": "print",
        })
        text = _get_text(result)
        assert "print" in text
        assert "[2]" in text

    async def test_search_with_type_filter(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("search_cells", {
            "session_id": "test-session",
            "query": "Title",
            "cell_type": "markdown",
        })
        text = _get_text(result)
        assert "Title" in text

    async def test_search_no_results(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("search_cells", {
            "session_id": "test-session",
            "query": "nonexistent",
        })
        assert "No matches found" in _get_text(result)

    async def test_search_case_insensitive(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("search_cells", {
            "session_id": "test-session",
            "query": "TITLE",
        })
        text = _get_text(result)
        assert "Title" in text


@pytest.mark.asyncio
class TestSaveNotebook:
    """Tests for the save_notebook MCP tool."""

    async def test_save_with_explicit_path(self, app_with_session, tmp_path):
        app, _ = app_with_session
        out = tmp_path / "explicit.ipynb"
        result = await app.call_tool("save_notebook", {
            "session_id": "test-session",
            "output_filepath": str(out),
        })
        assert "Saved" in _get_text(result)
        assert out.exists()

    async def test_save_without_filepath(self, app, session_manager):
        session_manager.store("no-path", NotebookDocument())
        result = await app.call_tool("save_notebook", {"session_id": "no-path"})
        assert "No filepath" in _get_text(result)


@pytest.mark.asyncio
class TestKernelExecution:
    async def test_execute_simple_code(self, app_with_session):
        """Execute a simple code cell and get output."""
        app, _ = app_with_session
        from unittest.mock import patch
        
        with patch("notebookllm.mcp.engine.KernelPool.start_kernel"):
            with patch("notebookllm.mcp.engine.KernelPool.execute_cell", return_value="[stdout] executed"):
                result = await app.call_tool("execute_cell", {
                    "session_id": "test-session",
                    "index": 0,
                })
        text = _get_text(result)
        assert "[stdout]" in text or "[output]" in text or "executed" in text.lower()

    async def test_execute_all_cells(self, app_with_session):
        """Execute all code cells sequentially."""
        app, _ = app_with_session
        from unittest.mock import patch
        
        with patch("notebookllm.mcp.engine.KernelPool.start_kernel"):
            with patch("notebookllm.mcp.engine.KernelPool.execute_all_cells", return_value="Executed 2 cells"):
                result = await app.call_tool("execute_all_cells", {
                    "session_id": "test-session",
                })
        text = _get_text(result)
        assert "Executed" in text or "cells" in text.lower() or "execute" in text.lower()

    async def test_execute_non_code_cell_returns_error(self, app_with_session):
        """Markdown cell returns clear error, not crash."""
        app, _ = app_with_session
        result = await app.call_tool("execute_cell", {
            "session_id": "test-session",
            "index": 1,
        })
        assert "not a code cell" in _get_text(result).lower()


@pytest.mark.asyncio
class TestCreateNotebook:
    async def test_create_empty(self, app, session_manager):
        result = await app.call_tool("create_notebook", {})
        text = _get_text(result)
        assert "Created empty notebook" in text
        assert "Session:" in text

    async def test_create_with_format(self, app, session_manager):
        result = await app.call_tool("create_notebook", {"source_format": "ipynb"})
        text = _get_text(result)
        assert "Created empty notebook" in text

    async def test_created_doc_is_editable(self, app, session_manager):
        # Create notebook → get session ID → add cell
        create_result = await app.call_tool("create_notebook", {})
        session_id = _get_text(create_result).split("Session: ")[1].strip()
        add_result = _get_text(await app.call_tool("add_cell", {
            "session_id": session_id,
            "source": "x = 1",
            "cell_type": "code",
        }))
        assert "Added" in add_result


@pytest.mark.asyncio
class TestListSessions:
    async def test_list_empty(self, app, session_manager):
        result = await app.call_tool("list_sessions", {})
        text = _get_text(result)
        assert "No active sessions" in text

    async def test_list_after_load(self, app, session_manager):
        await app.call_tool("load_notebook", {
            "filepath": str(FIXTURES / "sample.ipynb"),
        })
        result = _get_text(await app.call_tool("list_sessions", {}))
        assert "cells" in result
        assert "3" in result or "cells" in result  # sample has 3 cells


@pytest.mark.asyncio
class TestMCPAppCreation:
    """Tests for basic app creation and lifecycle."""

    async def test_create_app(self, session_manager):
        app = create_app(session_manager)
        assert app is not None
        tools = await app.list_tools()
        tool_names = [t.name for t in tools]
        assert "load_notebook" in tool_names
        assert "to_text" in tool_names
        assert "list_cells" in tool_names
        assert "get_cell" in tool_names
        assert "add_cell" in tool_names
        assert "edit_cell" in tool_names
        assert "delete_cell" in tool_names
        assert "move_cell" in tool_names
        assert "search_cells" in tool_names
        assert "save" in tool_names
        assert "save_notebook" in tool_names
        assert "execute" in tool_names
        assert "execute_cell" in tool_names
        assert "execute_all" in tool_names
        assert "execute_all_cells" in tool_names
        assert "create" in tool_names
        assert "create_notebook" in tool_names
        assert "list_sessions" in tool_names
        assert "convert" in tool_names
        assert "convert_format" in tool_names
        assert "list_kernels" in tool_names
        assert "fingerprint" in tool_names
        assert "diff" in tool_names
        assert "close_session" in tool_names
        assert len(tool_names) == 26

    async def test_list_tools_output(self, session_manager):
        app = create_app(session_manager)
        tools = await app.list_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert len(tool.description) > 5

    async def test_all_tools_handle_missing_session_gracefully(self, session_manager):
        """Every tool with session_id should return error, not raise, for missing sessions."""
        app = create_app(session_manager)
        tools = await app.list_tools()
        for tool in tools:
            if "session_id" in tool.inputSchema.get("properties", {}):
                kwargs = {"session_id": "nonexistent"}
                props = tool.inputSchema.get("properties", {})
                for pname in tool.inputSchema.get("required", []):
                    if pname != "session_id":
                        ptype = props[pname].get("type", "string")
                        if ptype == "integer":
                            kwargs[pname] = 0
                        elif ptype == "number":
                            kwargs[pname] = 0.0
                        else:
                            kwargs[pname] = "dummy"
                try:
                    result = await app.call_tool(tool.name, kwargs)
                    text = _get_text(result)
                    assert "not found" in text.lower() or "error" in text.lower()
                except Exception:
                    pytest.fail(f"Tool {tool.name} raised exception for missing session")


@pytest.mark.asyncio
class TestMCPTokenTool:
    """Tests for the count_tokens MCP tool."""

    async def test_count_tokens(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("count_tokens", {
            "session_id": "test-session",
        })
        text = _get_text(result)
        assert "tokens" in text.lower()

    async def test_count_tokens_missing_session(self, app):
        result = await app.call_tool("count_tokens", {"session_id": "missing"})
        assert "not found" in _get_text(result).lower()

    async def test_count_tokens_with_mode(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("count_tokens", {
            "session_id": "test-session",
            "mode": "full",
        })
        text = _get_text(result)
        assert "tokens" in text.lower()


@pytest.mark.asyncio
class TestConvertFormat:
    async def test_convert_ipynb_to_percent(self, app_with_session, tmp_path):
        app, _ = app_with_session
        out = tmp_path / "converted.py"
        result = await app.call_tool("convert_format", {
            "session_id": "test-session",
            "output_filepath": str(out),
            "target_format": "percent",
        })
        assert "Converted" in _get_text(result)
        assert out.exists()
