"""Tests for notebookllm.loaders — format auto-detection and dispatch."""
from pathlib import Path

import pytest

from notebookllm.loaders import dump_file, load_file, loads_text
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadFile:
    def test_load_ipynb(self):
        doc = load_file(FIXTURES / "sample.ipynb")
        assert doc.source_format == "ipynb"
        assert len(doc.cells) > 0

    def test_load_percent(self):
        doc = load_file(FIXTURES / "sample_percent.py")
        assert doc.source_format == "percent"
        assert len(doc.cells) > 0

    def test_load_marimo(self):
        doc = load_file(FIXTURES / "sample_marimo.py")
        assert doc.source_format == "marimo"
        assert len(doc.cells) > 0

    def test_load_quarto(self):
        doc = load_file(FIXTURES / "sample_quarto.qmd")
        assert doc.source_format == "quarto"
        assert len(doc.cells) > 0

    def test_load_markdown(self):
        doc = load_file(FIXTURES / "sample_markdown.md")
        assert doc.source_format == "markdown"
        assert len(doc.cells) > 0

    def test_load_unknown_extension(self, tmp_path):
        f = tmp_path / "unknown.xyz"
        f.write_text("content")
        with pytest.raises(ValueError):
            load_file(f)


class TestDumpFile:
    def test_dump_ipynb(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.ipynb"
        dump_file(doc, out)
        assert out.exists()

    def test_dump_percent(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.py"
        dump_file(doc, out)
        assert out.exists()
        assert "# %% [code]" in out.read_text()

    def test_dump_quarto(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.qmd"
        dump_file(doc, out)
        assert out.exists()
        assert "```{python}" in out.read_text()

    def test_dump_markdown(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.md"
        dump_file(doc, out)
        assert out.exists()
        assert "```python" in out.read_text()


class TestLoadsText:
    def test_percent_format(self):
        text = "# %% [code]\nx = 1\n"
        doc = loads_text(text)
        assert doc.source_format == "percent"
        assert len(doc.cells) == 1

    def test_marimo_format(self):
        text = (
            "import marimo\napp = marimo.App()\n\n"
            "@app.cell\ndef f():\n    x = 1\n    return x,\n"
        )
        doc = loads_text(text)
        assert doc.source_format == "marimo"

    def test_quarto_format(self):
        text = "```{python}\nx = 1\n```\n"
        doc = loads_text(text)
        assert doc.source_format == "quarto"

    def test_markdown_format(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loads_text(text)
        assert doc.source_format == "markdown"

    def test_explicit_format(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loads_text(text, source_format="markdown")
        assert doc.source_format == "markdown"
