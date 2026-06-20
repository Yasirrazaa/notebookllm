"""Markdown format loader/dumper — .md files with ```python blocks."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellType, NotebookDocument

CODE_BLOCK_RE = re.compile(r"```(\w+)\s*\n(.*?)```", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownLoader(BaseLoader):
    """Load markdown files with embedded code blocks."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []
        metadata = {}

        # Parse YAML frontmatter (same as quarto loader)
        fm_match = FRONTMATTER_RE.match(content)
        if fm_match:
            try:
                metadata = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                metadata = {}
            content = content[fm_match.end():]

        last_end = 0

        for match in CODE_BLOCK_RE.finditer(content):
            # Markdown before this code block
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            # The code block
            lang = match.group(1)
            code = match.group(2).strip()
            if lang in ("python", "r", "julia", "javascript", "ts", "typescript"):
                cells.append(Cell(cell_type=CellType.CODE, source=code))
            else:
                cells.append(Cell(cell_type=CellType.RAW, source=code))

            last_end = match.end()

        # Trailing markdown
        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="markdown")


class MarkdownDumper(BaseDumper):
    """Dump to markdown format with embedded code blocks."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                lang = cell.metadata.get("language", "python") if cell.metadata else "python"
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
