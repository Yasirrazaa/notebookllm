"""Tests for notebookllm.models — NotebookDocument, Cell, CellType, OutputMode, CellOutput."""
import json

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

    def test_cell_with_language(self):
        """Language field distinguishes code type (python, sql, r, etc.)."""
        cell = Cell(cell_type=CellType.CODE, source="SELECT * FROM t", language="sql")
        assert cell.language == "sql"

    def test_cell_default_language(self):
        cell = Cell(cell_type=CellType.CODE, source="x = 1")
        assert cell.language is None

    def test_cell_block_type(self):
        """block_type preserves format-specific block classification."""
        cell = Cell(cell_type=CellType.CODE, source="x = 1", block_type="input")
        assert cell.block_type == "input"
        cell2 = Cell(cell_type=CellType.CODE, source="plot", block_type="visualization")
        assert cell2.block_type == "visualization"

    def test_cell_deepnote_fields(self):
        """Deepnote-specific fields are preserved in the Cell model."""
        cell = Cell(
            cell_type=CellType.CODE,
            source="SELECT * FROM sales",
            language="sql",
            block_type="sql",
            block_group="uuid-123",
            content_hash="sha256:abc123",
            sorting_key="a0",
        )
        assert cell.block_group == "uuid-123"
        assert cell.content_hash == "sha256:abc123"
        assert cell.sorting_key == "a0"

    def test_cell_to_dict_omits_none_fields(self):
        """Serialization should omit None fields to minimize size."""
        cell = Cell(cell_type=CellType.CODE, source="x = 1")
        d = cell._to_dict()
        assert "cell_type" in d
        assert "source" in d
        assert "language" not in d
        assert "block_type" not in d

    def test_cell_to_dict_includes_non_none_deepnote_fields(self):
        """Non-None Deepnote fields should appear in serialization."""
        cell = Cell(
            cell_type=CellType.CODE,
            source="x = 1",
            language="sql",
            block_type="sql",
            block_group="uuid-123",
        )
        d = cell._to_dict()
        assert d["language"] == "sql"
        assert d["block_type"] == "sql"
        assert d["block_group"] == "uuid-123"


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


class TestCellToDictRoundtrip:
    def test_cell_to_dict_basic(self):
        cell = Cell(cell_type=CellType.CODE, source="x = 1", execution_count=1)
        d = cell._to_dict()
        assert d["cell_type"] == "code"
        assert d["source"] == "x = 1"
        assert d["execution_count"] == 1

    def test_cell_from_dict_basic(self):
        data = {"cell_type": "code", "source": "x = 1", "execution_count": 1}
        cell = Cell._from_dict(data)
        assert cell.cell_type == CellType.CODE
        assert cell.source == "x = 1"
        assert cell.execution_count == 1

    def test_cell_from_dict_unknown_keys_ignored(self):
        """Version tolerance: unknown keys should be silently ignored."""
        data = {
            "cell_type": "code",
            "source": "x = 1",
            "unknown_field": "should_not_cause_error",
            "future_version_flag": True,
        }
        cell = Cell._from_dict(data)
        assert cell.cell_type == CellType.CODE
        assert cell.source == "x = 1"


class TestCellOutputToDictRoundtrip:
    def test_output_to_dict_stream(self):
        out = CellOutput(output_type="stream", content="hello", name="stdout")
        d = out._to_dict()
        assert d["output_type"] == "stream"
        assert d["content"] == "hello"
        assert d["name"] == "stdout"

    def test_output_from_dict_stream(self):
        data = {"output_type": "stream", "content": "hello", "name": "stdout"}
        out = CellOutput._from_dict(data)
        assert out.output_type == "stream"
        assert out.content == "hello"
        assert out.name == "stdout"

    def test_output_from_dict_missing_name(self):
        data = {"output_type": "stream", "content": "hello"}
        out = CellOutput._from_dict(data)
        assert out.name is None


