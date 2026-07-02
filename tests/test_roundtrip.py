"""Round-trip fidelity tests — format A → NotebookDocument → format A preserves content."""
from pathlib import Path

import pytest

from notebookllm.loaders import dump_file, load_file
from notebookllm.loaders.ipynb import IpynbDumper, IpynbLoader
from notebookllm.loaders.markdown import MarkdownDumper, MarkdownLoader
from notebookllm.loaders.percent import PercentDumper, PercentLoader
from notebookllm.loaders.quarto import QuartoDumper, QuartoLoader
from notebookllm.loaders.rmarkdown import RMarkdownDumper, RMarkdownLoader
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent / "fixtures"


def _assert_cells_match(doc1: NotebookDocument, doc2: NotebookDocument) -> None:
    """Assert that two notebooks have matching cell types and sources."""
    assert len(doc2.cells) == len(doc1.cells), (
        f"Cell count mismatch: {len(doc2.cells)} vs {len(doc1.cells)}"
    )
    for i, (c1, c2) in enumerate(zip(doc1.cells, doc2.cells, strict=True)):
        assert c1.cell_type == c2.cell_type, f"Cell {i}: type {c1.cell_type} vs {c2.cell_type}"
        assert c1.source.strip() == c2.source.strip(), (
            f"Cell {i}: source mismatch\n  Expected: {c1.source!r}\n  Got:      {c2.source!r}"
        )


# ── Parametrized dispatch round-trips ────────────────────────

ROUNDTRIP_CASES = [
    ("sample.ipynb", ".ipynb", "ipynb"),
    ("sample_percent.py", ".py", "percent"),
    ("sample_quarto.qmd", ".qmd", "quarto"),
    ("sample_markdown.md", ".md", "markdown"),
    ("sample_rmarkdown.Rmd", ".Rmd", "rmarkdown"),
    ("sample_marimo.py", ".py", "marimo"),
]


@pytest.mark.parametrize("fixture_name,ext,expected_format", ROUNDTRIP_CASES)
def test_roundtrip_via_dispatch(fixture_name, ext, expected_format, tmp_path):
    """Parametrized round-trip: load fixture → dump → load → verify cell count and sources match."""
    doc = load_file(FIXTURES / fixture_name)
    out = tmp_path / f"roundtrip{ext}"
    dump_file(doc, out)
    doc2 = load_file(out)
    assert len(doc2.cells) == len(doc.cells)
    for c1, c2 in zip(doc.cells, doc2.cells, strict=True):
        assert c1.cell_type == c2.cell_type
        assert c1.source.strip() == c2.source.strip()


# ── Parametrized cross-format conversions ────────────────────

CROSS_FORMAT_CASES = [
    ("sample.ipynb", "percent", ".py", "percent"),
    ("sample.ipynb", "quarto", ".qmd", "quarto"),
    ("sample_percent.py", "ipynb", ".ipynb", "ipynb"),
    ("sample_percent.py", "markdown", ".md", "markdown"),
    ("sample_quarto.qmd", "percent", ".py", "percent"),
    ("sample_markdown.md", "ipynb", ".ipynb", "ipynb"),
]


@pytest.mark.parametrize("fixture_name,target_fmt,ext,expected_format", CROSS_FORMAT_CASES)
def test_cross_format(fixture_name, target_fmt, ext, expected_format, tmp_path):
    """Parametrized cross-format: load from one format → dump to another → verify cells match."""
    doc = load_file(FIXTURES / fixture_name)
    out = tmp_path / f"converted{ext}"
    dump_file(doc, out, fmt=target_fmt)
    doc2 = load_file(out)
    assert doc2.source_format == expected_format
    _assert_cells_match(doc, doc2)


# ── Format-specific round-trip details ───────────────────────

