"""Speed benchmarks for notebookllm loaders and converters."""
from pathlib import Path

import pytest

from notebookllm.loaders import dump_file, load_file
from notebookllm.models import OutputMode

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadSpeed:
    """Benchmark loading speed across all supported notebook formats."""

    def test_load_ipynb_speed(self, benchmark):
        doc = benchmark(load_file, FIXTURES / "sample.ipynb")
        assert len(doc.cells) > 0

    def test_load_percent_speed(self, benchmark):
        doc = benchmark(load_file, FIXTURES / "sample_percent.py")
        assert len(doc.cells) > 0

    def test_load_quarto_speed(self, benchmark):
        doc = benchmark(load_file, FIXTURES / "sample_quarto.qmd")
        assert len(doc.cells) > 0

    def test_load_markdown_speed(self, benchmark):
        doc = benchmark(load_file, FIXTURES / "sample_markdown.md")
        assert len(doc.cells) > 0


class TestConvertSpeed:
    """Benchmark conversion speed for LLM-optimized output."""

    def test_to_text_minimal_speed(self, benchmark):
        doc = load_file(FIXTURES / "sample.ipynb")
        result = benchmark(doc.to_text)
        assert len(result) > 0

    def test_to_text_full_speed(self, benchmark):
        doc = load_file(FIXTURES / "sample.ipynb")
        result = benchmark(doc.to_text, mode=OutputMode.FULL)
        assert len(result) > 0

    def test_dump_ipynb_speed(self, benchmark):
        """Benchmark IpynbDumper dump speed (in-memory, no file I/O)."""
        from notebookllm.loaders.ipynb import IpynbDumper

        doc = load_file(FIXTURES / "sample.ipynb")
        dumper = IpynbDumper()
        raw = benchmark(dumper.dump, doc)
        assert isinstance(raw, str)
        assert len(raw) > 0


class TestLargeFileSpeed:
    """Benchmark streaming performance with large notebooks."""

    @pytest.mark.slow
    def test_stream_large_notebook_speed(self, benchmark, tmp_path):
        from notebookllm.loaders.ipynb import IpynbLoader
        from tests.test_loaders.test_ipynb import _generate_large_notebook

        nb_path = _generate_large_notebook(tmp_path, 10000)
        loader = IpynbLoader()
        loader.streaming_threshold = 0

        doc = benchmark(loader.load, nb_path)
        assert len(doc.cells) == 10000
