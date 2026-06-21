"""Input/output validation utilities."""
from __future__ import annotations

from pathlib import Path

from notebookllm.models import CellType


def validate_filepath(filepath: str | Path) -> Path:
    """Validate that filepath exists and is a file."""
    filepath = Path(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(f"Expected a file, got directory: {filepath}")
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return filepath


def validate_output_format(fmt: str) -> str:
    """Validate output format string."""
    valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown"}
    if fmt not in valid:
        raise ValueError(f"Invalid format '{fmt}'. Must be one of: {valid}")
    return fmt


def validate_cell_index(index: int, total: int) -> int:
    """Validate cell index is within range."""
    if index < 0 or index >= total:
        raise IndexError(f"Cell index {index} out of range (0-{total - 1})")
    return index


def validate_cell_type(cell_type: str) -> CellType:
    """Validate and convert cell type string to CellType enum."""
    try:
        return CellType(cell_type)
    except ValueError:
        raise ValueError(
            f"Invalid cell type '{cell_type}'. Must be one of: code, markdown, raw"
        ) from None
