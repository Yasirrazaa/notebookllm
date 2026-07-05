"""Input/output validation and atomic write utilities.

Provides:

- :class:`ValidationReport` and related validators for notebook integrity checks.
- :func:`atomic_write` for crash-safe file writing.
- Legacy validation functions (``validate_filepath``, ``validate_output_format``,
  ``validate_cell_index``, ``validate_cell_type``) for input sanitization.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from notebookllm.models import CellType, NotebookDocument

# ------------------------------------------------------------------
# Validation report
# ------------------------------------------------------------------


@dataclass
class ValidationError:
    """A single validation issue found in a notebook.

    Attributes:
        field: The field or property that failed validation
            (e.g. ``"cell_type"``, ``"outputs"``, ``"source"``).
        message: A human-readable description of the issue.
        severity: Either ``"error"`` (blocks usage) or ``"warning"``
            (informational).
        cell_index: Index of the offending cell, or ``None`` if the
            issue is at the notebook level.
    """

    field: str
    message: str
    severity: str = "error"
    cell_index: int | None = None


@dataclass
class ValidationReport:
    """Report from a notebook validation run.

    Attributes:
        errors: List of blocking issues.
        warnings: List of non-blocking issues.
    """

    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """``True`` if there are no errors (warnings are allowed)."""
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        """A one-line summary of the validation results.

        Returns:
            ``"Validation passed."`` if clean, or a count of errors/warnings.
        """
        if self.is_valid and not self.warnings:
            return "Validation passed."
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return f"Validation found {', '.join(parts)}."

    def format_text(self) -> str:
        """Format the report as human-readable text.

        Returns:
            Multi-line string with ``ERROR`` and ``WARNING`` lines.
        """
        lines = []
        for err in self.errors:
            loc = f"cell[{err.cell_index}] " if err.cell_index is not None else ""
            lines.append(f"  ERROR   {loc}{err.field}: {err.message}")
        for warn in self.warnings:
            loc = f"cell[{warn.cell_index}] " if warn.cell_index is not None else ""
            lines.append(f"  WARNING {loc}{warn.field}: {warn.message}")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Atomic write
# ------------------------------------------------------------------


def atomic_write(filepath: str | Path, content: str) -> None:
    """Write content to a file atomically using a temp file + rename.

    Writes to a temporary file in the same directory (same filesystem),
    then renames — which is atomic on POSIX and most local filesystems.

    Args:
        filepath: Destination file path.
        content: Content to write.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Use a .tmp suffix in the same directory so rename is atomic
    tmp_path = filepath.with_name(f".{filepath.name}.tmp")

    # Write to temp file
    tmp_path.write_text(content, encoding="utf-8")

    # On Windows, destination must not exist for os.replace — remove first
    if os.name == "nt" and filepath.exists():
        filepath.unlink()

    os.replace(str(tmp_path), str(filepath))


# ------------------------------------------------------------------
# Notebook validation
# ------------------------------------------------------------------


def validate_cell_types(doc: NotebookDocument) -> list[ValidationError]:
    """Check that all cells have a valid :class:`~notebookllm.models.CellType`.

    Args:
        doc: The notebook to validate.

    Returns:
        List of :class:`ValidationError` for cells with invalid types.
    """
    errors: list[ValidationError] = []
    for i, cell in enumerate(doc.cells):
        if not isinstance(cell.cell_type, CellType):
            errors.append(ValidationError(
                field="cell_type",
                message=f"Invalid cell_type: {cell.cell_type!r}",
                cell_index=i,
            ))
    return errors


def validate_no_orphan_outputs(doc: NotebookDocument) -> list[ValidationError]:
    """Check that non-code cells have no outputs (a common corruption signal).

    Args:
        doc: The notebook to validate.

    Returns:
        List of :class:`ValidationError` warnings for non-code cells
        that have outputs attached.
    """
    errors: list[ValidationError] = []
    for i, cell in enumerate(doc.cells):
        if cell.cell_type != CellType.CODE and cell.outputs:
            errors.append(ValidationError(
                field="outputs",
                message=f"Non-code cell ({cell.cell_type.value}) has {len(cell.outputs)} output(s)",
                severity="warning",
                cell_index=i,
            ))
    return errors


def validate_no_empty_cells(doc: NotebookDocument) -> list[ValidationError]:
    """Warn on empty cells (zero-length source text).

    Args:
        doc: The notebook to validate.

    Returns:
        List of :class:`ValidationError` warnings for empty cells.
    """
    warnings: list[ValidationError] = []
    for i, cell in enumerate(doc.cells):
        if not cell.source.strip():
            warnings.append(ValidationError(
                field="source",
                message="Cell is empty",
                severity="warning",
                cell_index=i,
            ))
    return warnings


def validate_notebook(doc: NotebookDocument) -> ValidationReport:
    """Run all validation checks on a :class:`~notebookllm.models.NotebookDocument`.

    Runs the following checks:

    - :func:`validate_cell_types` — errors for invalid cell types.
    - :func:`validate_no_orphan_outputs` — warnings for non-code cells with outputs.
    - :func:`validate_no_empty_cells` — warnings for empty cells.

    Args:
        doc: The notebook to validate.

    Returns:
        A :class:`ValidationReport` with all errors and warnings.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    errors.extend(validate_cell_types(doc))
    warnings.extend(validate_no_orphan_outputs(doc))
    warnings.extend(validate_no_empty_cells(doc))

    return ValidationReport(errors=errors, warnings=warnings)


# ------------------------------------------------------------------
# Legacy public API (unchanged signatures)
# ------------------------------------------------------------------


def validate_filepath(filepath: str | Path) -> Path:
    """Validate that a filepath exists and is a file (not a directory).

    Args:
        filepath: Path to validate.

    Returns:
        The resolved :class:`Path`.

    Raises:
        IsADirectoryError: If *filepath* is a directory.
        FileNotFoundError: If *filepath* does not exist.
    """
    filepath = Path(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(f"Expected a file, got directory: {filepath}")
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return filepath


def validate_output_format(fmt: str) -> str:
    """Validate that a format string is one of the supported output formats.

    Args:
        fmt: Format string to validate.

    Returns:
        The validated format string.

    Raises:
        ValueError: If *fmt* is not a supported format.
    """
    valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown", "script", "deepnote"}
    if fmt not in valid:
        raise ValueError(f"Invalid format '{fmt}'. Must be one of: {valid}")
    return fmt


def validate_cell_index(index: int, total: int) -> int:
    """Validate that a cell index is within the valid range.

    Args:
        index: Zero-based cell index.
        total: Total number of cells.

    Returns:
        The validated index.

    Raises:
        IndexError: If *index* is out of range.
    """
    if index < 0 or index >= total:
        raise IndexError(f"Cell index {index} out of range (0-{total - 1})")
    return index


def validate_cell_type(cell_type: str) -> CellType:
    """Validate and convert a cell type string to a :class:`~notebookllm.models.CellType` enum.

    Args:
        cell_type: String like ``"code"``, ``"markdown"``, or ``"raw"``.

    Returns:
        The corresponding :class:`~notebookllm.models.CellType`.

    Raises:
        ValueError: If *cell_type* is not one of the valid values.
    """
    try:
        return CellType(cell_type)
    except ValueError:
        raise ValueError(
            f"Invalid cell type '{cell_type}'. Must be one of: code, markdown, raw"
        ) from None
