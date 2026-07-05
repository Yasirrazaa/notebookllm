"""Tests for notebookllm.utils.validation."""

import pytest

from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument
from notebookllm.utils.validation import (
    ValidationError,
    ValidationReport,
    atomic_write,
    validate_cell_index,
    validate_cell_type,
    validate_cell_types,
    validate_filepath,
    validate_no_empty_cells,
    validate_no_orphan_outputs,
    validate_notebook,
    validate_output_format,
)


class TestValidateFilepath:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.ipynb"
        f.write_text("{}")
        result = validate_filepath(f)
        assert result == f

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.ipynb"
        with pytest.raises(FileNotFoundError):
            validate_filepath(f)

    def test_directory(self, tmp_path):
        with pytest.raises(IsADirectoryError):
            validate_filepath(tmp_path)


class TestValidateOutputFormat:
    def test_valid_formats(self):
        for fmt in ["ipynb", "percent", "marimo", "quarto", "markdown"]:
            assert validate_output_format(fmt) == fmt

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            validate_output_format("csv")


class TestValidateCellIndex:
    def test_valid_index(self):
        assert validate_cell_index(0, 5) == 0
        assert validate_cell_index(4, 5) == 4

    def test_negative_index(self):
        with pytest.raises(IndexError):
            validate_cell_index(-1, 5)

    def test_out_of_range(self):
        with pytest.raises(IndexError):
            validate_cell_index(5, 5)


class TestValidateCellType:
    def test_valid_types(self):
        assert validate_cell_type("code").value == "code"
        assert validate_cell_type("markdown").value == "markdown"
        assert validate_cell_type("raw").value == "raw"

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            validate_cell_type("invalid")


# ------------------------------------------------------------------
# New validation tests
# ------------------------------------------------------------------

class TestAtomicWrite:
    def test_writes_file(self, tmp_path):
        target = tmp_path / "test.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_creates_parent_dir(self, tmp_path):
        target = tmp_path / "nested" / "subdir" / "test.txt"
        atomic_write(target, "deep")
        assert target.read_text() == "deep"

    def test_no_temp_left_behind(self, tmp_path):
        target = tmp_path / "test.txt"
        atomic_write(target, "content")
        # No .test.txt.tmp should remain
        tmps = list(tmp_path.glob(".*.tmp"))
        assert len(tmps) == 0

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "test.txt"
        target.write_text("old")
        atomic_write(target, "new")
        assert target.read_text() == "new"


class TestValidateCellTypes:
    def test_all_valid(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        assert validate_cell_types(doc) == []

    def test_invalid_type_in_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        # Manually set an invalid type (shouldn't happen normally but tests validation)
        doc.cells[0].cell_type = "not_a_type"  # type: ignore[assignment]
        errors = validate_cell_types(doc)
        assert len(errors) == 1
        assert errors[0].cell_index == 0
        assert "cell_type" in errors[0].field


class TestValidateNoOrphanOutputs:
    def test_code_cell_with_outputs_ok(self):
        doc = NotebookDocument()
        cell = Cell(cell_type=CellType.CODE, source="print('hi')")
        cell.outputs.append(CellOutput(output_type="stream", content="hi"))
        doc.add_cell(cell)
        assert validate_no_orphan_outputs(doc) == []

    def test_markdown_cell_with_outputs_warns(self):
        doc = NotebookDocument()
        cell = Cell(cell_type=CellType.MARKDOWN, source="# Title")
        cell.outputs.append(CellOutput(output_type="stream", content="output"))
        doc.add_cell(cell)
        warnings = validate_no_orphan_outputs(doc)
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"


class TestValidateNoEmptyCells:
    def test_all_nonempty_ok(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        assert validate_no_empty_cells(doc) == []

    def test_empty_cell_warns(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source=""))
        warnings = validate_no_empty_cells(doc)
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_whitespace_only_cell_warns(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="   \n  "))
        warnings = validate_no_empty_cells(doc)
        assert len(warnings) == 1


class TestValidateNotebook:
    def test_clean_notebook(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Hello"))
        report = validate_notebook(doc)
        assert report.is_valid
        assert len(report.warnings) == 0

    def test_multiple_issues(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source=""))
        cell = Cell(cell_type=CellType.MARKDOWN, source="# Title")
        cell.outputs.append(CellOutput(output_type="stream", content="orphan"))
        doc.add_cell(cell)
        report = validate_notebook(doc)
        # 1 error (empty cell type), 2 warnings (empty source, orphan outputs)
        assert len(report.warnings) == 2


class TestValidationReport:
    def test_summary_clean(self):
        r = ValidationReport()
        assert r.is_valid
        assert r.summary == "Validation passed."

    def test_summary_with_issues(self):
        r = ValidationReport(errors=[ValidationError("x", "bad", "error")])
        assert not r.is_valid
        assert "error(s)" in r.summary

    def test_format_text(self):
        r = ValidationReport(
            errors=[ValidationError("source", "Missing source", cell_index=1)],
            warnings=[ValidationError(
                "outputs", "Orphan output",
                severity="warning", cell_index=2,
            )],
        )
        text = r.format_text()
        assert "ERROR" in text
        assert "WARNING" in text
        assert "cell[1]" in text
        assert "cell[2]" in text
