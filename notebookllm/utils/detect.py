"""Format detection for notebooks — extension and content sniffing."""
from __future__ import annotations

from pathlib import Path


def detect_format(filepath: Path, content: str | None = None) -> str:
    """Detect notebook format from file extension and optionally content sniffing.

    Returns: "ipynb", "quarto", "markdown", "marimo", or "percent"
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()

    if ext == ".ipynb":
        return "ipynb"
    elif ext == ".qmd":
        return "quarto"
    elif ext in (".md", ".rmd"):
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

    Returns: "percent", "marimo", "quarto", "markdown"
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

    # Fallback: treat as percent format
    return "percent"
