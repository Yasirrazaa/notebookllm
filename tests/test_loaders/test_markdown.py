"""Tests for notebookllm.loaders.markdown — markdown format (.md with ```python blocks)."""
import pytest
from pathlib import Path
from notebookllm.loaders.markdown import MarkdownLoader, MarkdownDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestMarkdownLoader:
    def test_load_sample(self):
        loader = MarkdownLoader()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) >= 2
        assert doc.source_format == "markdown"

    def test_load_preserves_cell_types(self):
        loader = MarkdownLoader()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        types = [c.cell_type for c in doc.cells]
        assert CellType.CODE in types
        assert CellType.MARKDOWN in types

    def test_loads_from_string(self):
        loader = MarkdownLoader()
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE

    def test_load_no_code_blocks(self):
        loader = MarkdownLoader()
        text = "# Just markdown\n\nNo code here.\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.MARKDOWN

    def test_load_empty_file(self):
        loader = MarkdownLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_load_multiple_code_blocks(self):
        loader = MarkdownLoader()
        text = "```python\na = 1\n```\n\n```python\nb = 2\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert all(c.cell_type == CellType.CODE for c in doc.cells)

    def test_load_parses_frontmatter(self):
        """Markdown files with YAML frontmatter should extract metadata."""
        loader = MarkdownLoader()
        text = '---\ntitle: "My Doc"\nauthor: "Test"\n---\n\n# Hello\n\n```python\nx = 1\n```\n'
        doc = loader.loads(text)
        assert doc.metadata.get("title") == "My Doc"
        assert doc.metadata.get("author") == "Test"

    def test_load_frontmatter_preserves_cells(self):
        """Frontmatter should be stripped from content but cells preserved."""
        loader = MarkdownLoader()
        text = '---\ntitle: Test\n---\n\n# Intro\n\n```python\nx = 1\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].source == "# Intro"
        assert doc.cells[1].source == "x = 1"


class TestMarkdownDumper:
    def test_dump_to_string(self):
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "```python" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.md"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()

    def test_roundtrip_preserves_content(self):
        loader = MarkdownLoader()
        dumper = MarkdownDumper()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
