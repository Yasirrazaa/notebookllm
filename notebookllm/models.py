"""Core data models for notebookllm — universal notebook representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
class CellType(Enum):
    """Type of notebook cell."""

    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"


class OutputMode(Enum):
    """LLM output verbosity mode."""

    MINIMAL = "minimal"  # Cell markers + source only
    STANDARD = "standard"  # Cell markers + source + metadata (type, exec count)
    FULL = "full"  # Cell markers + source + metadata + outputs


@dataclass
class CellOutput:
    """Represents output from a cell execution."""

    output_type: str  # "stream", "execute_result", "display_data", "error"
    content: str | dict  # Text for streams, data dict for display
    name: str | None = None  # "stdout" or "stderr" for stream type


@dataclass
class Cell:
    """Universal cell representation."""

    cell_type: CellType
    source: str
    execution_count: int | None = None
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    cell_id: str | None = None


@dataclass
class NotebookDocument:
    """Universal notebook representation — format-agnostic."""

    cells: list[Cell] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    kernel_name: str | None = None
    language: str = "python"
    source_format: str | None = None

    @classmethod
    def from_file(cls, filepath: str | Path) -> NotebookDocument:
        """Load a notebook from file. Auto-detects format."""
        from notebookllm.loaders import load_file

        return load_file(filepath)

    def to_file(self, filepath: str | Path, fmt: str | None = None) -> None:
        """Save notebook to file. Auto-detects format from extension or uses fmt."""
        from notebookllm.loaders import dump_file

        dump_file(self, filepath, fmt=fmt)

    def to_text(self, mode: OutputMode = OutputMode.MINIMAL) -> str:
        """Convert to LLM-optimized text."""
        from notebookllm.converters.llm_optimizer import LLMOptimizer

        optimizer = LLMOptimizer(mode=mode)
        return optimizer.optimize(self)

    @classmethod
    def from_text(cls, text: str, source_format: str | None = None) -> NotebookDocument:
        """Parse text content into NotebookDocument.

        If source_format is None, attempts auto-detection by content sniffing.
        """
        from notebookllm.loaders import loads_text

        return loads_text(text, source_format=source_format)

    def filter_cells(
        self, cell_type: CellType | None = None, query: str | None = None
    ) -> list[Cell]:
        """Filter cells by type and/or content query."""
        results = self.cells
        if cell_type is not None:
            results = [c for c in results if c.cell_type == cell_type]
        if query is not None:
            q = query.lower()
            results = [c for c in results if q in c.source.lower()]
        return results

    def get_cell(self, index: int) -> Cell:
        """Get cell by index. Raises IndexError if out of range."""
        if index < 0 or index >= len(self.cells):
            raise IndexError(f"Cell index {index} out of range (0-{len(self.cells) - 1})")
        return self.cells[index]

    def add_cell(self, cell: Cell, position: int | None = None) -> None:
        """Add a cell at the given position, or append if None."""
        if position is None:
            self.cells.append(cell)
        else:
            if position < 0 or position > len(self.cells):
                raise IndexError(f"Position {position} out of range (0-{len(self.cells)})")
            self.cells.insert(position, cell)

    def edit_cell(self, index: int, source: str, cell_type: CellType | None = None) -> None:
        """Edit a cell's source and optionally change its type."""
        cell = self.get_cell(index)
        cell.source = source
        if cell_type is not None:
            cell.cell_type = cell_type

    def delete_cell(self, index: int) -> None:
        """Delete a cell by index."""
        self.get_cell(index)  # Validate index exists
        self.cells.pop(index)

    def move_cell(self, from_index: int, to_index: int) -> None:
        """Move a cell from one position to another."""
        cell = self.get_cell(from_index)
        self.cells.pop(from_index)
        if to_index > len(self.cells):
            to_index = len(self.cells)
        self.cells.insert(to_index, cell)

    def search(self, query: str, cell_type: CellType | None = None) -> list[tuple[int, Cell]]:
        """Search cells by content (case-insensitive substring match).

        Returns list of (index, cell) tuples for cells containing query.
        """
        q = query.lower()
        results = []
        for i, cell in enumerate(self.cells):
            if cell_type is not None and cell.cell_type != cell_type:
                continue
            if q in cell.source.lower():
                results.append((i, cell))
        return results
