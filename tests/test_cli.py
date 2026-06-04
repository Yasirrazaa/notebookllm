"""Tests for notebookllm.cli.commands — CLI integration."""
import pytest
from click.testing import CliRunner
from pathlib import Path
from notebookllm.cli.commands import cli


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


class TestConvert:
    def test_convert_to_stdout(self, runner):
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample_percent.py")])
        assert result.exit_code == 0
        assert "# %% [code]" in result.output

    def test_convert_to_file(self, runner, tmp_path):
        out = tmp_path / "output.py"
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample.ipynb"), "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_convert_with_mode(self, runner):
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample_percent.py"), "-m", "full"])
        assert result.exit_code == 0

    def test_convert_nonexistent_file(self, runner):
        result = runner.invoke(cli, ["convert", "nonexistent.ipynb"])
        assert result.exit_code != 0


class TestInspect:
    def test_inspect(self, runner):
        result = runner.invoke(cli, ["inspect", str(FIXTURES / "sample.ipynb")])
        assert result.exit_code == 0
        assert "Cells:" in result.output or "cell" in result.output.lower()


class TestSearch:
    def test_search(self, runner):
        result = runner.invoke(cli, ["search", str(FIXTURES / "sample_percent.py"), "pandas"])
        assert result.exit_code == 0

    def test_search_with_type(self, runner):
        result = runner.invoke(cli, ["search", str(FIXTURES / "sample_percent.py"), "pandas", "-t", "code"])
        assert result.exit_code == 0


class TestGet:
    def test_get_cell(self, runner):
        result = runner.invoke(cli, ["get", str(FIXTURES / "sample_percent.py"), "0"])
        assert result.exit_code == 0
