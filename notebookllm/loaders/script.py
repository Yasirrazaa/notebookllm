"""Script format dumper — flat ``.py`` without cell markers.

Converts notebooks to standalone scripts: code cells become code,
markdown/raw cells become comments. This is a **one-way** export format
(no loader) — there is no way to reconstruct cell boundaries from a
flat script.

Use this format when you need a plain Python file that can be run
directly without any notebook-aware tooling.
"""
from __future__ import annotations

from pathlib import Path

from notebookllm.loaders.base import BaseDumper
from notebookllm.models import CellType, NotebookDocument


class ScriptDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to flat ``.py`` format.

    Code cells become Python code. Markdown and raw cells become ``#``-prefixed
    comments. All cell boundaries are lost — this format cannot be loaded back.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to a flat script.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The flat script content as a string.
        """
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                parts.append(cell.source.rstrip("\n"))
            elif cell.cell_type == CellType.MARKDOWN:
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
