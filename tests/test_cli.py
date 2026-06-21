"""Tests for notebookllm.cli.commands — CLI integration."""
from pathlib import Path

import pytest
from click.testing import CliRunner

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
        path = str(FIXTURES / "sample_percent.py")
        result = runner.invoke(cli, ["search", path, "pandas", "-t", "code"])
        assert result.exit_code == 0


class TestGet:
    def test_get_cell(self, runner):
        result = runner.invoke(cli, ["get", str(FIXTURES / "sample_percent.py"), "0"])
        assert result.exit_code == 0


class TestServer:
    def test_server_help(self, runner):
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "transport" in result.output.lower()

    def test_server_transport_option(self, runner):
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "stdio" in result.output or "sse" in result.output


class TestErrors:
    def test_convert_malformed_ipynb(self, runner, tmp_path):
        bad_file = tmp_path / "bad.ipynb"
        bad_file.write_text("{invalid json!!!}")
        result = runner.invoke(cli, ["convert", str(bad_file)])
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "Error" in result.output

    def test_inspect_malformed_file(self, runner, tmp_path):
        bad_file = tmp_path / "bad.ipynb"
        bad_file.write_text("not json at all")
        result = runner.invoke(cli, ["inspect", str(bad_file)])
        assert result.exit_code != 0


class TestTokens:
    def test_tokens_basic(self, runner):
        result = runner.invoke(cli, ["tokens", str(FIXTURES / "sample.ipynb")])
        assert result.exit_code == 0
        assert "tokens" in result.output.lower()
        assert "Total" in result.output

    def test_tokens_with_mode(self, runner):
        result = runner.invoke(cli, ["tokens", str(FIXTURES / "sample_percent.py"), "-m", "full"])
        assert result.exit_code == 0
        assert "tokens" in result.output.lower()

    def test_tokens_with_breakdown(self, runner):
        result = runner.invoke(cli, ["tokens", str(FIXTURES / "sample.ipynb"), "--breakdown"])
        assert result.exit_code == 0
        assert "cell" in result.output.lower() or "Cell" in result.output
