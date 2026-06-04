"""Percent format loader/dumper — .py files with # %% markers."""
from __future__ import annotations

import re
from pathlib import Path

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellType, NotebookDocument

CELL_MARKER = re.compile(r"^#\s*%%\s*(?:\[(\w+)\])?\s*$")


def _is_inside_string(lines: list[str]) -> bool:
    """Check if the current code is inside an unclosed triple-quoted string.

    Tracks triple-double-quote and triple-single-quote boundaries to avoid
    false-positive cell marker detection when '# %%' appears inside a string.
    Returns True if we're inside an unclosed triple-quoted string.
    """
    depth_dq = 0  # triple-double-quote depth
    depth_sq = 0  # triple-single-quote depth
    for line in lines:
        i = 0
        while i < len(line):
            if line[i:i+3] == '"""':
                depth_dq ^= 1  # toggle
                i += 3
            elif line[i:i+3] == "'''":
                depth_sq ^= 1
                i += 3
            else:
                i += 1
    return depth_dq == 1 or depth_sq == 1


class PercentLoader(BaseLoader):
    """Load percent format .py files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells: list[Cell] = []
        current_type = CellType.CODE
        current_lines: list[str] = []
        all_lines: list[str] = []
        has_markers = False

        for line in content.splitlines(keepends=True):
            # Skip markers that appear inside triple-quoted strings
            if _is_inside_string(all_lines + [line.split("#")[0]]):
                current_lines.append(line)
                all_lines.append(line)
                continue

            match = CELL_MARKER.match(line.rstrip())
            if match:
                has_markers = True
                if current_lines or cells:
                    source = "".join(current_lines).rstrip("\n")
                    cells.append(Cell(cell_type=current_type, source=source))
                cell_type_str = match.group(1) or "code"
                try:
                    current_type = CellType(cell_type_str)
                except ValueError:
                    current_type = CellType.CODE
                current_lines = []
            else:
                current_lines.append(line)
            all_lines.append(line)

        if current_lines:
            source = "".join(current_lines).rstrip("\n")
            cells.append(Cell(cell_type=current_type, source=source))

        if not has_markers and content.strip():
            cells = [Cell(cell_type=CellType.CODE, source=content.rstrip("\n"))]

        return NotebookDocument(cells=cells, source_format="percent")


class PercentDumper(BaseDumper):
    """Dump to percent format .py files."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        parts = []
        for cell in doc.cells:
            marker = f"# %% [{cell.cell_type.value}]"
            parts.append(f"{marker}\n{cell.source}")

        result = "\n\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
