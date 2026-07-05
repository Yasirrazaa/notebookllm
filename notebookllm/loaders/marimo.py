"""Marimo format loader/dumper — ``.py`` files with ``@app.cell`` decorators.

Marimo (https://marimo.io) is a reactive Python notebook that stores
notebooks as standard Python files. Cells are defined as functions
decorated with ``@app.cell``.

Markdown cells are represented as ``mo.md("...")`` calls inside code
cells. The loader detects this pattern and converts them to
:attr:`~notebookllm.models.CellType.MARKDOWN` cells.
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument


class MarimoLoader(BaseLoader):
    """Load marimo-format ``.py`` files using AST parsing.

    Parses the Python AST to find functions decorated with ``@app.cell``,
    extracts their source code, and detects ``mo.md()`` calls to identify
    markdown cells. Also extracts the ``__generated_with`` version from
    module-level assignments.
    """

    def load(self, source: str | Path) -> NotebookDocument:
        """Load a marimo notebook from a file path.

        Args:
            source: Path to the marimo ``.py`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        """Load a marimo notebook from a string.

        Args:
            content: Raw marimo source code.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
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
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "__generated_with" and node.value is not None:
                    if isinstance(node.value, ast.Constant):
                        generated_with = node.value.value
                    elif isinstance(node.value, ast.Str):
                        generated_with = node.value.s

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not self._has_cell_decorator(node):
                continue
            cell_source, cell_type = self._extract_cell(content, node)
            cells.append(Cell(cell_type=cell_type, source=cell_source))

        metadata = {}
        if generated_with:
            metadata["generated_with"] = generated_with

        return NotebookDocument(cells=cells, metadata=metadata, source_format="marimo")

    def _has_cell_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if a function has the ``@app.cell`` decorator.

        Args:
            node: An AST function definition node.

        Returns:
            ``True`` if the function is decorated with ``@app.cell``.
        """
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute):
                if dec.attr == "cell" and isinstance(dec.value, ast.Name) and dec.value.id == "app":
                    return True
            if isinstance(dec, ast.Name) and dec.id == "cell":
                return True
        return False

    def _is_mo_md_call(self, source: str) -> bool:
        """Detect if a cell body is primarily a ``mo.md()`` call (marimo markdown).

        Marimo stores markdown content as ``mo.md("...")`` calls inside
        code cells. This pattern is detected to convert the cell to
        :attr:`~notebookllm.models.CellType.MARKDOWN`.

        Args:
            source: The cell source text.

        Returns:
            ``True`` if the cell appears to be a ``mo.md()`` markdown cell.
        """
        stripped = source.strip()
        return bool(re.match(r"^(?:return\s+)?mo\.md\(", stripped))

    def _extract_cell(self, content: str, node: ast.FunctionDef) -> tuple[str, CellType]:
        """Extract the body of a marimo cell function and detect its type.

        Strips the function definition, dedents the body, removes trailing
        ``return`` statements, and detects ``mo.md()`` calls.

        Args:
            content: The full marimo source code.
            node: The AST function definition node.

        Returns:
            A ``(source, cell_type)`` tuple.
        """
        lines = content.splitlines(keepends=True)
        body_start = node.body[0].lineno - 1
        if hasattr(node, "end_lineno") and node.end_lineno:
            end_line = node.body[-1].end_lineno
        elif hasattr(node.body[-1], "end_lineno") and node.body[-1].end_lineno:
            end_line = node.body[-1].end_lineno
        else:
            end_line = max(stmt.lineno for stmt in node.body)

        body_lines = lines[body_start:end_line]
        source = "".join(body_lines)

        # Strip common indentation (the body is indented under def)
        source = textwrap.dedent(source)

        # Remove trailing return statement (marimo convention: return var1, var2,)
        source = re.sub(r"\nreturn\s+[^\n]*\s*$", "", source)

        # Detect if this is a mo.md() markdown cell
        cell_type = CellType.MARKDOWN if self._is_mo_md_call(source) else CellType.CODE

        return source, cell_type


class MarimoDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to marimo format.

    Produces a valid marimo ``.py`` file with ``@app.cell`` decorators.
    Markdown cells are wrapped in ``mo.md()`` calls.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to marimo format.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The marimo-format source code as a string.
        """
        lines = [
            "import marimo",
            "",
            f"__generated_with = \"{doc.metadata.get('generated_with', '0.8.0')}\"",
            "app = marimo.App()",
            "",
            "",
        ]

        for i, cell in enumerate(doc.cells):
            lines.append("@app.cell")
            func_name = f"cell_{i}"
            lines.append(f"def {func_name}():")

            if cell.cell_type == CellType.MARKDOWN:
                md_content = cell.source.replace('"""', '\\"\\"\\"')
                body = (
                    "import marimo as mo\nreturn mo.md(\n"
                    f'    """\n{textwrap.indent(md_content, "    ")}'
                    '\n    """\n)'
                )
            else:
                body = cell.source

            if not body.strip():
                body = "pass"

            indented_body = textwrap.indent(body, "    ")
            lines.append(indented_body)

            has_return = body.strip().endswith("return")
            has_leading_return = re.search(r"^\s*return\b", body, flags=re.MULTILINE)
            if not has_return and not has_leading_return:
                lines.append("    return")

            lines.append("")
            lines.append("")

        content = "\n".join(lines).rstrip() + "\n"

        if filepath:
            filepath.write_text(content, encoding="utf-8")
        return content
