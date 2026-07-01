"""MCP server for notebookllm — tools for notebook operations."""
from __future__ import annotations

import asyncio
import uuid

from notebookllm.loaders import dump_file, load_file
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument, OutputMode
from mcp.server.fastmcp.tools.base import ToolAnnotations

MAX_SESSIONS = 100


def _get_doc_safe(session_manager: SessionManager, session_id: str) -> NotebookDocument | None:
    """Get notebook doc, returning None if session missing."""
    try:
        return session_manager.get(session_id)
    except KeyError:
        return None


def _validate_cell_type(cell_type: str) -> CellType | str:
    """Convert string to CellType, returning an error message on failure."""
    try:
        return CellType(cell_type)
    except ValueError:
        valid = [ct.value for ct in CellType]
        return f"Invalid cell_type '{cell_type}'. Valid: {', '.join(valid)}"


def _validate_output_mode(mode: str) -> OutputMode | str:
    """Convert string to OutputMode, returning an error message on failure."""
    try:
        return OutputMode(mode)
    except ValueError:
        valid = [m.value for m in OutputMode]
        return f"Invalid mode '{mode}'. Valid: {', '.join(valid)}"


def _enforce_session_limit(
    session_manager: SessionManager, kernel_pool: object
) -> None:
    """Evict oldest session if over MAX_SESSIONS (synchronous path — for load/create)."""
    sessions = session_manager.list_sessions()
    while len(sessions) > MAX_SESSIONS:
        oldest = sessions[0]
        session_manager.delete(oldest)
        sessions = session_manager.list_sessions()


async def _enforce_session_limit_async(
    session_manager: SessionManager, kernel_pool: object
) -> None:
    """Evict oldest session if over MAX_SESSIONS (async path — for tools that can await)."""
    from notebookllm.mcp.engine import KernelPool

    sessions = session_manager.list_sessions()
    while len(sessions) > MAX_SESSIONS:
        oldest = sessions[0]
        if isinstance(kernel_pool, KernelPool):
            await kernel_pool.shutdown_kernel(oldest)
        session_manager.delete(oldest)
        sessions = session_manager.list_sessions()


