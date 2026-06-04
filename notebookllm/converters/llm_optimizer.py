"""LLM Optimizer — converts NotebookDocument to LLM-optimized text."""
from __future__ import annotations

from notebookllm.models import CellOutput, CellType, NotebookDocument, OutputMode


class LLMOptimizer:
    """Converts NotebookDocument to LLM-optimized text with configurable output modes."""

    def __init__(
        self,
        mode: OutputMode = OutputMode.MINIMAL,
        include_cell_markers: bool = True,
        max_line_length: int | None = None,
        strip_outputs: bool = True,
    ):
        self.mode = mode
        self.include_cell_markers = include_cell_markers
        self.max_line_length = max_line_length
        self.strip_outputs = strip_outputs

    def optimize(self, doc: NotebookDocument) -> str:
        """Produce optimized text based on mode."""
        if not doc.cells:
            return ""

        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))

        return "\n\n".join(parts)

    def _format_cell(self, cell) -> str:
        lines = []

        # Cell marker
        if self.include_cell_markers:
            lines.append(f"# %% [{cell.cell_type.value}]")

        # Metadata (STANDARD+)
        if self.mode in (OutputMode.STANDARD, OutputMode.FULL):
            if cell.execution_count is not None:
                lines.append(f"# exec_count: {cell.execution_count}")
            tags = cell.metadata.get("tags")
            if tags:
                lines.append(f"# tags: {', '.join(tags)}")

        # Source
        lines.append(cell.source)

        # Outputs (FULL only)
        if self.mode == OutputMode.FULL and cell.outputs:
            lines.append("# --- outputs ---")
            for output in cell.outputs:
                lines.append(self._format_output(output))

        return "\n".join(lines)

    def _format_output(self, output: CellOutput) -> str:
        if output.output_type == "stream":
            name = output.name or "stdout"
            return f"# [{name}] {output.content}"
        elif output.output_type == "execute_result":
            return f"# [output] {output.content}"
        elif output.output_type == "display_data":
            return f"# [display] {output.content}"
        elif output.output_type == "error":
            return f"# [error] {output.content}"
        else:
            return f"# [{output.output_type}] {output.content}"
