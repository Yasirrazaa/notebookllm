"""Markdown format loader/dumper — ``.md`` files with fenced code blocks.

Loads and saves notebooks as standard Markdown files. Code cells are
stored as fenced code blocks with language tags (e.g., `````python```,
`````r`````). Markdown cells are stored as plain markdown text.

Supports optional YAML frontmatter. Code blocks with known languages
(python, r, julia, javascript, typescript) become
:attr:`~notebookllm.models.CellType.CODE` cells; others become
:attr:`~notebookllm.models.CellType.RAW`.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

CODE_BLOCK_RE = re.compile(r"```(\w+)\s*\n(.*?)```", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownLoader(BaseLoader):
    """Load Markdown files with embedded fenced code blocks.

    Code blocks with known languages (python, r, julia, javascript, etc.)
    are treated as :attr:`~notebookllm.models.CellType.CODE` cells. Other
    language blocks become :attr:`~notebookllm.models.CellType.RAW` cells.
    """

    def load(self, source: str | Path) -> NotebookDocument:
        """Load a Markdown notebook from a file.

        Args:
            source: Path to the ``.md`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        """Load a Markdown notebook from a string.

        Args:
            content: Raw markdown content.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        cells: list[Cell] = []
        metadata: dict[str, object] = {}

        fm_match = FRONTMATTER_RE.match(content)
        if fm_match:
            try:
                metadata = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                metadata = {}
            content = content[fm_match.end():]

        last_end = 0

        for match in CODE_BLOCK_RE.finditer(content):
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            lang = match.group(1)
            code = match.group(2).strip()
            if lang in ("python", "r", "julia", "javascript", "ts", "typescript"):
                cells.append(Cell(cell_type=CellType.CODE, source=code, language=lang))
            else:
                cells.append(Cell(cell_type=CellType.RAW, source=code, language=lang))

            last_end = match.end()

        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="markdown")


class MarkdownDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to Markdown format.

    Code cells are written as fenced code blocks with language tags.
    Markdown cells are written as plain text.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to Markdown format.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The markdown content as a string.
        """
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                if cell.metadata:
                    lang = cell.language or cell.metadata.get("language", "python")
                else:
                    lang = cell.language or "python"
                parts.append(f"```{lang}")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                parts.append("```raw")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
