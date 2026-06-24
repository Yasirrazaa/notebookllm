"""Quarto format loader/dumper — .qmd files."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
CODE_CHUNK_RE = re.compile(r"```\{(\w+)\}\s*\n(.*?)```", re.DOTALL)


class QuartoLoader(BaseLoader):
    """Load quarto .qmd files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells: list[Cell] = []
        metadata: dict[str, object] = {}

        # Parse YAML frontmatter
        fm_match = FRONTMATTER_RE.match(content)
        if fm_match:
            try:
                metadata = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                metadata = {}
            content = content[fm_match.end():]

        # Find all code chunks and markdown between them
        last_end = 0
        for match in CODE_CHUNK_RE.finditer(content):
            # Markdown before this code chunk
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            # The code chunk
            lang = match.group(1)
            raw_code = match.group(2)

            # Extract quarto cell options (#| key: value) from the top of the code block
            cell_options = {}
            code_lines = raw_code.split("\n")
            cleaned_lines = []
            for cline in code_lines:
                opt_match = re.match(r"^\s*#\|\s+([\w-]+)\s*:\s*(.+)$", cline)
                if opt_match:
                    cell_options[opt_match.group(1)] = opt_match.group(2).strip()
                else:
                    cleaned_lines.append(cline)
            code = "\n".join(cleaned_lines).strip()

            cell_metadata: dict[str, object] = {}
            if cell_options:
                cell_metadata["quarto_options"] = cell_options
            cell_metadata["language"] = lang

            if lang in ("python", "r", "julia"):
                cells.append(Cell(cell_type=CellType.CODE, source=code, language=lang, metadata=cell_metadata))
            else:
                cells.append(Cell(cell_type=CellType.RAW, source=code, language=lang, metadata=cell_metadata))

            last_end = match.end()

        # Trailing markdown
        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="quarto")


class QuartoDumper(BaseDumper):
    """Dump to quarto .qmd format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []

        # YAML frontmatter
        if doc.metadata:
            parts.append("---")
            parts.append(yaml.dump(doc.metadata, default_flow_style=False).strip())
            parts.append("---")
            parts.append("")

        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                lang = cell.language or (cell.metadata.get("language", "python") if cell.metadata else "python")
                parts.append(f"```{{{lang}}}")
                # Preserve cell options if present
                if cell.metadata and "quarto_options" in cell.metadata:
                    for k, v in cell.metadata["quarto_options"].items():
                        parts.append(f"#| {k}: {v}")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                lang = cell.metadata.get("language", "raw") if cell.metadata else "raw"
                parts.append(f"```{{{lang}}}")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
