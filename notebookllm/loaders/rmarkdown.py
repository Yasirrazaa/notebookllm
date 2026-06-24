"""R Markdown format loader/dumper — .Rmd files with R and Python code blocks."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

# Regex to match RMarkdown code blocks: ```{language} ... ```
# Captures the language inside curly braces and the code content.
CODE_BLOCK_RE = re.compile(r"```\{(\w+)\}(?:\s*\n)?(.*?)```", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class RMarkdownLoader(BaseLoader):
    """Load RMarkdown files with embedded R and Python code blocks."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells: list[Cell] = []
        metadata: dict[str, object] = {}

        # Parse YAML frontmatter (same as markdown loader)
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
            lang = match.group(1).lower()  # normalize to lowercase
            code = match.group(2).strip()
            if lang in ("r", "python"):
                cells.append(
                    Cell(
                        cell_type=CellType.CODE,
                        source=code,
                        language=lang,
                        metadata={"language": lang},
                    )
                )
            else:
                # Treat unknown languages as raw cells
                cells.append(Cell(
                    cell_type=CellType.RAW,
                    source=code,
                    language=lang,
                    metadata={"language": lang},
                ))

            last_end = match.end()

        # Trailing markdown
        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="rmarkdown")


class RMarkdownDumper(BaseDumper):
    """Dump to RMarkdown format with embedded code blocks."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                lang = cell.language or (cell.metadata.get("language", "python") if cell.metadata else "python")
                parts.append(f"```{{{lang}}}")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                # For raw cells, we output as a code block with no language? Or as raw?
                # We'll follow the markdown dumper's approach for raw.
                parts.append("```raw")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result