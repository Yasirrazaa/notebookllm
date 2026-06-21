"""Tests for notebookllm.loaders.quarto — quarto format (.qmd)."""
from pathlib import Path

from notebookllm.loaders.quarto import QuartoDumper, QuartoLoader
from notebookllm.models import Cell, CellType, NotebookDocument

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

    def test_load_preserves_cell_options(self):
        """Quarto #| cell options should be stored in cell metadata."""
        loader = QuartoLoader()
        text = """```{python}
#| echo: false
#| eval: true
x = 1
```
"""
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        cell = doc.cells[0]
        assert "quarto_options" in cell.metadata
        assert cell.metadata["quarto_options"]["echo"] == "false"
        assert cell.metadata["quarto_options"]["eval"] == "true"

    def test_load_strips_cell_options_from_source(self):
        """#| lines should be removed from the cell source."""
        loader = QuartoLoader()
        text = """```{python}
#| echo: false
#| fig-cap: "My Plot"
x = 1
print(x)
```
"""
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert "#|" not in doc.cells[0].source
        assert "x = 1" in doc.cells[0].source
        assert "print(x)" in doc.cells[0].source

    def test_load_stores_language_in_metadata(self):
        """Code block language should be stored in cell metadata."""
        loader = QuartoLoader()
        text = """```{r}
x <- 1
```
"""
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].metadata.get("language") == "r"


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