class TestIpynbRoundtrip:
    """Detailed .ipynb round-trip tests."""

    def test_roundtrip_single_code_cell(self, tmp_path):
        loader = IpynbLoader()
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1", execution_count=1))
        out = tmp_path / "single.ipynb"
        dumper.dump(doc, filepath=out)
        doc2 = loader.load(out)
        assert len(doc2.cells) == 1
        assert doc2.cells[0].source == "x = 1"
        assert doc2.cells[0].execution_count == 1

    def test_roundtrip_mixed_cells(self, tmp_path):
        loader = IpynbLoader()
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        doc.add_cell(Cell(cell_type=CellType.RAW, source="raw content"))
        out = tmp_path / "mixed.ipynb"
        dumper.dump(doc, filepath=out)
        doc2 = loader.load(out)
        assert len(doc2.cells) == 3
        assert doc2.cells[0].cell_type == CellType.MARKDOWN
        assert doc2.cells[1].cell_type == CellType.CODE
        assert doc2.cells[2].cell_type == CellType.RAW


class TestPercentRoundtrip:
    """Detailed percent format round-trip tests."""

    def test_roundtrip_single_code_cell(self):
        loader = PercentLoader()
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert doc2.cells[0].source == "x = 1"

    def test_roundtrip_code_and_markdown(self):
        loader = PercentLoader()
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Analysis"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == 2
        assert doc2.cells[0].cell_type == CellType.CODE
        assert doc2.cells[1].cell_type == CellType.MARKDOWN

    def test_roundtrip_no_markers(self):
        """Plain .py file (no markers) should stay as single code cell."""
        loader = PercentLoader()
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1\nprint(x)"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == 1
        assert "x = 1" in doc2.cells[0].source


class TestQuartoRoundtrip:
    """Detailed quarto format round-trip tests."""

    def test_roundtrip_code_and_markdown(self):
        loader = QuartoLoader()
        dumper = QuartoDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="## Setup"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == 2
        assert doc2.cells[0].source == "## Setup"
        assert doc2.cells[1].source == "x = 1"

    def test_roundtrip_preserves_metadata(self, tmp_path):
        doc = NotebookDocument(metadata={"title": "Test", "author": "Me"})
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        dumper = QuartoDumper()
        out = tmp_path / "meta.qmd"
        dumper.dump(doc, filepath=out)
        loader = QuartoLoader()
        doc2 = loader.load(out)
        assert doc2.metadata.get("title") == "Test"


class TestMarkdownRoundtrip:
    """Detailed markdown format round-trip tests."""

    def test_roundtrip_code_only(self):
        loader = MarkdownLoader()
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="print(42)"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert doc2.cells[0].source == "print(42)"

    def test_roundtrip_mixed(self):
        loader = MarkdownLoader()
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Doc"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="data = load()"))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == 2


class TestRMarkdownRoundtrip:
    """Detailed RMarkdown format round-trip tests."""

    def test_roundtrip_code_and_markdown(self):
        loader = RMarkdownLoader()
        dumper = RMarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x <- 1", metadata={"language": "r"}))
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == 2
        assert doc2.cells[0].source == "# Title"
        assert doc2.cells[1].source == "x <- 1"


class TestNotebookDocumentRoundtrip:
    """Test NotebookDocument convenience methods for round-tripping."""

    def test_from_file_to_file(self, tmp_path):
        doc = NotebookDocument.from_file(FIXTURES / "sample.ipynb")
        out = tmp_path / "via_doc.ipynb"
        doc.to_file(out)
        doc2 = NotebookDocument.from_file(out)
        assert len(doc2.cells) == len(doc.cells)
        assert doc2.cells[0].source == doc.cells[0].source

    def test_from_text(self):
        text = "# %% [code]\nx = 42\n\n# %% [markdown]\n# Hello\n"
        doc = NotebookDocument.from_text(text)
        assert doc.source_format == "percent"
        assert len(doc.cells) == 2
        assert doc.cells[0].source == "x = 42"

    def test_to_text_and_back(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="print(1)"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Hi"))
        text = doc.to_text()
        assert "# %% [code]" in text
        assert "# %% [markdown]" in text
        assert "print(1)" in text
