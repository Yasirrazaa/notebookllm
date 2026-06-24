"""Core data models for notebookllm — universal notebook representation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from notebookllm.utils.tokenizer import NotebookTokenReport


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

    def _to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "output_type": self.output_type,
            "content": self.content,
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> CellOutput:
        return cls(
            output_type=data["output_type"],
            content=data.get("content", ""),
            name=data.get("name"),
        )


@dataclass
class Cell:
    """Universal cell representation — format-agnostic with Deepnote-compatible fields."""

    cell_type: CellType
    source: str
    execution_count: int | None = None
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    cell_id: str | None = None
    # --- Expanded fields for format-agnostic CIR ---
    language: str | None = None       # "python", "r", "sql", "julia", etc.
    block_type: str | None = None     # Format-specific: "sql", "visualization", "input", etc.
    block_group: str | None = None    # Deepnote blockGroup UUID
    content_hash: str | None = None   # Deepnote SHA-256 contentHash
    sorting_key: str | None = None    # Deepnote base-36 ordering key

    def _to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "cell_type": self.cell_type.value,
            "source": self.source,
        }
        if self.execution_count is not None:
            d["execution_count"] = self.execution_count
        if self.outputs:
            d["outputs"] = [o._to_dict() for o in self.outputs]
        if self.metadata:
            d["metadata"] = self.metadata
        if self.cell_id is not None:
            d["cell_id"] = self.cell_id
        if self.language is not None:
            d["language"] = self.language
        if self.block_type is not None:
            d["block_type"] = self.block_type
        if self.block_group is not None:
            d["block_group"] = self.block_group
        if self.content_hash is not None:
            d["content_hash"] = self.content_hash
        if self.sorting_key is not None:
            d["sorting_key"] = self.sorting_key
        return d

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Cell:
        outputs_data = data.get("outputs", [])
        outputs = [CellOutput._from_dict(o) for o in outputs_data]
        return cls(
            cell_type=CellType(data["cell_type"]),
            source=data.get("source", ""),
            execution_count=data.get("execution_count"),
            outputs=outputs,
            metadata=data.get("metadata", {}),
            cell_id=data.get("cell_id"),
            language=data.get("language"),
            block_type=data.get("block_type"),
            block_group=data.get("block_group"),
            content_hash=data.get("content_hash"),
            sorting_key=data.get("sorting_key"),
        )


@dataclass
class NotebookDocument:
    """Universal notebook representation — format-agnostic."""

    cells: list[Cell] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    kernel_name: str | None = None
    language: str = "python"
    source_format: str | None = None

    def _cir_version(self) -> int:
        """Return the CIR schema version for serialization."""
        return 2  # v1: original fields; v2: added language, block_type, block_group, content_hash, sorting_key

    def to_json(self) -> str:
        """Serialize NotebookDocument to JSON string."""
        data = self._to_dict()
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> NotebookDocument:
        """Deserialize JSON string → NotebookDocument. Version-tolerant."""
        data = json.loads(json_str)
        return cls._from_dict(data)

    def _to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "_cir_version": self._cir_version(),
            "cells": [cell._to_dict() for cell in self.cells],
            "metadata": self.metadata,
            "kernel_name": self.kernel_name,
            "language": self.language,
            "source_format": self.source_format,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> NotebookDocument:
        """Restore from dict. Ignores unknown keys for forward compat."""
        cells_data = data.get("cells", [])
        cells = [Cell._from_dict(c) for c in cells_data]
        return cls(
            cells=cells,
            metadata=data.get("metadata", {}),
            kernel_name=data.get("kernel_name"),
            language=data.get("language", "python"),
            source_format=data.get("source_format"),
        )

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

    def token_breakdown(self, mode: OutputMode = OutputMode.MINIMAL) -> NotebookTokenReport:
        """Get token usage breakdown for this notebook.

        Parameters
        ----------
        mode:
            Output verbosity mode. Defaults to ``MINIMAL``.

        Returns
        -------
        NotebookTokenReport
            A report with per-cell and total token counts.
        """
        from notebookllm.utils.tokenizer import tokenize_notebook

        return tokenize_notebook(self, mode=mode.value)
