"""Script format dumper — flat .py without cell markers.

Converts notebooks to standalone scripts: code cells become code,
markdown/raw cells become comments. This is a ONE-WAY export format
(no loader) — there's no way to reconstruct cell boundaries from
a flat script.
"""
from __future__ import annotations

from pathlib import Path

from notebookllm.loaders.base import BaseDumper
from notebookllm.models import CellType, NotebookDocument


class ScriptDumper(BaseDumper):
    """Dump to flat script format (no cell markers)."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                parts.append(cell.source.rstrip("\n"))
            elif cell.cell_type == CellType.MARKDOWN:
                # Markdown becomes comment lines
                for line in cell.source.split("\n"):
                    if line.strip():
                        parts.append(f"# {line}")
                    else:
                        parts.append("#")
            elif cell.cell_type == CellType.RAW:
                for line in cell.source.split("\n"):
                    if line.strip():
                        parts.append(f"# {line}")
                    else:
                        parts.append("#")
            parts.append("")

        result = "\n".join(parts).rstrip()
        if result:
            result += "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result