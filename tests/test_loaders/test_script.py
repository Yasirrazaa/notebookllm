"""Tests for notebookllm.loaders.script — flat script format (.py without markers)."""
from notebookllm.loaders.script import ScriptDumper
from notebookllm.models import Cell, CellType, NotebookDocument


class TestScriptDumper:
    def test_dump_code_only(self):
        dumper = ScriptDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1\nprint(x)"))
        result = dumper.dump(doc)
        assert "x = 1" in result
        assert "print(x)" in result
        assert "# %% [code]" not in result

    def test_dump_markdown_as_comments(self):
        dumper = ScriptDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title\n\nDescription"))
        result = dumper.dump(doc)
        lines = result.split("\n")
        comment_lines = [line for line in lines if line.startswith("#")]
        assert any("Title" in line for line in comment_lines)

    def test_dump_to_file(self, tmp_path):
        dumper = ScriptDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.py"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()

    def test_dump_empty_notebook(self):
        dumper = ScriptDumper()
        doc = NotebookDocument()
        result = dumper.dump(doc)
        assert result == ""

    def test_dump_raw_as_comments(self):
        dumper = ScriptDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.RAW, source="raw content"))
        result = dumper.dump(doc)
        assert "# raw content" in result