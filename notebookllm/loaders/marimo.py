"""Marimo format loader — .py files with @app.cell decorators."""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

from notebookllm.loaders.base import BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument


class MarimoLoader(BaseLoader):
    """Load marimo format .py files using AST parsing."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return NotebookDocument(cells=[], source_format="marimo")

        # Extract __generated_with version from module-level assignment
        generated_with = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__generated_with":
                        if isinstance(node.value, ast.Constant):
                            generated_with = node.value.value
                        elif isinstance(node.value, ast.Str):  # Python < 3.8 compat
                            generated_with = node.value.s

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not self._has_cell_decorator(node):
                continue
            # Extract cell body from AST
            cell_source, cell_type = self._extract_cell(content, node)
            cells.append(Cell(cell_type=cell_type, source=cell_source))

        metadata = {}
        if generated_with:
            metadata["generated_with"] = generated_with

        return NotebookDocument(cells=cells, metadata=metadata, source_format="marimo")

    def _has_cell_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if function has @app.cell decorator."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute):
                if dec.attr == "cell" and isinstance(dec.value, ast.Name) and dec.value.id == "app":
                    return True
            if isinstance(dec, ast.Name) and dec.id == "cell":
                return True
        return False

    def _is_mo_md_call(self, source: str) -> bool:
        """Detect if the cell body is primarily a mo.md() call (marimo markdown).

        Marimo stores markdown content as mo.md("...") calls inside code cells.
        We detect this pattern to convert the cell to CellType.MARKDOWN.
        """
        stripped = source.strip()
        # Match mo.md("...") with optional return prefix
        return bool(re.match(r"^(?:return\s+)?mo\.md\(", stripped))

    def _extract_cell(self, content: str, node: ast.FunctionDef) -> tuple[str, CellType]:
        """Extract cell body and detect if it's markdown (mo.md() call)."""
        lines = content.splitlines(keepends=True)
        body_start = node.body[0].lineno - 1
        end_line = node.body[-1].end_lineno if hasattr(node, "end_lineno") and node.end_lineno else (body_start + len(node.body))

        body_lines = lines[body_start:end_line]
        source = "".join(body_lines)

        # Strip common indentation (the body is indented under def)
        source = textwrap.dedent(source)

        # Remove trailing return statement (marimo convention: return var1, var2,)
        source = re.sub(r"\nreturn\s+[^\n]*\s*$", "", source)

        # Detect if this is a mo.md() markdown cell
        cell_type = CellType.MARKDOWN if self._is_mo_md_call(source) else CellType.CODE

        return source, cell_type