"""Format auto-detection and dispatch — entry points for loading and dumping notebooks.

This module provides the public functions for reading and writing notebooks:

- :func:`load_file`: Load a notebook from a file path (auto-detects format).
- :func:`dump_file`: Save a notebook to a file (auto-detects format from extension).
- :func:`loads_text`: Parse a string into a notebook (auto-detects format from content).

Each function dispatches to the appropriate format-specific loader or dumper
based on the detected format.
"""
from __future__ import annotations

from pathlib import Path

from notebookllm.models import NotebookDocument
from notebookllm.utils.detect import detect_format, detect_text_format


def load_file(filepath: str | Path) -> NotebookDocument:
    """Load a notebook from a file. Auto-detects format from the file extension.

    Supported formats (auto-detected by extension):

    - ``.ipynb`` — Jupyter Notebook
    - ``.py`` — Percent script (``# %%``) or Marimo (``@app.cell``)
    - ``.qmd`` — Quarto document
    - ``.md`` — Markdown with fenced code blocks
    - ``.rmd`` — R Markdown
    - ``.deepnote`` — Deepnote YAML project

    Args:
        filepath: Path to the notebook file.

    Returns:
        A :class:`~notebookllm.models.NotebookDocument`.

    Raises:
        ValueError: If the format cannot be detected from the extension.
    """
    filepath = Path(filepath)
    fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbLoader
        return IpynbLoader().load(filepath)
    elif fmt == "deepnote":
        from notebookllm.loaders.deepnote import DeepnoteLoader
        return DeepnoteLoader().load(filepath)
    elif fmt == "percent":
        from notebookllm.loaders.percent import PercentLoader
        return PercentLoader().load(filepath)
    elif fmt == "marimo":
        from notebookllm.loaders.marimo import MarimoLoader
        return MarimoLoader().load(filepath)
    elif fmt == "quarto":
        from notebookllm.loaders.quarto import QuartoLoader
        return QuartoLoader().load(filepath)
    elif fmt == "markdown":
        from notebookllm.loaders.markdown import MarkdownLoader
        return MarkdownLoader().load(filepath)
    elif fmt == "rmarkdown":
        from notebookllm.loaders.rmarkdown import RMarkdownLoader
        return RMarkdownLoader().load(filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def dump_file(doc: NotebookDocument, filepath: str | Path, fmt: str | None = None) -> None:
    """Dump a notebook to a file. Auto-detects format from extension or uses *fmt*.

    Args:
        doc: The notebook to serialize.
        filepath: Destination file path.
        fmt: Output format override. If ``None``, inferred from the file extension.

    Raises:
        ValueError: If the format is not supported.
    """
    filepath = Path(filepath)
    if fmt is None:
        fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbDumper
        IpynbDumper().dump(doc, filepath)
    elif fmt == "deepnote":
        from notebookllm.loaders.deepnote import DeepnoteDumper
        DeepnoteDumper().dump(doc, filepath)
    elif fmt == "percent":
        from notebookllm.loaders.percent import PercentDumper
        PercentDumper().dump(doc, filepath)
    elif fmt == "marimo":
        from notebookllm.loaders.marimo import MarimoDumper
        MarimoDumper().dump(doc, filepath)
    elif fmt == "quarto":
        from notebookllm.loaders.quarto import QuartoDumper
        QuartoDumper().dump(doc, filepath)
    elif fmt == "markdown":
        from notebookllm.loaders.markdown import MarkdownDumper
        MarkdownDumper().dump(doc, filepath)
    elif fmt == "rmarkdown":
        from notebookllm.loaders.rmarkdown import RMarkdownDumper
        RMarkdownDumper().dump(doc, filepath)
    elif fmt == "script":
        from notebookllm.loaders.script import ScriptDumper
        ScriptDumper().dump(doc, filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def loads_text(text: str, source_format: str | None = None) -> NotebookDocument:
    """Load a notebook from a string. Auto-detects format if not specified.

    Args:
        text: The raw text content to parse.
        source_format: Explicit format hint. If ``None``, format is detected
            by content sniffing (see :func:`~notebookllm.utils.detect.detect_text_format`).

    Returns:
        A :class:`~notebookllm.models.NotebookDocument`.

    Raises:
        ValueError: If the format is not supported or cannot be detected.
    """
    if source_format is None:
        source_format = detect_text_format(text)

    if source_format == "ipynb":
        from notebookllm.loaders.ipynb import IpynbLoader
        return IpynbLoader().loads(text)
    elif source_format == "deepnote":
        from notebookllm.loaders.deepnote import DeepnoteLoader
        return DeepnoteLoader().loads(text)
    elif source_format == "percent":
        from notebookllm.loaders.percent import PercentLoader
        return PercentLoader().loads(text)
    elif source_format == "marimo":
        from notebookllm.loaders.marimo import MarimoLoader
        return MarimoLoader().loads(text)
    elif source_format == "quarto":
        from notebookllm.loaders.quarto import QuartoLoader
        return QuartoLoader().loads(text)
    elif source_format == "markdown":
        from notebookllm.loaders.markdown import MarkdownLoader
        return MarkdownLoader().loads(text)
    elif source_format == "rmarkdown":
        from notebookllm.loaders.rmarkdown import RMarkdownLoader
        return RMarkdownLoader().loads(text)
    else:
        raise ValueError(f"Unsupported format: {source_format}")
