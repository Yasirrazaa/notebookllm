"""Tests for notebookllm.utils.detect — format detection."""
import pytest
from pathlib import Path
from notebookllm.utils.detect import detect_format, detect_text_format


class TestDetectFormat:
    def test_ipynb_extension(self, tmp_path):
        f = tmp_path / "notebook.ipynb"
        f.write_text("{}")
        assert detect_format(f) == "ipynb"

    def test_qmd_extension(self, tmp_path):
        f = tmp_path / "notebook.qmd"
        f.write_text("---\ntitle: Test\n---")
        assert detect_format(f) == "quarto"

    def test_md_extension(self, tmp_path):
        f = tmp_path / "notebook.md"
        f.write_text("# Title")
        assert detect_format(f) == "markdown"

    def test_rmd_extension(self, tmp_path):
        f = tmp_path / "notebook.rmd"
        f.write_text("# Title")
        assert detect_format(f) == "markdown"

    def test_py_percent_format(self, tmp_path):
        f = tmp_path / "notebook.py"
        f.write_text("# %% [code]\nx = 1\n")
        assert detect_format(f) == "percent"

    def test_py_marimo_format(self, tmp_path):
        f = tmp_path / "notebook.py"
        f.write_text("import marimo\n\n@app.cell\ndef f():\n    return\n")
        assert detect_format(f) == "marimo"

    def test_py_default_to_percent(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("x = 1\nprint(x)\n")
        assert detect_format(f) == "percent"

    def test_unknown_extension_raises(self, tmp_path):
        f = tmp_path / "notebook.xyz"
        f.write_text("content")
        with pytest.raises(ValueError, match="Cannot detect format"):
            detect_format(f)


class TestDetectTextFormat:
    def test_percent_markers(self):
        text = "# %% [code]\nx = 1\n# %% [markdown]\n# Title"
        assert detect_text_format(text) == "percent"

    def test_marimo_markers(self):
        text = "import marimo\n\n@app.cell\ndef f():\n    return\n"
        assert detect_text_format(text) == "marimo"

    def test_quarto_markers(self):
        text = "---\ntitle: Test\n---\n\n```{python}\nx = 1\n```\n"
        assert detect_text_format(text) == "quarto"

    def test_markdown_code_blocks(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        assert detect_text_format(text) == "markdown"

    def test_plain_python_fallback(self):
        text = "x = 1\nprint(x)\n"
        assert detect_text_format(text) == "percent"
