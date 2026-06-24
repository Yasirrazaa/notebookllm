"""LLM Optimizer — converts NotebookDocument to LLM-optimized text."""
from __future__ import annotations

from notebookllm.models import Cell, CellOutput, NotebookDocument, OutputMode


class LLMOptimizer:
    """Converts NotebookDocument to LLM-optimized text with configurable output modes."""

    def __init__(
        self,
        mode: OutputMode = OutputMode.MINIMAL,
        include_cell_markers: bool = True,
        max_line_length: int | None = None,
        summarize_outputs: bool = False,
    ):
        self.mode = mode
        self.include_cell_markers = include_cell_markers
        self.max_line_length = max_line_length
        self.summarize_outputs = summarize_outputs

    def optimize(self, doc: NotebookDocument) -> str:
        """Produce optimized text based on mode."""
        if not doc.cells:
            return ""

        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))

        return "\n\n".join(parts)

    def _format_cell(self, cell: Cell) -> str:
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
        if self.summarize_outputs:
            summary = self._summarize_output(output)
            if summary is not None:
                return summary

        # Extract text/plain from rich MIME bundles for cleaner LLM output
        content = output.content
        if isinstance(content, dict):
            content = content.get("text/plain", str(content))

        if output.output_type == "stream":
            name = output.name or "stdout"
            return f"# [{name}] {content}"
        elif output.output_type == "execute_result":
            return f"# [output] {content}"
        elif output.output_type == "display_data":
            return f"# [display] {content}"
        elif output.output_type == "error":
            lines_content = content.split("\n")
            if len(lines_content) > 1:
                return "\n".join(f"# [error] {line}" for line in lines_content)
            return f"# [error] {content}"
        else:
            return f"# [{output.output_type}] {content}"

    def _summarize_output(self, output: CellOutput) -> str | None:
        """Detect output type and compress intelligently."""
        content = output.content
        if isinstance(content, dict):
            # Check for DataFrame patterns in MIME bundle
            if "text/html" in content and "text/plain" in content:
                text_plain = content["text/plain"]
                return self._summarize_dataframe(text_plain)
            # Check for image
            if "image/png" in content or "image/jpeg" in content:
                return "# [image] <Image Data>"
        
        # String content
        text = content if isinstance(content, str) else content.get("text/plain", str(content))
        
        # Traceback detection
        if output.output_type == "error" and "Traceback" in text:
            return self._summarize_traceback(text)

        # Truncate long strings
        if len(text) > 500:
            return f"# [{output.output_type or 'output'}] {text[:500]}... (truncated {len(text) - 500} chars)"

        return None

    def _summarize_dataframe(self, text_plain: str) -> str:
        lines = text_plain.split("\n")
        if not lines:
            return "# [DataFrame] <empty>"
        # Naive schema extraction: assume first line has columns
        columns = lines[0].strip()
        return f"# [DataFrame] Columns: {columns} (values hidden for brevity)"

    def _summarize_traceback(self, text: str) -> str:
        lines = text.strip().split("\n")
        # Find the last line which usually contains the actual ErrorType: message
        if lines:
            return f"# [error] {lines[-1]}"
        return "# [error] Unknown Error"
