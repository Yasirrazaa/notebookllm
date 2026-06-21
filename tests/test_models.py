"""Tests for notebookllm.models — NotebookDocument, Cell, CellType, OutputMode, CellOutput."""
import pytest

from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


class TestCellType:
    def test_enum_values(self):
        assert CellType.CODE.value == "code"
        assert CellType.MARKDOWN.value == "markdown"
        assert CellType.RAW.value == "raw"

    def test_from_string(self):
        assert CellType("code") == CellType.CODE
        assert CellType("markdown") == CellType.MARKDOWN


class TestOutputMode:
    def test_enum_values(self):
        assert OutputMode.MINIMAL.value == "minimal"
        assert OutputMode.STANDARD.value == "standard"
        assert OutputMode.FULL.value == "full"


class TestCellOutput:
    def test_stream_output(self):
        out = CellOutput(output_type="stream", content="hello world", name="stdout")
        assert out.output_type == "stream"
        assert out.content == "hello world"
        assert out.name == "stdout"

    def test_execute_result(self):
        out = CellOutput(output_type="execute_result", content={"text/plain": "42"})
        assert out.output_type == "execute_result"
        assert out.name is None

    def test_error_output(self):
        out = CellOutput(output_type="error", content="Traceback...")
        assert out.output_type == "error"


class TestCell:
    def test_code_cell(self):
        cell = Cell(cell_type=CellType.CODE, source="print('hello')")
        assert cell.cell_type == CellType.CODE
        assert cell.source == "print('hello')"
        assert cell.execution_count is None
        assert cell.outputs == []
        assert cell.metadata == {}
        assert cell.cell_id is None

    def test_cell_with_outputs(self):
        outputs = [CellOutput(output_type="stream", content="hello", name="stdout")]
        cell = Cell(cell_type=CellType.CODE, source="print('hello')", outputs=outputs)
        assert len(cell.outputs) == 1
        assert cell.outputs[0].content == "hello"

    def test_markdown_cell(self):
        cell = Cell(cell_type=CellType.MARKDOWN, source="# Title")
        assert cell.cell_type == CellType.MARKDOWN


class TestNotebookDocument:
    def test_empty_notebook(self):
        doc = NotebookDocument()
        assert doc.cells == []
        assert doc.metadata == {}
        assert doc.language == "python"
        assert doc.source_format is None

    def test_add_cell(self):
        doc = NotebookDocument()
        cell = Cell(cell_type=CellType.CODE, source="x = 1")
        doc.add_cell(cell)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "x = 1"

    def test_add_cell_at_position(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"), position=0)
        assert len(doc.cells) == 3
        assert doc.cells[0].source == "# Title"
        assert doc.cells[1].source == "a"
        assert doc.cells[2].source == "b"

    def test_get_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        cell = doc.get_cell(0)
        assert cell.source == "x = 1"

    def test_get_cell_out_of_range(self):
        doc = NotebookDocument()
        with pytest.raises(IndexError):
            doc.get_cell(0)

    def test_edit_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.edit_cell(0, source="x = 2")
        assert doc.cells[0].source == "x = 2"

    def test_edit_cell_change_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="# comment"))
        doc.edit_cell(0, source="# Title", cell_type=CellType.MARKDOWN)
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[0].source == "# Title"

    def test_delete_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.delete_cell(0)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "b"

    def test_delete_cell_out_of_range(self):
        doc = NotebookDocument()
        with pytest.raises(IndexError):
            doc.delete_cell(0)

    def test_move_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="c"))
        doc.move_cell(0, 2)
        assert doc.cells[0].source == "b"
        assert doc.cells[1].source == "c"
        assert doc.cells[2].source == "a"

    def test_filter_cells_by_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        code_cells = doc.filter_cells(cell_type=CellType.CODE)
        assert len(code_cells) == 2

    def test_filter_cells_by_query(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import numpy"))
        results = doc.filter_cells(query="pandas")
        assert len(results) == 1
        assert results[0].source == "import pandas"

    def test_search(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas as pd"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import numpy as np"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="Data analysis with pandas"))
        results = doc.search("pandas")
        assert len(results) == 2
        indices = [r[0] for r in results]
        assert 0 in indices
        assert 2 in indices

    def test_search_case_insensitive(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import Pandas"))
        results = doc.search("pandas")
        assert len(results) == 1

    def test_search_with_cell_type_filter(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="pandas documentation"))
        results = doc.search("pandas", cell_type=CellType.MARKDOWN)
        assert len(results) == 1
        assert results[0][1].cell_type == CellType.MARKDOWN
