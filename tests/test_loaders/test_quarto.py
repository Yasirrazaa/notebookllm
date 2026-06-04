"""Tests for notebookllm.loaders.quarto — quarto format (.qmd)."""
import pytest
from pathlib import Path
from notebookllm.loaders.quarto import QuartoLoader, QuartoDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestQuartoLoader:
    def test_load_sample(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) >= 2
        assert doc.source_format == "quarto"

    def test_load_preserves_cell_types(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        types = [c.cell_type for c in doc.cells]
        assert CellType.CODE in types
        assert CellType.MARKDOWN in types

    def test_load_preserves_code_content(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        assert any("import pandas" in c.source for c in code_cells)

    def test_load_preserves_metadata(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        assert "title" in doc.metadata

    def test_loads_from_string(self):
        loader = QuartoLoader()
        text = '---\ntitle: "Test"\n---\n\n```{python}\nx = 1\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE

    def test_load_no_frontmatter(self):
        loader = QuartoLoader()
        text = "```{python}\nx = 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1


class TestQuartoDumper:
    def test_dump_to_string(self):
        dumper = QuartoDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "```{python}" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = QuartoDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.qmd"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()

    def test_dump_includes_frontmatter(self):
        dumper = QuartoDumper()
        doc = NotebookDocument(metadata={"title": "My Analysis"})
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "---" in result
        assert "title:" in result
