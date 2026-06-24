"""LLM Optimizer — converts NotebookDocument to LLM-optimized text."""
from __future__ import annotations

from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


class LLMOptimizer:
    """Converts NotebookDocument to LLM-optimized text with configurable output modes.

    Parameters
    ----------
    mode:
        Output verbosity mode.
    include_cell_markers:
        Whether to include ``# %% [type]`` markers.
    max_line_length:
        If set, truncate source lines to this length.
    summarize_outputs:
        Replace long/rich outputs with compressed summaries.
    max_tokens:
        If set, trim the result to fit within this many tokens.
        Token counting uses a simple heuristic: 1 token ≈ 4 characters.
        Lower-priority cells (code without outputs, bottom cells) are
        dropped first; markdown cells are kept as long as possible.
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
        """Produce optimized text, optionally constrained by token budget."""
        if not doc.cells:
            return ""

        # --- token budget mode: build incrementally, dropping lowest-value cells ---
        if self.max_tokens is not None:
            return self._optimize_with_budget(doc)

        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))

        return "\n\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4

    def _optimize_with_budget(self, doc: NotebookDocument) -> str:
        """Render cells within the token budget, dropping bottom code cells first."""
        budget = self.max_tokens

        # First pass: render in FULL mode with summarization
        saved_mode = self.mode
        saved_summary = self.summarize_outputs
        self.mode = OutputMode.FULL
        self.summarize_outputs = True

        # Sort cells by priority for dropping:
        #   Priority 1 (drop first): code cells with no outputs (scaffolding)
        #   Priority 2: code cells WITH outputs
        #   Priority 3 (keep longest): markdown cells
        priorities: list[tuple[int, int]] = []  # (priority, cell_index)
        for i, cell in enumerate(doc.cells):
            if cell.cell_type == CellType.MARKDOWN:
                priorities.append((2, i))  # highest priority — never drop
            elif cell.outputs:
                priorities.append((1, i))
            else:
                priorities.append((0, i))
        priorities.sort(key=lambda x: (x[0], -x[1]))  # low priority first, then bottom-up

        # Try rendering with all cells, drop lowest-priority cells until within budget
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

            # Drop lowest-priority cell that isn't the last markdown
            for pri, idx in priorities:
                if idx in kept_indices and (pri < 2 or sum(1 for i in kept_indices if doc.cells[i].cell_type == CellType.MARKDOWN) > 1):
                    kept_indices.discard(idx)
                    break
            else:
                break  # can't drop any more

        # Final render after dropping
        subset = [doc.cells[i] for i in sorted(kept_indices)]
        temp_doc = NotebookDocument(cells=subset, metadata=doc.metadata,
                                     source_format=doc.source_format)
        result = self._render_all(temp_doc)
        self.mode = saved_mode
        self.summarize_outputs = saved_summary
        return result

    def _render_all(self, doc: NotebookDocument) -> str:
        """Render all cells using current settings."""
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
            image_summary = self._summarize_image(content)
            if image_summary:
                return image_summary
        
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
        """Try to extract shape and columns from DataFrame ASCII repr.

        Heuristic — works for pandas default formatting. The 100% accurate
        approach requires kernel-side type checking.
        """
        lines = text_plain.strip().split("\n")
        if not lines:
            return "# [DataFrame] <empty>"

        # Try to detect shape line like "(1000, 5)" in first few lines
        shape = ""
        for line in lines[:5]:
            stripped = line.strip()
            if stripped.startswith("(") and ")" in stripped and "," in stripped:
                shape = f" {stripped}"

        # Columns are typically in the first line (for small DataFrames)
        # or second/third line for truncated views like:
        #     col1  col2  col3
        # 0    x     y     z
        columns_line = lines[0].strip()
        # Filter out row index lines (start with digit + whitespace)
        if columns_line and not columns_line[0].isdigit():
            columns = columns_line
        else:
            columns = lines[1].strip() if len(lines) > 1 and not lines[1].strip()[0].isdigit() else ""

        if shape and columns:
            return f"# [DataFrame{shape}] Columns: {columns} (values hidden)"
        if columns:
            return f"# [DataFrame] Columns: {columns}"
        return f"# [DataFrame] {shape or '<unknown shape>'}"

    def _summarize_image(self, content: dict) -> str | None:
        """Return image metadata instead of base64 data."""
        for mime in ("image/png", "image/jpeg", "image/svg+xml", "image/gif"):
            if mime in content:
                data = content[mime]
                size = len(data) if isinstance(data, str) else len(str(data))
                size_kb = size // 1024
                return f"# [Plot: {mime}, ~{size_kb}KB]"
        return None

    def _summarize_traceback(self, text: str) -> str:
        lines = text.strip().split("\n")
        # Find the last line which usually contains the actual ErrorType: message
        if lines:
            return f"# [error] {lines[-1]}"
        return "# [error] Unknown Error"
