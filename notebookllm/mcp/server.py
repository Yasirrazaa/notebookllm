"""MCP server for notebookllm — tools for notebook operations."""
from __future__ import annotations

import uuid

from notebookllm.loaders import dump_file, load_file
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument, OutputMode

MAX_SESSIONS = 100


def _get_doc_safe(session_manager: SessionManager, session_id: str) -> NotebookDocument | None:
    """Get notebook doc, returning None if session missing."""
    try:
        return session_manager.get(session_id)
    except KeyError:
        return None


def create_app(session_manager: SessionManager | None = None):
    """Create and configure the MCP server app."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP server requires 'mcp[cli]'. Install with: pip install notebookllm[mcp]"
        ) from None

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
    def create_notebook(source_format: str | None = None) -> str:
        """Create a new empty notebook session."""
        session_id = str(uuid.uuid4())
        doc = NotebookDocument(source_format=source_format)
        session_manager.store(session_id, doc)
        return f"Created empty notebook. Session: {session_id}"

    @mcp.tool()
    def list_sessions() -> str:
        """List all active notebook sessions."""
        sessions = session_manager.list_sessions()
        if not sessions:
            return "No active sessions."
        lines = []
        for sid in sessions:
            doc = _get_doc_safe(session_manager, sid)
            cell_count = len(doc.cells) if doc else "?"
            fmt = doc.source_format or "unspecified" if doc else "?"
            lines.append(f"{sid:36s} {cell_count:3d} cells  [{fmt}]")
        return "\n".join(lines)

    @mcp.tool()
    def save_notebook(session_id: str, output_filepath: str | None = None) -> str:
        """Save notebook to file."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        filepath = output_filepath or session_manager.get_filepath(session_id)
        if not filepath:
            return "No filepath specified and none set in session."
        dump_file(doc, filepath)
        return f"Saved to {filepath}"

    @mcp.tool()
    def to_text(session_id: str, mode: str = "minimal") -> str:
        """Convert notebook to LLM-optimized text."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        output_mode = OutputMode(mode)
        return doc.to_text(mode=output_mode)

    @mcp.tool()
    def list_cells(session_id: str) -> str:
        """List all cells with index, type, and preview."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
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
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        cell = doc.get_cell(index)
        return f"Cell [{index}] ({cell.cell_type.value}):\n{cell.source}"

    @mcp.tool()
    def add_cell(
        session_id: str, source: str, cell_type: str = "code", position: int | None = None
    ) -> str:
        """Add a new cell."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        ct = CellType(cell_type)
        cell = Cell(cell_type=ct, source=source)
        doc.add_cell(cell, position=position)
        return f"Added {cell_type} cell at position {position or len(doc.cells) - 1}"

    @mcp.tool()
    def edit_cell(session_id: str, index: int, source: str, cell_type: str | None = None) -> str:
        """Edit an existing cell."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        ct = CellType(cell_type) if cell_type else None
        doc.edit_cell(index, source=source, cell_type=ct)
        return f"Edited cell [{index}]"

    @mcp.tool()
    def delete_cell(session_id: str, index: int) -> str:
        """Delete a cell by index."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        cell = doc.get_cell(index)
        doc.delete_cell(index)
        return f"Deleted cell [{index}] ({cell.cell_type.value})"

    @mcp.tool()
    def move_cell(session_id: str, from_index: int, to_index: int) -> str:
        """Move a cell from one position to another."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        doc.move_cell(from_index, to_index)
        return f"Moved cell from [{from_index}] to [{to_index}]"

    @mcp.tool()
    def search_cells(session_id: str, query: str, cell_type: str | None = None) -> str:
        """Search cells by content (case-insensitive)."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
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
    def count_tokens(session_id: str, mode: str = "minimal") -> str:
        """Count tokens in the session notebook (modes: minimal, standard, full)."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        from notebookllm.utils.tokenizer import tokenize_notebook
        report = tokenize_notebook(doc, mode=mode)
        return report.token_summary

    @mcp.tool()
    def convert_format(session_id: str, output_filepath: str, target_format: str) -> str:
        """Convert a session's notebook to another format and save it. Target formats: ipynb, deepnote, percent, marimo, quarto, markdown, rmarkdown, script."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        
        from notebookllm.loaders import dump_file
        try:
            dump_file(doc, output_filepath, fmt=target_format)
            return f"Converted session {session_id} to {target_format} format: {output_filepath}"
        except Exception as e:
            return f"Error converting format: {e}"

    @mcp.tool()
    def execute_cell(session_id: str, index: int, timeout: int = 60) -> str:
        """Execute a code cell via Jupyter kernel (requires notebookllm[execute])."""
        try:
            import jupyter_client  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return (
                "Error: notebookllm[execute] not installed."
                " Run: pip install notebookllm[execute]"
            )

        try:
            session = session_manager.get_session(session_id)
        except KeyError:
            return f"Session not found: {session_id}"
            
        doc = session.doc
        cell = doc.get_cell(index)
        if cell.cell_type != CellType.CODE:
            return f"Cell [{index}] is not a code cell (it's {cell.cell_type.value})."

        # Execute via jupyter_client
        from jupyter_client import KernelManager

        if session.kernel_manager is None:
            kernel_name = doc.kernel_name or "python3"
            try:
                session.kernel_manager = KernelManager(kernel_name=kernel_name)
                session.kernel_manager.start_kernel()
                session.kernel_client = session.kernel_manager.client()
                session.kernel_client.start_channels()
            except Exception as e:
                return f"Failed to start kernel '{kernel_name}': {e}"

        client = session.kernel_client

        try:
            msg_id = client.execute(cell.source)
            try:
                reply = client.get_shell_msg(timeout=timeout)
            except TimeoutError:
                return f"Cell execution timed out after {timeout}s"
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
                            out_name = content.get("name", "stdout")
                            out_text = content.get("text", "")
                            outputs.append(f"[{out_name}] {out_text}")
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
        except Exception as e:
            return f"Error executing cell: {e}"

    return mcp


def main(transport: str = "stdio") -> None:
    """Run the MCP server."""
    app = create_app()
    app.run(transport=transport)


if __name__ == "__main__":
    main()
