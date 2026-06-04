"""Tests for notebookllm.loaders.percent — percent format (.py with # %% markers)."""
import pytest
from pathlib import Path
from notebookllm.loaders.percent import PercentLoader, PercentDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestPercentLoader:
    def test_load_sample(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 3
        assert doc.source_format == "percent"

    def test_load_preserves_cell_types(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[2].cell_type == CellType.CODE

    def test_load_preserves_source(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert "import pandas" in doc.cells[0].source
        assert "df.head()" in doc.cells[0].source

    def test_loads_from_string(self):
        loader = PercentLoader()
        text = "# %% [code]\nx = 1\n\n# %% [markdown]\n# Title\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN

    def test_load_no_markers(self):
        """Files without markers are treated as a single code cell."""
        loader = PercentLoader()
        text = "x = 1\nprint(x)\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE
        assert "x = 1" in doc.cells[0].source

    def test_load_empty_file(self):
        loader = PercentLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_load_consecutive_markers(self):
        loader = PercentLoader()
        text = "# %% [code]\n\n# %% [code]\nx = 1\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2

    def test_load_preserves_indentation(self):
        """percent loader should NOT use textwrap.dedent — preserve indentation."""
        loader = PercentLoader()
        text = "# %% [code]\nif True:\n    x = 1\n    print(x)\n"
        doc = loader.loads(text)
        assert "    x = 1" in doc.cells[0].source
        assert "    print(x)" in doc.cells[0].source

    def test_load_skips_markers_inside_triple_quotes(self):
        """Marker inside triple-quoted string should not trigger cell boundary."""
        loader = PercentLoader()
        text = '# %% [code]\nx = """\n# %% [markdown]\nThis is not a real marker\n"""\ny = 1\n'
        doc = loader.loads(text)
        # Should be a single code cell, not split by the fake marker
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE
        assert 'x = """' in doc.cells[0].source
        assert 'y = 1' in doc.cells[0].source

    def test_load_skips_markers_inside_triple_single_quotes(self):
        """Marker inside triple-single-quoted string should not trigger cell boundary."""
        loader = PercentLoader()
        text = "# %% [code]\nx = '''\n# %% [markdown]\nStill code\n'''\ny = 2\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE

    def test_load_skips_markers_in_single_line_strings(self):
        """Marker inside a single-line string that happens to start with # should not trigger."""
        loader = PercentLoader()
        text = "# %% [code]\nprint('# %% this is not a marker')\nz = 3\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert 'print' in doc.cells[0].source
        assert 'z = 3' in doc.cells[0].source

    def test_load_multiple_code_cells_with_triple_quotes(self):
        """Real markers should still work after a triple-quoted string closes."""
        loader = PercentLoader()
        text = '# %% [code]\nx = """\ncontent\n"""\n\n# %% [markdown]\n# Real title\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN


class TestPercentDumper:
    def test_dump_to_string(self):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "# %% [code]" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.py"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()
        assert "# %% [code]" in filepath.read_text()

    def test_dump_multiple_cells(self):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        result = dumper.dump(doc)
        assert result.count("# %%") == 3

    def test_roundtrip_preserves_content(self):
        loader = PercentLoader()
        dumper = PercentDumper()
        doc = loader.load(FIXTURES / "sample_percent.py")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source.strip() == c2.source.strip()
