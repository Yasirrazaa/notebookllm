"""Percent format loader/dumper — ``.py`` files with cell markers.

Percent-format scripts (also called "cell mode" or "VS Code interactive")
use ``# %%`` comments as cell delimiters. This is the native format for
VS Code's Python Interactive window, Spyder, and PyCharm's Scientific Mode.

Markdown cells are encoded as ``#``-prefixed comment lines.

Example::

    # %% [markdown]
    # This is a markdown cell.
    # It explains what follows.

    # %% [code]
    import pandas as pd
    print("hello")
"""
from __future__ import annotations

import re
from pathlib import Path

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

CELL_MARKER = re.compile(r"^#\s*%%\s*(?:\[(\w+)\])?\s*$")


class PercentLoader(BaseLoader):
    """Load percent-format ``.py`` files with ``# %%`` cell markers.

    Detects cell boundaries by ``# %%`` markers. Markdown cells are
    identified by the ``[markdown]`` tag in the marker line. Supports
    triple-quoted strings (``'\"\"\"'`` and ``'''``) — markers inside
    docstrings are ignored.
    """

    def load(self, source: str | Path) -> NotebookDocument:
        """Load a percent-format notebook from a file path.

        Args:
            source: Path to the ``.py`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        """Load a percent-format notebook from a string.

        Args:
            content: Raw percent-format source code.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        cells: list[Cell] = []
        current_type = CellType.CODE
        current_lines: list[str] = []
        has_markers = False
        in_triple_dq = False  # inside """ (odd depth)
        in_triple_sq = False  # inside ''' (odd depth)

        for line in content.splitlines(keepends=True):
            line_before_comment = line.split("#")[0]

            # Track triple-quote state incrementally (O(1) per line instead of O(n²))
            in_triple_dq = _toggle_on_triple(line_before_comment, '"""', in_triple_dq)
            in_triple_sq = _toggle_on_triple(line_before_comment, "'''", in_triple_sq)

            # Skip markers that appear inside triple-quoted strings
            if in_triple_dq or in_triple_sq:
                current_lines.append(line)
                continue

            match = CELL_MARKER.match(line.rstrip())
            if match:
                has_markers = True
                if current_lines or cells:
                    source = _make_source(current_lines, current_type)
                    cells.append(Cell(cell_type=current_type, source=source))
                cell_type_str = match.group(1) or "code"
                try:
                    current_type = CellType(cell_type_str)
                except ValueError:
                    current_type = CellType.CODE
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            source = _make_source(current_lines, current_type)
            cells.append(Cell(cell_type=current_type, source=source))

        if not has_markers and content.strip():
            cells = [Cell(cell_type=CellType.CODE, source=content.rstrip("\n"))]

        return NotebookDocument(cells=cells, source_format="percent")


def _toggle_on_triple(text: str, delimiter: str, current: bool) -> bool:
    """Toggle boolean state on each occurrence of a triple delimiter in text.

    Used to track whether we are inside a triple-quoted string (``\"\"\"``
    or ``'''``) while scanning for cell markers.

    Args:
        text: The text to scan.
        delimiter: Triple-quote delimiter (``'\"\"\"'`` or ``\"'''\"``).
        current: Current state (``True`` = inside triple-quoted string).

    Returns:
        Updated state after processing all occurrences in *text*.
    """
    i = 0
    while i < len(text):
        idx = text.find(delimiter, i)
        if idx < 0:
            break
        current = not current
        i = idx + 3
    return current


def _strip_comment_prefix(line: str) -> str:
    """Strip the leading ``# `` (or bare ``#``) comment prefix from a markdown line.

    In percent format, markdown cells are stored as Python comments where
    each line starts with ``# `` (or just ``#`` on empty lines). This function
    removes one level of that encoding.

    Args:
        line: A single line from a percent-format markdown cell.

    Returns:
        The line with the ``# `` prefix removed.
    """
    if line.startswith("# "):
        return line[2:]
    if line.startswith("#") and not line.startswith("##"):
        # Bare '# ' or just '#' — strip one character
        return line[1:]
    return line


def _make_source(lines: list[str], cell_type: CellType) -> str:
    """Build cell source from raw percent-format lines.

    For markdown cells, strips ``# `` comment prefixes. For code and raw
    cells, joins lines as-is.

    Args:
        lines: Raw lines including comment prefixes for markdown cells.
        cell_type: The type of cell being built.

    Returns:
        Clean cell source text.
    """
    if cell_type == CellType.MARKDOWN:
        stripped = [_strip_comment_prefix(line) for line in lines]
        return "".join(stripped).rstrip("\n")
    return "".join(lines).rstrip("\n")


class PercentDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to percent format.

    Code cells are output with ``# %% [code]`` markers. Markdown cells
    use ``# %% [markdown]`` markers with content encoded as ``#``-prefixed
    comment lines.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to percent-format ``.py``.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            Percent-format source code as a string.
        """
        parts = []
        for cell in doc.cells:
            marker = f"# %% [{cell.cell_type.value}]"
            source = cell.source.rstrip("\n")
            if cell.cell_type == CellType.MARKDOWN:
                # Encode markdown lines as Python comments with "# " prefix
                md_lines = source.split("\n")
                encoded = "\n".join(
                    f"# {line}" if line else "#"
                    for line in md_lines
                )
                parts.append(f"{marker}\n{encoded}")
            else:
                parts.append(f"{marker}\n{source}")

        result = "\n\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
