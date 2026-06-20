"""MCP server for notebookllm — tools for notebook operations."""
from __future__ import annotations

import uuid
from typing import Any

from notebookllm.loaders import load_file, dump_file
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument, OutputMode

MAX_SESSIONS = 100


def create_app(session_manager: SessionManager | None = None):
    """Create and configure the MCP server app."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError("MCP server requires 'mcp[cli]'. Install with: pip install notebookllm[mcp]")

    if session_manager is None:
        session_manager = SessionManager()

    mcp = FastMCP("notebookllm")

    @mcp.tool()
    def load_notebook(filepath: str) -> str:
        """Load a notebook file into session."""
        session_id = str(uuid.uuid4())
        doc = load_file(filepath)
        session_manager.store(session_id, doc, filepath=filepath)
        # Evict oldest session if over limit
        sessions = session_manager.list_sessions()
        if len(sessions) > MAX_SESSIONS:
            oldest = sessions[0]
            session_manager.delete(oldest)
        return f"Loaded {len(doc.cells)} cells from {filepath}. Session: {session_id}"

    @mcp.tool()
    def save_notebook(session_id: str, output_filepath: str | None = None) -> str:
        """Save notebook to file."""
        doc = session_manager.get(session_id)
        filepath = output_filepath or session_manager.get_filepath(session_id)
        if not filepath:
            return "No filepath specified and none set in session."
        dump_file(doc, filepath)
        return f"Saved to {filepath}"

    @mcp.tool()
    def to_text(session_id: str, mode: str = "minimal") -> str:
        """Convert notebook to LLM-optimized text."""
        doc = session_manager.get(session_id)
        output_mode = OutputMode(mode)
        return doc.to_text(mode=output_mode)

    @mcp.tool()
    def list_cells(session_id: str) -> str:
        """List all cells with index, type, and preview."""
        doc = session_manager.get(session_id)
        lines = []
        for i, cell in enumerate(doc.cells):
            preview = cell.source[:60].replace("\n", " ")
            if len(cell.source) > 60:
                preview += "..."
            lines.append(f"[{i}] {cell.cell_type.value:10s} {preview}")
        return "\n".join(lines) if lines else "No cells."

    @mcp.tool()
    def get_cell(session_id: str, index: int) -> str:
        """Get a specific cell by index."""
        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        return f"Cell [{index}] ({cell.cell_type.value}):\n{cell.source}"

    @mcp.tool()
    def add_cell(session_id: str, source: str, cell_type: str = "code", position: int | None = None) -> str:
        """Add a new cell."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type)
        cell = Cell(cell_type=ct, source=source)
        doc.add_cell(cell, position=position)
        return f"Added {cell_type} cell at position {position or len(doc.cells) - 1}"

    @mcp.tool()
    def edit_cell(session_id: str, index: int, source: str, cell_type: str | None = None) -> str:
        """Edit an existing cell."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type) if cell_type else None
        doc.edit_cell(index, source=source, cell_type=ct)
        return f"Edited cell [{index}]"

    @mcp.tool()
    def delete_cell(session_id: str, index: int) -> str:
        """Delete a cell by index."""
        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        doc.delete_cell(index)
        return f"Deleted cell [{index}] ({cell.cell_type.value})"

    @mcp.tool()
    def move_cell(session_id: str, from_index: int, to_index: int) -> str:
        """Move a cell from one position to another."""
        doc = session_manager.get(session_id)
        doc.move_cell(from_index, to_index)
        return f"Moved cell from [{from_index}] to [{to_index}]"

    @mcp.tool()
    def search_cells(session_id: str, query: str, cell_type: str | None = None) -> str:
        """Search cells by content (case-insensitive)."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type) if cell_type else None
        results = doc.search(query, cell_type=ct)
        if not results:
            return "No matches found."
        lines = []
        for idx, cell in results:
            preview = cell.source[:60].replace("\n", " ")
            lines.append(f"[{idx}] {cell.cell_type.value:10s} {preview}")
        return "\n".join(lines)

    @mcp.tool()
    def execute_cell(session_id: str, index: int, timeout: int = 60) -> str:
        """Execute a code cell via Jupyter kernel (requires notebookllm[execute])."""
        try:
            import jupyter_client  # noqa: F401
        except ImportError:
            return "Error: notebookllm[execute] not installed. Run: pip install notebookllm[execute]"

        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        if cell.cell_type != CellType.CODE:
            return f"Cell [{index}] is not a code cell (it's {cell.cell_type.value})."

        # Execute via jupyter_client
        from jupyter_client import KernelManager

        km = KernelManager(kernel_name="python3")
        km.start_kernel()
        try:
            client = km.client()
            client.start_channels()
            msg_id = client.execute(cell.source)
            reply = client.get_shell_msg(timeout=timeout)
            if reply["content"]["status"] == "error":
                return f"Execution error: {reply['content']['evalue']}"

            # Collect outputs
            outputs = []
            while True:
                try:
                    msg = client.get_iopub_msg(timeout=5)
                    if msg["parent_header"].get("msg_id") == msg_id:
                        msg_type = msg["msg_type"]
                        content = msg["content"]
                        if msg_type == "stream":
                            outputs.append(f"[{content.get('name', 'stdout')}] {content.get('text', '')}")
                        elif msg_type == "execute_result":
                            data = content.get("data", {})
                            outputs.append(f"[output] {data.get('text/plain', '')}")
                        elif msg_type == "error":
                            outputs.append(f"[error] {content.get('evalue', '')}")
                        elif msg_type == "status" and content.get("execution_state") == "idle":
                            break
                except TimeoutError:
                    break

            return "\n".join(outputs) if outputs else "Cell executed (no output)."
        finally:
            km.shutdown_kernel()

    return mcp


def main(transport: str = "stdio") -> None:
    """Run the MCP server."""
    app = create_app()
    app.run(transport=transport)


if __name__ == "__main__":
    main()
