"""R Markdown format loader/dumper — ``.Rmd`` files with R and Python code blocks.

R Markdown is a variant of Markdown used by RStudio and the ``rmarkdown``
package. Code blocks use the `````{language}``` syntax (same as Quarto)
and support R, Python, Julia, and other languages.

See: https://rmarkdown.rstudio.com

The loader distinguishes between R and Python code cells by setting
the ``language`` field in cell metadata, enabling bidirectional
conversion between R Markdown and other notebook formats.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

# Regex to match RMarkdown code blocks: ```{language} ... ```
CODE_BLOCK_RE = re.compile(r"```\{(\w+)\}(?:\s*\n)?(.*?)```", re.DOTALL)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class RMarkdownLoader(BaseLoader):
    """Load R Markdown files with embedded R and Python code blocks.

    R code blocks (`````{r}```) are stored with ``language="r"``.
    Python and other languages are recognized similarly. Unknown
    languages become :attr:`~notebookllm.models.CellType.RAW` cells.
    """

    def load(self, source: str | Path) -> NotebookDocument:
        """Load an R Markdown file from disk.

        Args:
            source: Path to the ``.Rmd`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        """Load an R Markdown notebook from a string.

        Args:
            content: Raw ``.Rmd`` content.

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

            lang = match.group(1).lower()
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
                cells.append(Cell(
                    cell_type=CellType.RAW,
                    source=code,
                    language=lang,
                    metadata={"language": lang},
                ))

            last_end = match.end()

        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="rmarkdown")


class RMarkdownDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to R Markdown format.

    Produces ``.Rmd`` output with `````{language}``` fenced code blocks.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to R Markdown format.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The ``.Rmd`` content as a string.
        """
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                if cell.metadata:
                    lang = cell.language or cell.metadata.get("language", "python")
                else:
                    lang = cell.language or "python"
                parts.append(f"```{{{lang}}}")
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
