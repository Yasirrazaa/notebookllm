"""Format auto-detection and dispatch — the entry point for loading/dumping notebooks."""
from __future__ import annotations

from pathlib import Path

from notebookllm.utils.detect import detect_format, detect_text_format
from notebookllm.models import NotebookDocument


def load_file(filepath: str | Path) -> NotebookDocument:
    """Load a notebook from file. Auto-detects format from extension."""
    filepath = Path(filepath)
    fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbLoader
        return IpynbLoader().load(filepath)
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
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def dump_file(doc: NotebookDocument, filepath: str | Path, fmt: str | None = None) -> None:
    """Dump a notebook to file. Auto-detects format from extension or uses fmt."""
    filepath = Path(filepath)
    if fmt is None:
        fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbDumper
        IpynbDumper().dump(doc, filepath)
    elif fmt == "percent":
        from notebookllm.loaders.percent import PercentDumper
        PercentDumper().dump(doc, filepath)
    elif fmt == "quarto":
        from notebookllm.loaders.quarto import QuartoDumper
        QuartoDumper().dump(doc, filepath)
    elif fmt == "markdown":
        from notebookllm.loaders.markdown import MarkdownDumper
        MarkdownDumper().dump(doc, filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def loads_text(text: str, source_format: str | None = None) -> NotebookDocument:
    """Load a notebook from text content. Auto-detects format if not specified."""
    if source_format is None:
        source_format = detect_text_format(text)

    if source_format == "ipynb":
        from notebookllm.loaders.ipynb import IpynbLoader
        return IpynbLoader().loads(text)
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
    else:
        raise ValueError(f"Unsupported format: {source_format}")
