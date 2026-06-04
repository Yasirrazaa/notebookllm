"""Marimo format loader — .py files with @app.cell decorators."""
from __future__ import annotations

import ast
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
            # If AST fails, return empty
            return NotebookDocument(cells=[], source_format="marimo")

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not self._has_cell_decorator(node):
                continue
            # Extract cell body from AST
            cell_source = self._extract_cell_body(content, node)
            cells.append(Cell(cell_type=CellType.CODE, source=cell_source))

        return NotebookDocument(cells=cells, source_format="marimo")

    def _has_cell_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if function has @app.cell or @app.function decorator."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "cell":
                return True
            if isinstance(dec, ast.Name) and dec.id == "cell":
                return True
        return False

    def _extract_cell_body(self, content: str, node: ast.FunctionDef) -> str:
        """Extract the function body as source code, stripping the decorator and def line."""
        lines = content.splitlines(keepends=True)
        # Find the start of the function body (first line after def:)
        body_start = node.body[0].lineno - 1
        body_end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else body_start + 1

        body_lines = lines[body_start:body_end]
        source = "".join(body_lines)

        # Strip common indentation (the body is indented under def)
        source = textwrap.dedent(source)

        # Remove trailing return statement if it's just returning variables
        # (marimo convention: return var1, var2,)
        source = source.rstrip()

        return source