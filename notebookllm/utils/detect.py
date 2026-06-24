"""Format detection for notebooks — extension and content sniffing."""
from __future__ import annotations

from pathlib import Path


def detect_format(filepath: Path, content: str | None = None) -> str:
    """Detect notebook format from file extension and optionally content sniffing.

    Returns: "ipynb", "quarto", "markdown", "marimo", "deepnote", or "percent"
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()

    if ext == ".ipynb":
        return "ipynb"
    elif ext == ".qmd":
        return "quarto"
    elif ext == ".rmd":
        return "rmarkdown"
    elif ext == ".deepnote":
        return "deepnote"
    elif ext == ".md":
        return "markdown"
    elif ext == ".py":
        if content is None and filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                content = ""
        if content and ("import marimo" in content or "@app.cell" in content):
            return "marimo"
        return "percent"
    else:
        raise ValueError(f"Cannot detect format for {filepath}")


def detect_text_format(content: str) -> str:
    """Detect format from text content alone (content sniffing).

    Returns: "percent", "marimo", "quarto", "markdown", "ipynb"
    """
    lines = content.splitlines()

    # Check for percent format markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# %%"):
            return "percent"

    # Check for marimo markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import marimo") or stripped.startswith("@app.cell"):
            return "marimo"

    # Check for R Markdown markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```{r}"):
            return "rmarkdown"

    # Check for quarto markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```{python}"):
            return "quarto"

    # Check for markdown code blocks
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```python"):
            return "markdown"

    # Check for ipynb JSON content (must be after structured formats)
    if content.strip().startswith("{"):
        try:
            import json
            obj = json.loads(content)
            if "cells" in obj and "nbformat" in obj:
                return "ipynb"
        except Exception:
            pass

    # Check for Deepnote YAML format
    if content.strip().startswith("metadata:") or "project:\n  notebooks:" in content:
        try:
            import yaml
            obj = yaml.safe_load(content)
            if isinstance(obj, dict) and "project" in obj and "notebooks" in obj["project"]:
                return "deepnote"
        except Exception:
            pass

    # Fallback: treat as percent format
    return "percent"