class TestNotebookDocumentSerialization:
    def test_notebook_json_roundtrip(self):
        """NotebookDocument serializes to JSON and back without data loss."""
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1", execution_count=1))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        out = CellOutput(output_type="stream", content="hello", name="stdout")
        doc.add_cell(Cell(
            cell_type=CellType.CODE,
            source="print('hello')",
            execution_count=2,
            outputs=[out],
        ))
        doc.metadata = {"kernelspec": {"name": "python3"}}
        doc.source_format = "ipynb"

        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)

        assert len(doc2.cells) == len(doc.cells)
        for i in range(len(doc.cells)):
            assert doc2.cells[i].source == doc.cells[i].source
            assert doc2.cells[i].cell_type == doc.cells[i].cell_type
            assert doc2.cells[i].execution_count == doc.cells[i].execution_count
        assert doc2.metadata == doc.metadata
        assert doc2.source_format == "ipynb"

    def test_empty_notebook_roundtrip(self):
        """Empty notebook -> to_json() -> from_json() -> empty notebook."""
        doc = NotebookDocument()
        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)
        assert doc2.cells == []
        assert doc2.metadata == {}
        assert doc2.language == "python"

    def test_notebook_with_all_cell_types(self):
        """Notebook with all cell types + outputs round-trips correctly."""
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.RAW, source="raw_data"))

        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)

        assert len(doc2.cells) == 3
        assert doc2.cells[0].cell_type == CellType.CODE
        assert doc2.cells[1].cell_type == CellType.MARKDOWN
        assert doc2.cells[2].cell_type == CellType.RAW

    def test_unicode_content(self):
        """Unicode content (Japanese, emoji) survives round-trip."""
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# 日本語\nこんにちは"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="print('🚀')"))

        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)

        assert "日本語" in doc2.cells[0].source
        assert "🚀" in doc2.cells[1].source

    def test_nested_metadata(self):
        """Deeply nested metadata dicts survive round-trip."""
        doc = NotebookDocument()
        doc.metadata = {
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python", "version": "3.11.0"},
            "tags": ["project", "analysis"],
        }
        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)
        assert doc2.metadata["kernelspec"]["name"] == "python3"
        assert doc2.metadata["language_info"]["version"] == "3.11.0"

    def test_none_values(self):
        """None values (execution_count, cell_id) are preserved on restore."""
        cell = Cell(cell_type=CellType.CODE, source="x = 1", execution_count=None, cell_id=None)
        d = cell._to_dict()
        assert "execution_count" not in d
        assert "cell_id" not in d

    def test_version_tolerance_unknown_keys(self):
        """from_json should ignore unknown keys for forward compatibility."""
        json_str = json.dumps({
            "_cir_version": 999,
            "cells": [{"cell_type": "code", "source": "x = 1"}],
            "metadata": {},
            "kernel_name": None,
            "language": "python",
            "source_format": "ipynb",
            "unknown_top_level_field": "should be ignored",
        })
        doc = NotebookDocument.from_json(json_str)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "x = 1"

    def test_serialized_contains_version(self):
        """JSON output should contain _cir_version."""
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        json_str = doc.to_json()
        data = json.loads(json_str)
        assert "_cir_version" in data
        assert data["_cir_version"] == 2

    def test_language_field_serialization(self):
        """Cell language field should survive round-trip."""
        doc = NotebookDocument()
        sql_cell = Cell(
            cell_type=CellType.CODE,
            source="SELECT * FROM t",
            language="sql",
            block_type="sql",
            block_group="uuid-123",
            content_hash="sha256:abc",
            sorting_key="a0",
        )
        doc.add_cell(sql_cell)
        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)
        c2 = doc2.cells[0]
        assert c2.language == "sql"
        assert c2.block_type == "sql"
        assert c2.block_group == "uuid-123"
        assert c2.content_hash == "sha256:abc"
        assert c2.sorting_key == "a0"

    def test_very_long_source(self):
        """Very long cell sources (>100KB) survive round-trip."""
        long_source = "x = 1\n" * 5000  # ~30KB
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source=long_source))
        json_str = doc.to_json()
        doc2 = NotebookDocument.from_json(json_str)
        assert doc2.cells[0].source == long_source
