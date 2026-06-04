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
        """Check if function has @app.cell decorator."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute):
                if dec.attr == "cell" and isinstance(dec.value, ast.Name) and dec.value.id == "app":
                    return True
            if isinstance(dec, ast.Name) and dec.id == "cell":
                return True
        return False

    def _extract_cell_body(self, content: str, node: ast.FunctionDef) -> str:
        """Extract the function body as source code, stripping the decorator and def line."""
        lines = content.splitlines(keepends=True)
        body_start = node.body[0].lineno - 1
        end_line = node.body[-1].end_lineno if hasattr(node, "end_lineno") and node.end_lineno else (body_start + len(node.body))

        body_lines = lines[body_start:end_line]
        source = "".join(body_lines)

        # Strip common indentation (the body is indented under def)
        source = textwrap.dedent(source)

        # Remove trailing return statement (marimo convention: return var1, var2,)
        source = re.sub(r"\nreturn\s+[^\n]*\s*$", "", source)

        return source