"""Input/output validation and atomic write utilities."""
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
    """A single validation issue found in a notebook."""
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"
    cell_index: int | None = None


@dataclass
class ValidationReport:
    """Report from a notebook validation run."""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        if self.is_valid and not self.warnings:
            return "Validation passed."
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return f"Validation found {', '.join(parts)}."

    def format_text(self) -> str:
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
    """Write content to file atomically using a temp file + rename.

    Writes to a temporary file in the same directory (same filesystem),
    then renames, which is atomic on POSIX and most local filesystems.
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
    """Check all cells have valid cell_type."""
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
    """Check that non-code cells have no outputs (a common corruption signal)."""
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
    """Warn on empty cells (zero-length source)."""
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
    """Run all validation checks on a NotebookDocument.

    Returns a ValidationReport with errors and warnings.
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
    """Validate that filepath exists and is a file."""
    filepath = Path(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(f"Expected a file, got directory: {filepath}")
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return filepath


def validate_output_format(fmt: str) -> str:
    """Validate output format string."""
    valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown", "script", "deepnote"}
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
