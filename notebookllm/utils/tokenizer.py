"""Token counting utilities — estimate LLM token usage for notebooks.

Provides accurate token counting via ``tiktoken`` (GPT-4 ``cl100k_base``
encoding) and a fast character-based fallback (``len(text) / 4``).

Key functions:

- :func:`count_tokens`: Token count for a single string.
- :func:`tokenize_notebook`: Full token analysis of a notebook.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from notebookllm.models import NotebookDocument, OutputMode

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore[assignment]

DEFAULT_ENCODING = "cl100k_base"
CHARS_PER_TOKEN = 4.0


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count the number of tokens in *text*.

    Uses ``tiktoken`` with the GPT-4 ``cl100k_base`` encoding for accurate
    counting when the ``[token]`` extra is installed. Falls back to a
    character-based estimate (``len(text) / 4``) when tiktoken is not
    available or the requested encoding is unknown.

    Args:
        text: The text to count tokens for.
        encoding_name: Name of the tiktoken encoding to use. Defaults to
            ``"cl100k_base"`` (GPT-4).

    Returns:
        Number of tokens. Returns ``0`` for empty strings.
    """
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except (KeyError, ValueError):
            pass

    return max(1, int(len(text) / CHARS_PER_TOKEN))


@dataclass
class CellTokenInfo:
    """Token usage breakdown for a single cell.

    Attributes:
        cell_index: Zero-based index of the cell in the notebook.
        cell_type: Type of the cell (``"code"``, ``"markdown"``, or ``"raw"``).
        tokens: Number of tokens in the cell's source text.
        preview: First 50 characters of the cell source (whitespace collapsed).
    """

    cell_index: int
    cell_type: str
    tokens: int
    preview: str


@dataclass
class NotebookTokenReport:
    """Token usage report for an entire notebook.

    Produced by :func:`tokenize_notebook`.

    Attributes:
        total_tokens: Total tokens across all cells.
        cell_tokens: Per-cell token breakdown as a list of :class:`CellTokenInfo`.
        mode: Output mode used for counting (``"minimal"``, ``"standard"``, or ``"full"``).
        num_cells: Number of cells in the notebook.
    """

    total_tokens: int
    cell_tokens: list[CellTokenInfo] = field(default_factory=list)
    mode: str = "minimal"
    num_cells: int = 0

    @property
    def token_summary(self) -> str:
        """Human-readable summary of token usage.

        Returns:
            A string like ``"Total: 420 tokens across 8 cells (minimal mode)"``.
        """
        if not self.cell_tokens:
            return "Empty notebook (0 tokens)"
        return (
            f"Total: {self.total_tokens} tokens across {self.num_cells} cells"
            f" ({self.mode} mode)"
        )


def tokenize_notebook(
    doc: NotebookDocument,
    mode: str = "minimal",
    encoding_name: str = DEFAULT_ENCODING,
) -> NotebookTokenReport:
    """Analyze token usage of a notebook in the given output mode.

    Counts tokens for the full notebook text (``doc.to_text(...)``) and
    provides a per-cell breakdown of the individual cell sources.

    Args:
        doc: The notebook document to analyze.
        mode: Output verbosity mode (``"minimal"``, ``"standard"``, or
            ``"full"``). Passed to :meth:`NotebookDocument.to_text` to
            obtain the full serialized text for total token counting.
        encoding_name: Name of the tiktoken encoding to use. Defaults to
            ``"cl100k_base"`` (GPT-4).

    Returns:
        A :class:`NotebookTokenReport` with per-cell and total token counts.
    """
    output_mode = OutputMode(mode)
    full_text = doc.to_text(mode=output_mode)
    total = count_tokens(full_text, encoding_name=encoding_name)

    cell_tokens: list[CellTokenInfo] = []
    for i, cell in enumerate(doc.cells):
        cell_text = cell.source
        ct = count_tokens(cell_text, encoding_name=encoding_name)
        preview = cell.source[:50].replace("\n", " ")
        cell_tokens.append(CellTokenInfo(
            cell_index=i,
            cell_type=cell.cell_type.value,
            tokens=ct,
            preview=preview,
        ))

    return NotebookTokenReport(
        total_tokens=total,
        cell_tokens=cell_tokens,
        mode=mode,
        num_cells=len(doc.cells),
    )
