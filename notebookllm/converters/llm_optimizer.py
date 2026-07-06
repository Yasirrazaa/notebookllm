"""AI Agent Optimizer — converts NotebookDocument to Agent-optimized plain text.

Produces clean, token-efficient text representations of notebooks for
Agent consumption. Supports four output modes with different verbosity
levels and an optional token budget that drops low-priority cells
automatically.
"""
from __future__ import annotations

from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


class LLMOptimizer:
    """Converts :class:`~notebookllm.models.NotebookDocument` to Agent-optimized text.

    The optimizer produces a clean, structured text format with ``# %% [type]``
    cell markers, optionally including metadata and outputs. When a token budget
    is set, it drops the lowest-value cells first to stay within the limit.

    Parameters
    ----------
    mode:
        Output verbosity mode. Defaults to :attr:`~notebookllm.models.OutputMode.MINIMAL`.
    include_cell_markers:
        Whether to include ``# %% [type]`` markers between cells.
    max_line_length:
        If set, truncate source lines to this length.
    summarize_outputs:
        Replace long and rich outputs (DataFrames, images, tracebacks)
        with compressed one-line summaries.
    max_tokens:
        If set, trim the result to fit within this many tokens by dropping
        lowest-priority cells first (bare code -> code with outputs ->
        markdown). Token counting uses a simple ``len(text) // 4`` heuristic.
    """

    def __init__(
        self,
        mode: OutputMode = OutputMode.MINIMAL,
        include_cell_markers: bool = True,
        max_line_length: int | None = None,
        summarize_outputs: bool = False,
        max_tokens: int | None = None,
    ):
        self.mode = mode
        self.include_cell_markers = include_cell_markers
        self.max_line_length = max_line_length
        self.summarize_outputs = summarize_outputs
        self.max_tokens = max_tokens

    def optimize(self, doc: NotebookDocument) -> str:
        """Produce optimized text, optionally constrained by token budget.

        Args:
            doc: The notebook to optimize.

        Returns:
            The optimized plain text representation.
        """
        if not doc.cells:
            return ""

        if self.max_tokens is not None:
            return self._optimize_with_budget(doc)

        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))

        return "\n\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate using ``len(text) // 4`` heuristic.

        Args:
            text: The text to estimate.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def _optimize_with_budget(self, doc: NotebookDocument) -> str:
        """Render cells within a token budget, dropping lowest-priority cells.

        Priority order (highest = kept longest):

        1. Markdown cells (explanatory, most valuable for AI Agent understanding).
        2. Code cells with outputs (executed, have results).
        3. Code cells without outputs (scaffolding — dropped first).

        Args:
            doc: The notebook to render.

        Returns:
            The optimized text, trimmed to fit within the token budget.
        """
        assert self.max_tokens is not None
        budget: int = self.max_tokens

        saved_mode = self.mode
        saved_summary = self.summarize_outputs
        self.mode = OutputMode.FULL
        self.summarize_outputs = True

        priorities: list[tuple[int, int]] = []
        for i, cell in enumerate(doc.cells):
            if cell.cell_type == CellType.MARKDOWN:
                priorities.append((2, i))
            elif cell.outputs:
                priorities.append((1, i))
            else:
                priorities.append((0, i))
        priorities.sort(key=lambda x: (x[0], -x[1]))

        kept_indices = set(range(len(doc.cells)))
        for _ in range(len(doc.cells)):
            subset = [doc.cells[i] for i in sorted(kept_indices)]
            temp_doc = NotebookDocument(cells=subset, metadata=doc.metadata,
                                         source_format=doc.source_format)
            text = self._render_all(temp_doc)
            tokens = self._estimate_tokens(text)
            if tokens <= budget:
                self.mode = saved_mode
                self.summarize_outputs = saved_summary
                return text

            for _pri, _idx in priorities:
                md_count = sum(
                    1 for i in kept_indices
                    if doc.cells[i].cell_type == CellType.MARKDOWN
                )
                if _idx in kept_indices and (_pri < 2 or md_count > 1):
                    kept_indices.discard(_idx)
                    break
            else:
                break

        subset = [doc.cells[i] for i in sorted(kept_indices)]
        temp_doc = NotebookDocument(cells=subset, metadata=doc.metadata,
                                     source_format=doc.source_format)
        result = self._render_all(temp_doc)
        self.mode = saved_mode
        self.summarize_outputs = saved_summary
        return result

    def _render_all(self, doc: NotebookDocument) -> str:
        """Render all cells using current settings.

        Args:
            doc: The notebook to render.

        Returns:
            The rendered text.
        """
        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))
        return "\n\n".join(parts)

    def _format_cell(self, cell: Cell) -> str:
        """Format a single cell as Agent-optimized text.

        Args:
            cell: The cell to format.

        Returns:
            The formatted cell text.
        """
        lines = []

        if self.include_cell_markers:
            lines.append(f"# %% [{cell.cell_type.value}]")

        if self.mode in (OutputMode.STANDARD, OutputMode.FULL):
            if cell.execution_count is not None:
                lines.append(f"# exec_count: {cell.execution_count}")
            tags = cell.metadata.get("tags")
            if tags:
                lines.append(f"# tags: {', '.join(tags)}")

        lines.append(cell.source)

        if self.mode == OutputMode.FULL and cell.outputs:
            lines.append("# --- outputs ---")
            for output in cell.outputs:
                lines.append(self._format_output(output))

        return "\n".join(lines)

    def _format_output(self, output: CellOutput) -> str:
        """Format a single cell output for Agent consumption.

        If :attr:`summarize_outputs` is enabled, long outputs are compressed
        automatically (DataFrames get shape/columns summaries, images get
        size metadata, tracebacks get their last line).

        Args:
            output: The output to format.

        Returns:
            The formatted output string.
        """
        if self.summarize_outputs:
            summary = self._summarize_output(output)
            if summary is not None:
                return summary

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
        """Detect output type and return a compressed summary.

        Handles:
        - DataFrames (shape + column names)
        - Images (MIME type + size)
        - Error tracebacks (last line only)
        - Long text (truncated with char count)

        Args:
            output: The output to summarize.

        Returns:
            A one-line summary, or ``None`` if no compression is needed.
        """
        content = output.content
        if isinstance(content, dict):
            if "text/html" in content and "text/plain" in content:
                text_plain = content["text/plain"]
                return self._summarize_dataframe(text_plain)
            image_summary = self._summarize_image(content)
            if image_summary:
                return image_summary

        text = content if isinstance(content, str) else content.get("text/plain", str(content))

        if output.output_type == "error" and "Traceback" in text:
            return self._summarize_traceback(text)

        if len(text) > 500:
            out_type = output.output_type or 'output'
            remainder = len(text) - 500
            return f"# [{out_type}] {text[:500]}... (truncated {remainder} chars)"

        return None

    def _summarize_dataframe(self, text_plain: str) -> str:
        """Extract shape and column names from a pandas DataFrame ASCII repr.

        .. note::
            This is a heuristic — it works with pandas default formatting.
            The 100% accurate approach requires kernel-side type checking.

        Args:
            text_plain: The ``text/plain`` repr of a DataFrame.

        Returns:
            A one-line summary like ``# [DataFrame(1000, 5)] Columns: col1, col2, col3``.
        """
        lines = text_plain.strip().split("\n")
        if not lines:
            return "# [DataFrame] <empty>"

        shape = ""
        for line in lines[:5]:
            stripped = line.strip()
            if stripped.startswith("(") and ")" in stripped and "," in stripped:
                shape = f" {stripped}"

        columns_line = lines[0].strip()
        if columns_line and not columns_line[0].isdigit():
            columns = columns_line
        else:
            if len(lines) > 1 and not lines[1].strip()[0].isdigit():
                columns = lines[1].strip()
            else:
                columns = ""

        if shape and columns:
            return f"# [DataFrame{shape}] Columns: {columns} (values hidden)"
        if columns:
            return f"# [DataFrame] Columns: {columns}"
        return f"# [DataFrame] {shape or '<unknown shape>'}"

    def _summarize_image(self, content: dict) -> str | None:
        """Return image metadata (MIME type + size) instead of base64 data.

        Args:
            content: A MIME bundle dict.

        Returns:
            A one-line summary like ``# [Plot: image/png, ~42KB]``, or
            ``None`` if no image MIME type is found.
        """
        for mime in ("image/png", "image/jpeg", "image/svg+xml", "image/gif"):
            if mime in content:
                data = content[mime]
                size = len(data) if isinstance(data, str) else len(str(data))
                size_kb = size // 1024
                return f"# [Plot: {mime}, ~{size_kb}KB]"
        return None

    def _summarize_traceback(self, text: str) -> str:
        """Compress an error traceback to just the last line.

        Args:
            text: The full traceback text.

        Returns:
            A one-line summary like ``# [error] ValueError: invalid literal for int()``.
        """
        lines = text.strip().split("\n")
        if lines:
            return f"# [error] {lines[-1]}"
        return "# [error] Unknown Error"
