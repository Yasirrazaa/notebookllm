"""Core data models for notebookllm — universal notebook representation.

Defines a format-agnostic intermediate representation (CIR) for notebooks.
Every format loader and dumper converts to/from these models, providing a
single, type-safe API across all supported notebook formats.

Key classes:
    - :class:`NotebookDocument`: Top-level notebook container.
    - :class:`Cell`: A single cell (code, markdown, or raw).
    - :class:`CellOutput`: Execution output from a code cell.
    - :class:`CellType`: Enum distinguishing code / markdown / raw cells.
    - :class:`OutputMode`: AI Agent text verbosity levels.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from notebookllm.utils.tokenizer import NotebookTokenReport


class CellType(Enum):
    """Type of a notebook cell.

    Each cell in a notebook is one of these three types:

    - ``CODE``: Executable code cell (Python, R, Julia, SQL, etc.)
    - ``MARKDOWN``: Formatted text / documentation cell.
    - ``RAW``: Unformatted text (passthrough, not executed).

    Usage::

        >>> CellType.CODE
        <CellType.CODE: 'code'>
        >>> CellType("markdown")
        <CellType.MARKDOWN: 'markdown'>
    """

    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"


class OutputMode(Enum):
    """AI Agent output verbosity mode for :meth:`NotebookDocument.to_text`.

    Controls how much detail is included in the Agent-optimized plain-text
    representation of a notebook.

    Levels (increasing verbosity):

    ``MINIMAL``
        Cell markers (``# %% [type]``) + source code only.
        Cleanest for Agent input — ideal for high-level analysis.
    ``STANDARD``
        Adds execution count and cell metadata tags — useful for
        understanding notebook execution history.
    ``FULL``
        Adds cell execution outputs (stdout, stderr, rich display data,
        error tracebacks) — complete picture of notebook state.
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


@dataclass
class CellOutput:
    """Represents output from a single code-cell execution.

    Stores one piece of output — a stream chunk, a rich display result,
    or an error traceback.

    Attributes:
        output_type: The kind of output (``"stream"``, ``"execute_result"``,
            ``"display_data"``, or ``"error"``).
        content: The output content. For stream output this is plain text.
            For ``execute_result`` / ``display_data`` it may be a MIME-bundle
            dict (e.g. ``{"text/plain": "...", "image/png": "..."}``).
        name: Stream name — ``"stdout"`` or ``"stderr"``. Only set when
            ``output_type == "stream"``.
    """

    output_type: str
    content: str | dict
    name: str | None = None

    def _to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        d: dict[str, Any] = {
            "output_type": self.output_type,
            "content": self.content,
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> CellOutput:
        """Restore a CellOutput from a previously serialized dict.

        Args:
            data: Dict produced by :meth:`_to_dict`.

        Returns:
            A new CellOutput instance.
        """
        return cls(
            output_type=data["output_type"],
            content=data.get("content", ""),
            name=data.get("name"),
        )


@dataclass
class Cell:
    """Universal cell representation — format-agnostic.

    A single notebook cell, storing its type, source code, execution
    metadata, and optional format-specific fields (e.g. Deepnote block
    metadata, language tag).

    This is the building block of :class:`NotebookDocument`. Every format
    loader produces ``Cell`` instances and every dumper consumes them.

    Attributes:
        cell_type: Whether this is code, markdown, or raw.
        source: The cell's text content (code or markdown).
        execution_count: Execution counter (``None`` if never run).
        outputs: List of :class:`CellOutput` objects (code cells only).
        metadata: Arbitrary key-value metadata (tags, cell-level options).
        cell_id: Unique cell identifier (UUID string), auto-generated when needed.
        language: Programming language (e.g. ``"python"``, ``"r"``, ``"sql"``, ``"julia"``).
        block_type: Format-specific block type (Deepnote: sql, visualization, input, etc.).
        block_group: Deepnote ``blockGroup`` UUID for grouped blocks.
        content_hash: Deepnote SHA-256 content hash (first 16 hex chars).
        sorting_key: Deepnote base-36 sorting key for block ordering.
    """

    cell_type: CellType
    source: str
    execution_count: int | None = None
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    cell_id: str | None = None
    # --- Expanded fields for format-agnostic CIR ---
    language: str | None = None
    block_type: str | None = None
    block_group: str | None = None
    content_hash: str | None = None
    sorting_key: str | None = None

    def _to_dict(self) -> dict[str, Any]:
        """Serialize this cell to a JSON-compatible dict.

        Only fields that are set (not ``None``) are included, keeping
        the serialized representation compact.
        """
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
        """Restore a Cell from a previously serialized dict.

        Args:
            data: Dict produced by :meth:`_to_dict`.

        Returns:
            A new Cell instance.
        """
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
    """Universal notebook representation — format-agnostic.

    The central data structure of notebookllm. Every format loader
    produces a ``NotebookDocument`` and every dumper consumes one.

    ``NotebookDocument`` provides the public API for reading, editing,
    searching, converting, and token-analyzing notebooks.

    Attributes:
        cells: Ordered list of :class:`Cell` objects.
        metadata: Notebook-level metadata (kernel spec, language info, Deepnote settings, etc.).
        kernel_name: Name of the Jupyter kernel (e.g. ``"python3"``).
        language: Primary language (``"python"``, ``"r"``). Defaults to ``"python"``.
        source_format: Format loaded from or dumped to (``"ipynb"``, ``"quarto"``, ``"marimo"``).
    """

    cells: list[Cell] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    kernel_name: str | None = None
    language: str = "python"
    source_format: str | None = None

    def _cir_version(self) -> int:
        """Return the CIR schema version for serialization.

        History:

        - **v1**: Original fields (cells, metadata, kernel_name, etc.)
        - **v2**: Added ``language``, ``block_type``, ``block_group``,
          ``content_hash``, ``sorting_key`` to Cell.
        """
        return 2

    def to_json(self) -> str:
        """Serialize the notebook to a JSON string.

        The output includes a ``_cir_version`` field for forward-compatible
        deserialization.

        Returns:
            Indented JSON string.
        """
        data = self._to_dict()
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> NotebookDocument:
        """Deserialize a JSON string back into a NotebookDocument.

        Version-tolerant — unknown keys are silently ignored so newer
        serialized documents can be read by older code.

        Args:
            json_str: A JSON string produced by :meth:`to_json`.

        Returns:
            A new NotebookDocument instance.
        """
        data = json.loads(json_str)
        return cls._from_dict(data)

    def _to_dict(self) -> dict[str, Any]:
        """Convert the notebook to a JSON-serializable dict."""
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
        """Restore a NotebookDocument from a dict.

        Ignores unknown keys for forward compatibility.

        Args:
            data: Dict produced by :meth:`_to_dict` (or a newer version).

        Returns:
            A new NotebookDocument instance.
        """
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
        """Load a notebook from a file. Auto-detects format.

        This is a convenience wrapper around :func:`notebookllm.load_file`.

        Args:
            filepath: Path to the notebook file.

        Returns:
            A NotebookDocument with the loaded content.

        Raises:
            ValueError: If the format cannot be detected from the file
                extension or content.
        """
        from notebookllm.loaders import load_file

        return load_file(filepath)

    def to_file(self, filepath: str | Path, fmt: str | None = None) -> None:
        """Save the notebook to a file.

        Auto-detects the output format from the file extension unless
        ``fmt`` is explicitly provided.

        Args:
            filepath: Destination file path.
            fmt: Output format override (e.g. ``"ipynb"``). If ``None``, inferred from extension.
        """
        from notebookllm.loaders import dump_file

        dump_file(self, filepath, fmt=fmt)

    def to_text(
        self, mode: OutputMode = OutputMode.MINIMAL, *, max_tokens: int | None = None
    ) -> str:
        """Convert the notebook to Agent-optimized plain text.

        The output format uses ``# %% [type]`` markers for cell boundaries.
        The verbosity is controlled by the ``mode`` parameter.

        Args:
            mode: Output verbosity. Defaults to :attr:`OutputMode.MINIMAL`.
            max_tokens: Token budget for token-budget mode (drops lowest-priority cells).

        Returns:
            Plain text representation of the notebook.
        """
        from notebookllm.converters.llm_optimizer import LLMOptimizer

        optimizer = LLMOptimizer(mode=mode, max_tokens=max_tokens)
        return optimizer.optimize(self)

    @classmethod
    def from_text(cls, text: str, source_format: str | None = None) -> NotebookDocument:
        """Parse plain text into a NotebookDocument.

        When ``source_format`` is ``None``, the format is auto-detected
        by content sniffing (see :func:`notebookllm.utils.detect.detect_text_format`).

        Args:
            text: The plain text content to parse.
            source_format: Explicit format hint or ``None`` for auto-detect.

        Returns:
            A new NotebookDocument.
        """
        from notebookllm.loaders import loads_text

        return loads_text(text, source_format=source_format)

    def filter_cells(
        self, cell_type: CellType | None = None, query: str | None = None
    ) -> list[Cell]:
        """Filter cells by type and/or content query.

        Args:
            cell_type: If set, only return cells of this type.
            query: If set, only return cells whose source contains this string (case-insensitive).

        Returns:
            Filtered list of :class:`Cell` objects.
        """
        results = self.cells
        if cell_type is not None:
            results = [c for c in results if c.cell_type == cell_type]
        if query is not None:
            q = query.lower()
            results = [c for c in results if q in c.source.lower()]
        return results

    def get_cell(self, index: int) -> Cell:
        """Get a cell by its index.

        Args:
            index: Zero-based cell index.

        Returns:
            The :class:`Cell` at that index.

        Raises:
            IndexError: If ``index`` is out of range.
        """
        if index < 0 or index >= len(self.cells):
            raise IndexError(f"Cell index {index} out of range (0-{len(self.cells) - 1})")
        return self.cells[index]

    def add_cell(self, cell: Cell, position: int | None = None) -> None:
        """Add a cell to the notebook.

        Args:
            cell: The :class:`Cell` to add.
            position: Insertion index. If ``None``, the cell is appended at the end.

        Raises:
            IndexError: If ``position`` is out of range.
        """
        if position is None:
            self.cells.append(cell)
        else:
            if position < 0 or position > len(self.cells):
                raise IndexError(f"Position {position} out of range (0-{len(self.cells)})")
            self.cells.insert(position, cell)

    def edit_cell(self, index: int, source: str, cell_type: CellType | None = None) -> None:
        """Edit a cell's source and optionally change its type.

        Args:
            index: Index of the cell to edit.
            source: New source text.
            cell_type: If set, change the cell's type.

        Raises:
            IndexError: If ``index`` is out of range.
        """
        cell = self.get_cell(index)
        cell.source = source
        if cell_type is not None:
            cell.cell_type = cell_type

    def delete_cell(self, index: int) -> None:
        """Delete a cell by index.

        Args:
            index: Index of the cell to remove.

        Raises:
            IndexError: If ``index`` is out of range.
        """
        self.get_cell(index)  # Validate index exists
        self.cells.pop(index)

    def move_cell(self, from_index: int, to_index: int) -> None:
        """Move a cell from one position to another.

        Args:
            from_index: Current index of the cell.
            to_index: Target index. If beyond the end, the cell is placed at the end.

        Raises:
            IndexError: If ``from_index`` is out of range.
        """
        cell = self.get_cell(from_index)
        self.cells.pop(from_index)
        if to_index > len(self.cells):
            to_index = len(self.cells)
        self.cells.insert(to_index, cell)

    def search(self, query: str, cell_type: CellType | None = None) -> list[tuple[int, Cell]]:
        """Search cells by content (case-insensitive substring match).

        Args:
            query: The search string.
            cell_type: If set, only search cells of this type.

        Returns:
            List of ``(index, cell)`` tuples for cells whose source
            contains the query string.
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
        """Get a token usage breakdown for this notebook.

        Analyzes every cell in the notebook and returns per-cell and
        total token counts for the given output mode.

        Args:
            mode: Output verbosity mode to use for counting. Defaults to
                :attr:`OutputMode.MINIMAL`.

        Returns:
            A :class:`~notebookllm.utils.tokenizer.NotebookTokenReport`
            with per-cell and total token counts.
        """
        from notebookllm.utils.tokenizer import tokenize_notebook

        return tokenize_notebook(self, mode=mode.value)
