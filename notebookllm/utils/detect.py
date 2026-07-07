"""Format detection for notebooks — file-extension mapping and content sniffing.

Determines which notebook format a file or string is in by checking:

- **File extension** (for :func:`detect_format`): ``.ipynb``, ``.qmd``, ``.rmd``,
  ``.deepnote``, ``.md``, ``.py`` — maps directly to format name.
- **Content patterns** (for :func:`detect_text_format`): ``# %%`` markers,
  ``import marimo``, `````{r}```/`````{python}``` blocks, JSON structure,
  YAML structure with ``project.notebooks`` keys.

Supports automatic detection for all 8+ notebook formats.
"""
from __future__ import annotations

from pathlib import Path


def detect_format(filepath: Path, content: str | None = None) -> str:
    """Detect notebook format from a file path, optionally checking content.

    Detection priority:

    * ``.ipynb`` -> ``"ipynb"``
    * ``.qmd`` -> ``"quarto"``
    * ``.rmd`` -> ``"rmarkdown"``
    * ``.deepnote`` -> ``"deepnote"``
    * ``.md`` -> ``"markdown"``
    * ``.py`` -> marimo (if contains ``@app.cell``) or percent

    Args:
        filepath: Path to the notebook file.
        content: Optional file content for content-based disambiguation.

    Returns:
        A format string: ``"ipynb"``, ``"quarto"``, ``"rmarkdown"``,
        ``"deepnote"``, ``"markdown"``, ``"marimo"``, or ``"percent"``.

    Raises:
        ValueError: If the file extension is not recognized.
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
    """Detect notebook format from text content alone (content sniffing).

    Detection order:

    1. ``"percent"`` — if any line starts with ``# %%``
    2. ``"marimo"`` — if contains ``import marimo`` or ``@app.cell``
    3. ``"rmarkdown"`` — if contains `````{r}```
    4. ``"quarto"`` — if contains `````{python}```
    5. ``"markdown"`` — if contains `````python```
    6. ``"ipynb"`` — if content is JSON with ``cells`` and ``nbformat`` keys
    7. ``"deepnote"`` — if content is YAML with ``project.notebooks``
    8. ``"percent"`` — fallback for unrecognized text

    Args:
        content: The raw text content to sniff.

    Returns:
        A format string: ``"percent"``, ``"marimo"``, ``"rmarkdown"``,
        ``"quarto"``, ``"markdown"``, ``"ipynb"``, or ``"deepnote"``.
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
