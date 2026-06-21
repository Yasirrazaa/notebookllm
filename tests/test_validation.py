"""Tests for notebookllm.utils.validation."""

import pytest

from notebookllm.utils.validation import (
    validate_cell_index,
    validate_cell_type,
    validate_filepath,
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
