"""Tests for notebookllm.converters.llm_optimizer — configurable output modes."""
from notebookllm.converters.llm_optimizer import LLMOptimizer
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


def _sample_doc():
    doc = NotebookDocument()
    doc.add_cell(Cell(
        cell_type=CellType.CODE,
        source="import pandas as pd\ndf = pd.read_csv('data.csv')",
        execution_count=1,
        outputs=[
            CellOutput(
                output_type="stream",
                content="    col1  col2\n0     1     2",
                name="stdout",
            ),
        ],
        metadata={"tags": ["setup"]},
    ))
    doc.add_cell(Cell(
        cell_type=CellType.MARKDOWN,
        source="# Analysis\n\nThis is the analysis section.",
    ))
    doc.add_cell(Cell(
        cell_type=CellType.CODE,
        source="df.describe()",
        execution_count=2,
        outputs=[
            CellOutput(
                output_type="execute_result",
                content="       col1  col2\ncount   3.0   3.0\nmean    2.0   2.0",
            ),
        ],
    ))
    return doc


class TestMinimalMode:
    def test_basic_output(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert "# %% [code]" in result
        assert "# %% [markdown]" in result
        assert "import pandas" in result
        assert "# Analysis" in result

    def test_no_metadata(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert "exec_count" not in result
        assert "tags" not in result
        assert "outputs" not in result

    def test_cell_markers_present(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert result.count("# %% [") == 3


class TestStandardMode:
    def test_includes_exec_count(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "exec_count: 1" in result
        assert "exec_count: 2" in result

    def test_includes_tags(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "tags: setup" in result

    def test_no_outputs(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "outputs ---" not in result


class TestFullMode:
    def test_includes_outputs(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "# --- outputs ---" in result

    def test_includes_stream_output(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[stdout]" in result

    def test_includes_exec_result(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "count" in result


class TestOptions:
    def test_no_cell_markers(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL, include_cell_markers=False).optimize(doc)
        assert "# %% [" not in result
        assert "import pandas" in result

    def test_empty_notebook(self):
        doc = NotebookDocument()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert result == ""


class TestFullModeEdgeCases:
    """Edge case coverage for LLMOptimizer._format_output() output types."""

    def test_display_data_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="display('hello')",
            outputs=[CellOutput(output_type="display_data", content={"text/plain": "hello"})],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[display]" in result
        assert "hello" in result

    def test_dict_content_fallback(self):
        """When MIME bundle has no text/plain key, fallback to str()."""
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="display({'text/html': '<b>hi</b>'})",
            outputs=[CellOutput(output_type="display_data", content={"text/html": "<b>hi</b>"})],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[display]" in result
        assert "<b>hi</b>" in result or "text/html" in result

    def test_single_line_error_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(output_type="error", content="division by zero")],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[error]" in result
        error_lines = [line for line in result.split("\n") if "[error]" in line]
        assert len(error_lines) == 1

    def test_multi_line_error_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(
                output_type="error",
                content="Traceback (most recent call last):\n"
                        "  File \"<cell>\", line 1\n"
                        "ZeroDivisionError: division by zero"
            )],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert result.count("[error]") >= 2

    def test_unknown_output_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(output_type="unknown_type", content="something")],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[unknown_type]" in result

class TestSummarization:
    def test_summarize_dataframe_output(self):
        """DataFrame ASCII tables are replaced with schema summary."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        output = CellOutput(
            output_type="execute_result",
            content={
                "text/plain": "   age  revenue\n0   25    50000\n1   30    60000\n...",
                "text/html": "<table>...</table>"
            }
        )
        cell = Cell(cell_type=CellType.CODE, source="df.head()",
                    outputs=[output], execution_count=1)
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "DataFrame" in result
        assert "age" in result  # column name preserved
        assert "50000" not in result  # values removed

    def test_summarize_dataframe_with_shape(self):
        """DataFrame with shape line is detected."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        output = CellOutput(
            output_type="execute_result",
            content={
                "text/plain": (
                    "(1000, 5)\n"
                    "   name  age  salary\n"
                    "0  Alice   30   50000\n"
                    "1    Bob   25   60000"
                ),
                "text/html": "<table>...</table>"
            }
        )
        cell = Cell(cell_type=CellType.CODE, source="df.describe()",
                    outputs=[output], execution_count=1)
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "DataFrame" in result
        assert "1000" in result  # shape preserved

    def test_summarize_image_png(self):
        """Image output shows mime type and approximate size."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        # Simulate a ~50KB PNG
        fake_png = "x" * (50 * 1024)
        output = CellOutput(
            output_type="display_data",
            content={"image/png": fake_png, "text/plain": "[PNG image]"}
        )
        cell = Cell(cell_type=CellType.CODE, source="plt.plot([1,2,3])",
                    outputs=[output], execution_count=1)
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "Plot" in result
        assert "image/png" in result
        assert "KB" in result

    def test_summarize_image_jpeg(self):
        """JPEG image shows mime type and size."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        fake_jpeg = "y" * (20 * 1024)
        output = CellOutput(
            output_type="display_data",
            content={"image/jpeg": fake_jpeg}
        )
        cell = Cell(cell_type=CellType.CODE, source="plt.imshow(img)",
                    outputs=[output], execution_count=1)
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "Plot" in result
        assert "image/jpeg" in result

    def test_summarize_image_no_match(self):
        """Non-image MIME bundles pass through to default handling."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        output = CellOutput(
            output_type="display_data",
            content={"application/json": '{"key": "value"}'}
        )
        cell = Cell(cell_type=CellType.CODE, source='display({"key": "value"})',
                    outputs=[output], execution_count=1)
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "application" in result or "display" in result

    def test_summarize_long_traceback(self):
        """Full tracebacks are replaced with ErrorType: message."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        output = CellOutput(
            output_type="error",
            content=(
                "Traceback (most recent call last):\n"
                '  File "<stdin>", line 1\n'
                "ZeroDivisionError: division by zero"
            )
        )
        cell = Cell(cell_type=CellType.CODE, source="1/0", outputs=[output])
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "ZeroDivisionError" in result
        assert "Traceback" not in result

    def test_truncate_long_string(self):
        """Strings over 500 chars are truncated with count."""
        optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
        output = CellOutput(
            output_type="stream",
            content="x" * 600,
            name="stdout"
        )
        cell = Cell(cell_type=CellType.CODE, source="print('x'*600)", outputs=[output])
        doc = NotebookDocument(cells=[cell])
        result = optimizer.optimize(doc)
        assert "truncated" in result
        assert len(result) < 600


class TestTokenBudget:
    """Tests for the max_tokens / token budget feature."""

    def test_no_budget_returns_full(self):
        """Without max_tokens, all cells are returned."""
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert result.count("# %% [") == 3

    def test_large_budget_keeps_all(self):
        """With a large budget, all cells are kept."""
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL, max_tokens=10000).optimize(doc)
        assert result.count("# %% [") == 3

    def test_small_budget_drops_code_cells(self):
        """With a small budget, code cells without outputs are dropped first."""
        # Add a code cell with no outputs (low priority)
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))  # no outputs — lowest priority
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Important Context"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="print('hello')",
                          execution_count=1,
                          outputs=[CellOutput(
                              output_type="stream", content="hello"
                          )]))

        result = LLMOptimizer(mode=OutputMode.FULL, max_tokens=10).optimize(doc)
        # With a tiny budget, the code cell without outputs should be dropped first
        assert "x = 1" not in result, "Code cell without outputs should be dropped first"

    def test_budget_preserves_markdown(self):
        """Markdown cells are kept as long as possible under token budget."""
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Critical Documentation"))

        result = LLMOptimizer(mode=OutputMode.MINIMAL, max_tokens=10).optimize(doc)
        # Markdown should be kept over a bare code cell
        assert "# Critical Documentation" in result

    def test_budget_empty_notebook(self):
        """Empty notebook still returns empty under budget mode."""
        doc = NotebookDocument()
        result = LLMOptimizer(mode=OutputMode.MINIMAL, max_tokens=10).optimize(doc)
        assert result == ""
