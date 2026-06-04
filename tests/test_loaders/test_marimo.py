"""Tests for notebookllm.loaders.marimo — marimo format (.py with @app.cell)."""
from pathlib import Path
from notebookllm.loaders.marimo import MarimoLoader
from notebookllm.models import NotebookDocument, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestMarimoLoader:
    def test_load_sample(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert isinstance(doc, NotebookDocument)
        assert doc.source_format == "marimo"

    def test_load_extracts_cells(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert len(doc.cells) == 3

    def test_load_cell_types_are_code(self):
        """Marimo cells are always code cells."""
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        for cell in doc.cells:
            assert cell.cell_type == CellType.CODE

    def test_load_preserves_cell_content(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert "import pandas" in doc.cells[0].source
        assert "df.describe()" in doc.cells[1].source

    def test_loads_from_string(self):
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "app = marimo.App()\n"
            "\n"
            "@app.cell\n"
            "def f():\n"
            "    x = 1\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert "x = 1" in doc.cells[0].source

    def test_load_empty_marimo_file(self):
        loader = MarimoLoader()
        text = "import marimo\napp = marimo.App()\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 0

    def test_load_skips_non_cell_functions(self):
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "app = marimo.App()\n"
            "\n"
            "def helper():\n"
            "    return 42\n"
            "\n"
            "@app.cell\n"
            "def main():\n"
            "    return helper(),\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 1

    def test_load_detects_mo_md_cells(self):
        """Cells containing mo.md() calls should be detected as MARKDOWN type."""
        loader = MarimoLoader()
        text = (
            "import marimo as mo\n"
            "app = marimo.App()\n"
            "\n"
            "@app.cell\n"
            "def header():\n"
            "    mo.md(\"# Hello\")\n"
            "    return\n"
            "\n"
            "@app.cell\n"
            "def compute():\n"
            "    x = 1 + 2\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE

    def test_load_captures_generated_with(self):
        """The __generated_with version should be captured in notebook metadata."""
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "__generated_with = \"0.5.0\"\n"
            "app = marimo.App()\n"
            "\n"
            "@app.cell\n"
            "def f():\n"
            "    x = 1\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert doc.metadata.get("generated_with") == "0.5.0"