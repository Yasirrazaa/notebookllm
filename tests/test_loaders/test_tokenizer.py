"""Tests for notebookllm.utils.tokenizer — token counting utilities."""

from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument
from notebookllm.utils.tokenizer import (
    CellTokenInfo,
    NotebookTokenReport,
    count_tokens,
    tokenize_notebook,
)


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_simple_text(self):
        count = count_tokens("Hello, world!")
        assert count > 0

    def test_code_vs_markdown(self):
        code = 'import pandas as pd\ndf = pd.read_csv("data.csv")\nprint(df.head())'
        md = "# Analysis\n\nThis is a gentle introduction to pandas."
        code_tokens = count_tokens(code)
        md_tokens = count_tokens(md)
        assert code_tokens > 0
        assert md_tokens > 0

    def test_encoding_fallback(self, monkeypatch):
        """When tiktoken is not available, fall back to character estimate."""
        monkeypatch.setattr("notebookllm.utils.tokenizer.tiktoken", None)
        count = count_tokens("Hello, world! This is a test of the fallback estimator.")
        assert count > 0

    def test_custom_encoding(self):
        count = count_tokens("Hello", encoding_name="r50k_base")
        assert count > 0

    def test_unknown_encoding(self):
        """Unknown encoding should fall back gracefully."""
        count = count_tokens("Hello", encoding_name="nonexistent_encoding")
        assert count > 0

    def test_large_text(self):
        text = "word " * 10000
        count = count_tokens(text)
        assert count > 0
        # 10000 * 5 chars / 4 ≈ 12500 using fallback estimator
        assert count >= 10000


class TestTokenizeNotebook:
    def test_empty_notebook(self):
        doc = NotebookDocument()
        report = tokenize_notebook(doc)
        assert report.total_tokens == 0
        assert len(report.cell_tokens) == 0

    def test_notebook_with_cells(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        report = tokenize_notebook(doc, mode="minimal")
        assert report.total_tokens > 0
        assert len(report.cell_tokens) == 2
        assert report.cell_tokens[0].cell_index == 0
        assert report.cell_tokens[1].cell_index == 1

    def test_token_report_includes_mode(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        report_minimal = tokenize_notebook(doc, mode="minimal")
        report_full = tokenize_notebook(doc, mode="full")
        assert report_minimal.mode == "minimal"
        assert report_full.mode == "full"

    def test_token_count_varies_by_mode(self):
        """FULL mode should produce more tokens than MINIMAL for cells with outputs."""
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="print('hello')",
            outputs=[CellOutput(output_type="stream", content="hello\n", name="stdout")],
        ))
        minimal_tokens = tokenize_notebook(doc, mode="minimal").total_tokens
        full_tokens = tokenize_notebook(doc, mode="full").total_tokens
        assert full_tokens >= minimal_tokens


class TestNotebookTokenReport:
    def test_token_summary_empty(self):
        report = NotebookTokenReport(total_tokens=0, num_cells=0)
        assert "Empty notebook" in report.token_summary

    def test_token_summary_non_empty(self):
        report = NotebookTokenReport(
            total_tokens=100,
            cell_tokens=[
                CellTokenInfo(cell_index=0, cell_type="code", tokens=50, preview="x = 1"),
            ],
            num_cells=1,
        )
        assert "100 tokens" in report.token_summary
        assert "1 cells" in report.token_summary


class TestNotebookDocumentIntegration:
    def test_token_breakdown_method_exists(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        report = doc.token_breakdown()
        assert isinstance(report, NotebookTokenReport)
        assert report.total_tokens > 0

    def test_token_breakdown_with_mode(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        from notebookllm.models import OutputMode
        report = doc.token_breakdown(mode=OutputMode.FULL)
        assert report.mode == "full"
