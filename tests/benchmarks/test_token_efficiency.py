"""Token efficiency benchmarks — verify LLM token reduction claims."""
from pathlib import Path

import pytest

from notebookllm.loaders import load_file
from notebookllm.models import OutputMode

FIXTURES = Path(__file__).parent.parent / "fixtures"

try:
    from notebookllm.utils.tokenizer import count_tokens

    HAS_TOKENS = True
except ImportError:
    HAS_TOKENS = False


@pytest.mark.skipif(not HAS_TOKENS, reason="tokenizer module not available")
class TestTokenReduction:
    """Verify that notebookllm achieves meaningful token reduction vs raw ipynb."""

    @staticmethod
    def _count_raw_tokens(doc) -> int:
        import json

        from notebookllm.loaders.ipynb import IpynbDumper

        dumper = IpynbDumper()
        raw_json = dumper.dump(doc)
        return count_tokens(raw_json)

    def test_minimal_vs_raw_reduction(self):
        """MINIMAL mode should use fewer tokens than raw JSON."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        minimal_text = doc.to_text(mode=OutputMode.MINIMAL)
        minimal_tokens = count_tokens(minimal_text)
        assert minimal_tokens < raw_tokens

    def test_minimal_vs_full_tokens(self):
        """MINIMAL mode should use fewer or equal tokens vs FULL mode."""
        doc = load_file(FIXTURES / "sample.ipynb")
        minimal = count_tokens(doc.to_text(mode=OutputMode.MINIMAL))
        full = count_tokens(doc.to_text(mode=OutputMode.FULL))
        assert minimal <= full

    def test_token_reduction_percentage(self):
        """MINIMAL mode should achieve at least 50% token reduction vs raw JSON."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        minimal_text = doc.to_text(mode=OutputMode.MINIMAL)
        minimal_tokens = count_tokens(minimal_text)
        reduction = (raw_tokens - minimal_tokens) / raw_tokens * 100
        assert reduction >= 50

    def test_token_reduction_with_outputs(self):
        """FULL mode (with outputs) should achieve at least 40% reduction vs raw JSON."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        full_text = doc.to_text(mode=OutputMode.FULL)
        full_tokens = count_tokens(full_text)
        reduction = (raw_tokens - full_tokens) / raw_tokens * 100
        assert reduction >= 40
