"""Tests for notebookllm.loaders.rmarkdown — R Markdown format (.Rmd)."""
from pathlib import Path

from notebookllm.loaders.rmarkdown import RMarkdownDumper, RMarkdownLoader
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestRMarkdownLoader:
    def test_load_sample(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) >= 4
        assert doc.source_format == "rmarkdown"

    def test_load_preserves_cell_types(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        types = [c.cell_type for c in doc.cells]
        assert CellType.CODE in types
        assert CellType.MARKDOWN in types

    def test_loads_from_string(self):
        loader = RMarkdownLoader()
        text = (
            '---\ntitle: "Test"\n---\n\n# Title\n\n'
            '```{r}\nx <- 1\n```\n\n```{python}\ny = 2\n```\n'
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 3  # markdown, r, python
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE
        assert doc.cells[2].cell_type == CellType.CODE
        # Check language metadata for code cells
        assert doc.cells[1].metadata.get("language") == "r"
        assert doc.cells[2].metadata.get("language") == "python"

    def test_load_no_code_blocks(self):
        loader = RMarkdownLoader()
        text = '---\ntitle: "Test"\n---\n\n# Just markdown\n\nNo code here.\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.MARKDOWN

    def test_load_empty_file(self):
        loader = RMarkdownLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_load_multiple_code_blocks(self):
        loader = RMarkdownLoader()
        text = (
            '---\ntitle: "Test"\n---\n\n```{r}\na <- 1\n```\n\n'
            '```{r}\nb <- 2\n```\n\n```{python}\nc = 3\n```\n'
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 3
        assert all(c.cell_type == CellType.CODE for c in doc.cells)
        assert doc.cells[0].metadata.get("language") == "r"
        assert doc.cells[1].metadata.get("language") == "r"
        assert doc.cells[2].metadata.get("language") == "python"

    def test_load_parses_frontmatter(self):
        """RMarkdown files with YAML frontmatter should extract metadata."""
        loader = RMarkdownLoader()
        text = (
            '---\ntitle: "My Doc"\nauthor: "Test"\n'
            'date: "2023-01-01"\n---\n\n# Hello\n\n```{r}\nx <- 1\n```\n'
        )
        doc = loader.loads(text)
        assert doc.metadata.get("title") == "My Doc"
        assert doc.metadata.get("author") == "Test"
        assert doc.metadata.get("date") == "2023-01-01"

    def test_load_frontmatter_preserves_cells(self):
        """Frontmatter should be stripped from content but cells preserved."""
        loader = RMarkdownLoader()
        text = '---\ntitle: Test\n---\n\n# Intro\n\n```{r}\nx <- 1\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].source == "# Intro"
        assert doc.cells[1].source == "x <- 1"
        assert doc.cells[1].metadata.get("language") == "r"

    def test_load_bad_frontmatter(self):
        """Invalid YAML frontmatter should not crash."""
        loader = RMarkdownLoader()
        text = "---\n  broken yaml : [\n---\n\nHello\n\n```{r}\nprint('hi')\n```\n"
        doc = loader.loads(text)
        assert doc.metadata == {}
        assert len(doc.cells) >= 1

    def test_load_r_chunk_detection(self):
        """Detect R chunks even without language specification."""
        loader = RMarkdownLoader()
        text = '# Title\n\n```{r}\nplot(1:10)\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE
        assert doc.cells[1].metadata.get("language") == "r"

    def test_load_python_chunk_detection(self):
        """Detect Python chunks in RMarkdown."""
        loader = RMarkdownLoader()
        text = '# Title\n\n```{python}\nimport numpy as np\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE
        assert doc.cells[1].metadata.get("language") == "python"

    def test_load_mixed_chunks(self):
        """Handle mixed R and Python chunks in any order."""
        loader = RMarkdownLoader()
        text = (
            '---\ntitle: "Mixed"\n---\n\n```{r}\nlibrary(ggplot2)\n```\n'
            '\nSome markdown.\n\n```{python}\nimport sys\n```\n\n'
            '```{r}\nsummary(1:5)\n```\n'
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 4
        # [0] R code, [1] markdown, [2] Python code, [3] R code
        types = [c.cell_type for c in doc.cells]
        assert types == [CellType.CODE, CellType.MARKDOWN, CellType.CODE, CellType.CODE]
        langs = [c.metadata.get("language") for c in doc.cells if c.cell_type == CellType.CODE]
        assert langs == ["r", "python", "r"]


class TestRMarkdownDumper:
    def test_dump_to_string(self):
        dumper = RMarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x <- 1", metadata={"language": "r"}))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Header"))
        doc.add_cell(
            Cell(cell_type=CellType.CODE, source="print('hello')", metadata={"language": "python"})
        )
        result = dumper.dump(doc)
        # Should contain R and Python chunk markers
        assert "```{r}" in result
        assert "x <- 1" in result
        assert "```{python}" in result
        assert "print('hello')" in result
        assert "# Header" in result

    def test_dump_to_file(self, tmp_path):
        dumper = RMarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x <- 1", metadata={"language": "r"}))
        filepath = tmp_path / "output.Rmd"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()
        content = filepath.read_text()
        assert "```{r}" in content
        assert "x <- 1" in content

    def test_roundtrip_preserves_content(self):
        loader = RMarkdownLoader()
        dumper = RMarkdownDumper()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)