def create_app(session_manager: SessionManager | None = None):
    """Create and configure the MCP server app."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP server requires 'mcp[cli]'. Install with: pip install notebookllm[mcp]"
        ) from None

    from notebookllm.mcp.engine import KernelPool
    kernel_pool = KernelPool()

    if session_manager is None:
        session_manager = SessionManager()

    mcp = FastMCP("notebookllm")

    # ── Resources ──────────────────────────────────────────────

    @mcp.resource("notebook://{session_id}")
    def notebook_text(session_id: str) -> str:
        """Full notebook as LLM-optimized text (minimal mode)."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        return doc.to_text(mode=OutputMode.MINIMAL)

    @mcp.resource("notebook://{session_id}/cells")
    def notebook_cells(session_id: str) -> str:
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

    @mcp.resource("notebook://{session_id}/cells/{index}")
    def notebook_cell(session_id: str, index: int) -> str:
        """Get a specific cell by index."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        try:
            cell = doc.get_cell(index)
            return f"Cell [{index}] ({cell.cell_type.value}):\n{cell.source}"
        except IndexError:
            return f"Cell [{index}] not found."

    # ── Prompts ────────────────────────────────────────────────

    @mcp.prompt()
    def summarize_notebook(session_id: str) -> str:
        """Summarize the contents and purpose of a notebook session."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        cells = doc.cells
        code_cells = [c for c in cells if c.cell_type == CellType.CODE]
        markdown_cells = [c for c in cells if c.cell_type == CellType.MARKDOWN]
        imports = set()
        for c in code_cells:
            import re
            for m in re.finditer(r"^(?:from\s+([a-zA-Z0-9_.]+).*import|import\s+([a-zA-Z0-9_., ]+))", c.source, re.MULTILINE):
                if m.group(1):
                    imports.add(m.group(1).split(".")[0])
                elif m.group(2):
                    for im in m.group(2).split(","):
                        imports.add(im.strip().split(".")[0])
        libraries = f"Key libraries: {', '.join(sorted(imports))}." if imports else ""
        return (
            f"Please summarize the notebook session `{session_id}`.\n\n"
            f"The notebook has {len(cells)} cells "
            f"({len(code_cells)} code, {len(markdown_cells)} markdown).\n"
            f"{libraries}\n\n"
            f"Full content:\n{doc.to_text(mode=OutputMode.MINIMAL)}"
        )

    @mcp.prompt()
    def review_code(session_id: str) -> str:
        """Review code quality in a notebook session."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        code = "\n\n".join(c.source for c in code_cells)
        return (
            f"Please review the code quality in notebook session `{session_id}`. "
            f"Focus on correctness, readability, performance, and best practices. "
            f"There are {len(code_cells)} code cells.\n\n"
            f"```python\n{code}\n```"
        )

    @mcp.prompt()
    def explain_notebook(session_id: str) -> str:
        """Explain what a notebook does step by step."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        text = doc.to_text(mode=OutputMode.STANDARD)
        return (
            f"Please explain what notebook session `{session_id}` does. "
            f"Walk through each cell and explain the logic step by step.\n\n{text}"
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def load(filepath: str) -> str:
        """Load a notebook file into session."""
        session_id = str(uuid.uuid4())
        doc = load_file(filepath)
        session_manager.store(session_id, doc, filepath=filepath)
        _enforce_session_limit(session_manager, kernel_pool)
        return f"Loaded {len(doc.cells)} cells from {filepath}. Session: {session_id}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def load_notebook(filepath: str) -> str:
        """Alias for load()."""
        return load(filepath)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def create(source_format: str | None = None) -> str:
        """Create a new empty notebook session."""
        session_id = str(uuid.uuid4())
        doc = NotebookDocument(source_format=source_format)
        session_manager.store(session_id, doc)
        _enforce_session_limit(session_manager, kernel_pool)
        return f"Created empty notebook. Session: {session_id}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def create_notebook(source_format: str | None = None) -> str:
        """Alias for create()."""
        return create(source_format)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    def save(session_id: str, output_filepath: str | None = None) -> str:
        """Save notebook to file."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        filepath = output_filepath or session_manager.get_filepath(session_id)
        if not filepath:
            return "No filepath specified and none set in session."
        dump_file(doc, filepath)
        return f"Saved to {filepath}"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    def save_notebook(session_id: str, output_filepath: str | None = None) -> str:
        """Alias for save()."""
        return save(session_id, output_filepath)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def to_text(session_id: str, mode: str = "minimal") -> str:
        """Convert notebook to LLM-optimized text."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        result = _validate_output_mode(mode)
        if isinstance(result, str):
            return result
        return doc.to_text(mode=result)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def get_cell(session_id: str, index: int) -> str:
        """Get a specific cell by index."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        cell = doc.get_cell(index)
        return f"Cell [{index}] ({cell.cell_type.value}):\n{cell.source}"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    def add_cell(
        session_id: str, source: str, cell_type: str = "code", position: int | None = None
    ) -> str:
        """Add a new cell."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        result = _validate_cell_type(cell_type)
        if isinstance(result, str):
            return result
        cell = Cell(cell_type=result, source=source)
        doc.add_cell(cell, position=position)
        return f"Added {cell_type} cell at position {position or len(doc.cells) - 1}"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    def edit_cell(session_id: str, index: int, source: str, cell_type: str | None = None) -> str:
        """Edit an existing cell."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        if cell_type is not None:
            result = _validate_cell_type(cell_type)
            if isinstance(result, str):
                return result
            ct = result
        else:
            ct = None
        doc.edit_cell(index, source=source, cell_type=ct)
        return f"Edited cell [{index}]"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    def delete_cell(session_id: str, index: int) -> str:
        """Delete a cell by index."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        cell = doc.get_cell(index)
        doc.delete_cell(index)
        return f"Deleted cell [{index}] ({cell.cell_type.value})"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    def move_cell(session_id: str, from_index: int, to_index: int) -> str:
        """Move a cell from one position to another."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        doc.move_cell(from_index, to_index)
        return f"Moved cell from [{from_index}] to [{to_index}]"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def search_cells(session_id: str, query: str, cell_type: str | None = None) -> str:
        """Search cells by content (case-insensitive)."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        if cell_type is not None:
            result = _validate_cell_type(cell_type)
            if isinstance(result, str):
                return result
            ct = result
        else:
            ct = None
        results = doc.search(query, cell_type=ct)
        if not results:
            return "No matches found."
        lines = []
        for idx, cell in results:
            preview = cell.source[:60].replace("\n", " ")
            lines.append(f"[{idx}] {cell.cell_type.value:10s} {preview}")
        return "\n".join(lines)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def count_tokens(session_id: str, mode: str = "minimal") -> str:
        """Count tokens in the session notebook (modes: minimal, standard, full)."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        from notebookllm.utils.tokenizer import tokenize_notebook
        report = tokenize_notebook(doc, mode=mode)
        return report.token_summary

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    def convert(session_id: str, output_filepath: str, target_format: str) -> str:
        """Convert a session's notebook to another format and save it."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        
        from notebookllm.loaders import dump_file
        try:
            dump_file(doc, output_filepath, fmt=target_format)
            return f"Converted session {session_id} to {target_format} format: {output_filepath}"
        except Exception as e:
            return f"Error converting format: {e}"

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    def convert_format(session_id: str, output_filepath: str, target_format: str) -> str:
        """Alias for convert()."""
        return convert(session_id, output_filepath, target_format)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def execute(session_id: str, index: int, timeout: int = 60) -> str:
        """Execute a code cell via Jupyter kernel (requires notebookllm[execute])."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
            
        cell = doc.get_cell(index)
        if cell.cell_type != CellType.CODE:
            return f"Cell [{index}] is not a code cell (it's {cell.cell_type.value})."

        try:
            await kernel_pool.start_kernel(session_id, doc.kernel_name or "python3")
            return await kernel_pool.execute_cell(session_id, index, cell.source, timeout=timeout)
        except Exception as e:
            return str(e)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def execute_cell(session_id: str, index: int, timeout: int = 60) -> str:
        """Alias for execute()."""
        return await execute(session_id, index, timeout)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def execute_all(session_id: str, timeout: int = 60) -> str:
        """Execute all code cells sequentially."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"

        try:
            await kernel_pool.start_kernel(session_id, doc.kernel_name or "python3")
            return await kernel_pool.execute_all_cells(session_id, doc.cells, timeout=timeout)
        except Exception as e:
            return str(e)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def execute_all_cells(session_id: str, timeout: int = 60) -> str:
        """Alias for execute_all()."""
        return await execute_all(session_id, timeout)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def list_kernels() -> str:
        """List available kernels from jupyter kernelspec."""
        kernels = kernel_pool.list_kernels()
        if not kernels:
            return "No kernels found."
        lines = []
        for k in kernels:
            name = k.get("name", "?")
            display_name = k.get("display_name", name)
            language = k.get("language", "?")
            lines.append(f"  {name:20s} {display_name:30s} ({language})")
        return f"Available kernels ({len(kernels)}):\n" + "\n".join(lines)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    async def close_session(session_id: str) -> str:
        """Explicitly close and remove a notebook session, cleaning up any associated kernel."""
        # Shut down any active kernel before removing the session
        if kernel_pool.has_kernel(session_id):
            await kernel_pool.shutdown_kernel(session_id)
        try:
            session_manager.delete(session_id)
            return f"Session {session_id} closed."
        except KeyError:
            return f"Session not found: {session_id}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def fingerprint(session_id: str) -> str:
        """Provide a concise summary/fingerprint of a notebook session."""
        doc = _get_doc_safe(session_manager, session_id)
        if doc is None:
            return f"Session not found: {session_id}"
        
        cells = doc.cells
        total = len(cells)
        code_cells = [c for c in cells if c.cell_type == CellType.CODE]
        markdown = len([c for c in cells if c.cell_type == CellType.MARKDOWN])
        raw = len([c for c in cells if c.cell_type == CellType.RAW])
        
        executed = len([c for c in code_cells if c.execution_count is not None or c.outputs])
        
        import re
        imports = set()
        functions = set()
        for c in code_cells:
            for match in re.finditer(r"^(?:from\s+([a-zA-Z0-9_.]+).*import|import\s+([a-zA-Z0-9_., ]+))", c.source, re.MULTILINE):
                if match.group(1):
                    imports.add(match.group(1).split(".")[0])
                elif match.group(2):
                    for m in match.group(2).split(","):
                        imports.add(m.strip().split(".")[0])
            for match in re.finditer(r"^def\s+([a-zA-Z0-9_]+)\s*\(", c.source, re.MULTILINE):
                functions.add(match.group(1))
                
        lines = [
            f"Cells: {total} ({len(code_cells)} code, {markdown} markdown, {raw} raw)",
            f"Executed: {executed}/{len(code_cells)} code cells",
        ]
        if imports:
            lines.append(f"Imports: {', '.join(sorted(imports))}")
        if functions:
            lines.append(f"Functions: {', '.join(sorted(functions))}")
            
        return "\n".join(lines)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def diff(session_id1: str, session_id2: str) -> str:
        """Compare the minimal text representation of two notebook sessions."""
        doc1 = _get_doc_safe(session_manager, session_id1)
        doc2 = _get_doc_safe(session_manager, session_id2)
        if not doc1:
            return f"Session not found: {session_id1}"
        if not doc2:
            return f"Session not found: {session_id2}"
        import difflib
        text1 = doc1.to_text(mode=OutputMode.MINIMAL).splitlines(keepends=True)
        text2 = doc2.to_text(mode=OutputMode.MINIMAL).splitlines(keepends=True)
        return "".join(difflib.unified_diff(text1, text2, fromfile=session_id1, tofile=session_id2))

    return mcp


def main(transport: str = "stdio") -> None:
    """Run the MCP server."""
    app = create_app()
    app.run(transport=transport)


if __name__ == "__main__":
    main()
