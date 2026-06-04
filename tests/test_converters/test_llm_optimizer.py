"""Tests for notebookllm.converters.llm_optimizer — configurable output modes."""
import pytest
from notebookllm.converters.llm_optimizer import LLMOptimizer
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


def _sample_doc():
    doc = NotebookDocument()
    doc.add_cell(Cell(
        cell_type=CellType.CODE,
        source="import pandas as pd\ndf = pd.read_csv('data.csv')",
        execution_count=1,
        outputs=[CellOutput(output_type="stream", content="    col1  col2\n0     1     2", name="stdout")],
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
        outputs=[CellOutput(output_type="execute_result", content="       col1  col2\ncount   3.0   3.0\nmean    2.0   2.0")],
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
