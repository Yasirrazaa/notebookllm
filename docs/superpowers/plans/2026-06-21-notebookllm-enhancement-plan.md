# notebookllm Enhancement & Benchmarking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform notebookllm from a solid v3.0 into a best-in-class, benchmarked, CI-gated notebook optimization tool for LLM workflows — with token efficiency metrics, expanded format support, comprehensive test coverage, and publisher-quality documentation.

**Architecture:** Layered enhancement — (a) close coverage gaps in existing code, (b) add token/buffer analytics layer, (c) expand format support (R Markdown, script export), (d) build benchmark harness, (e) establish CI/CD pipeline with docs publishing.

**Tech Stack:** Python 3.11+, pytest (TDD), pytest-benchmark, tiktoken (token counting), GitHub Actions (CI), Sphinx (docs), ruff/mypy (quality gates)

**Current baseline:** 246 tests passing, 86% overall coverage, ruff 0 errors, mypy 0 errors (19 source files)

---

## Phase 0: Deep Review Findings (Context — not actionable tasks)

### Code Quality
- **Strengths**: Clean modular architecture, good separation of concerns via BaseLoader/BaseDumper, type-safe dataclasses, comprehensive error handling in loaders
- **Weaknesses**: MCP server has no error boundary middleware — exceptions from `session_manager.get()` bubble through. Some loaders have no dumper (marimo). CLI commands 95-96 are dead code paths.

### Test Coverage Gaps
| Module | Coverage | Missing Lines |
|--------|----------|---------------|
| `mcp/server.py` | **67%** | 17-18, 23, 65, 135-180, 187-188, 192 |
| `loaders/ipynb.py` | **81%** | 44-47, 92-93, 105, 124-125, 167, 177, 181-190, 197, 207, 255, 271, 277-292 |
| `converters/llm_optimizer.py` | **81%** | 61, 68-76 |
| `loaders/marimo.py` | **80%** | 26-27, 38-39, 42-46, 69-70, 90-93 |
| `loaders/markdown.py` | **88%** | 33-34, 51, 76-79 |

### Missing Features (from Research)
1. **Token counting** — no tool estimates token usage of output text
2. **R Markdown (.Rmd) support** — detect + load + convert (currently treated as generic markdown, losing R-specific cells)
3. **Script export** — no conversion from percent/ipynb to flat .py (no markers)
4. **Benchmark harness** — no standardized way to measure speed, memory, token efficiency
5. **CI/CD pipeline** — no GitHub Actions, no automated PyPI publishing
6. **Sphinx docs build** — stale config, no Makefile fix for local builds
7. **Large-file memory benchmarks** — streaming works but is untested for memory usage
8. **MCP server error wrapping** — no ToolError boundary around session lookups

---

## Phase 1: Close Coverage Gaps

### Task 1.1: MCP Server Error Middleware

**Files:**
- Modify: `notebookllm/mcp/server.py`
- Test: `tests/test_mcp.py`

**Context:** The MCP server wraps `session_manager.get()` in each tool. When a session is missing, a `KeyError` from `session.py:35` propagates as an uncaught exception instead of a `ToolError`. The tools should catch this and return a clean error message.

- [ ] **Step 1: Write the failing test for ToolError boundary**

Add to `tests/test_mcp.py`, inside `TestMCPAppCreation` class:

```python
async def test_all_tools_handle_missing_session_gracefully(self, session_manager):
    """Every tool that accepts session_id should return error, not raise, for missing sessions."""
    app = create_app(session_manager)
    tools = await app.list_tools()
    for tool in tools:
        if "session_id" in {n.name for n in tool.parameters}:
            try:
                result = await app.call_tool(tool.name, {"session_id": "nonexistent"})
                text = _get_text(result)
                assert "not found" in text.lower() or "error" in text.lower()
            except Exception:
                pytest.fail(f"Tool {tool.name} raised exception for missing session")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp.py::TestMCPAppCreation::test_all_tools_handle_missing_session_gracefully -v`

Expected: FAIL — some tools raise `KeyError` instead of returning an error

- [ ] **Step 3: Add helper to wrap session access in MCP tools**

Modify `notebookllm/mcp/server.py`. Add a helper function:

```python
def _get_doc_safe(session_manager, session_id: str) -> NotebookDocument | None:
    """Get notebook doc, returning None and logging if session missing."""
    try:
        return session_manager.get(session_id)
    except KeyError:
        return None
```

Then in each tool function that calls `session_manager.get()`, add a guard:

```python
doc = _get_doc_safe(session_manager, session_id)
if doc is None:
    return f"Session not found: {session_id}"
```

Apply this pattern to: `save_notebook`, `to_text`, `list_cells`, `get_cell`, `add_cell`, `edit_cell`, `delete_cell`, `move_cell`, `search_cells`, `execute_cell`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp.py -v --tb=short`

Expected: All MCP tests pass (including the new one)

- [ ] **Step 5: Commit**

```bash
git add notebookllm/mcp/server.py tests/test_mcp.py
git commit -m "fix: add ToolError boundary for missing sessions in MCP tools"
```

---

### Task 1.2: LLM Optimizer Error Format Coverage

**Files:**
- Modify: `notebookllm/converters/llm_optimizer.py`
- Test: `tests/test_converters/test_llm_optimizer.py`

**Context:** `_format_output()` has untested branches for `display_data` (line 68-69), `error` with single-line (line 73-74), unknown output types (line 75-76), and dict content extraction fallback (line 61). These should be tested.

- [ ] **Step 1: Write tests for uncovered output formats**

Add to `tests/test_converters/test_llm_optimizer.py`:

```python
class TestFullModeEdgeCases:
    def test_display_data_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="display('hello')",
            outputs=[CellOutput(output_type="display_data", content={"text/plain": "hello"})],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[display]" in result
        assert "hello" in result

    def test_single_line_error_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(output_type="error", content="division by zero")],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[error]" in result

    def test_multi_line_error_output(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(output_type="error", content="Traceback (most recent call last):\n  File \"<cell>\", line 1\nZeroDivisionError: division by zero")],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[error]" in result
        assert result.count("[error]") >= 2

    def test_unknown_output_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="1/0",
            outputs=[CellOutput(output_type="unknown_type", content="something")],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[unknown_type]" in result

    def test_dict_content_fallback(self):
        """When MIME bundle has no text/plain key, fallback to str()."""
        doc = NotebookDocument()
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="display({'text/html': '<b>hi</b>'})",
            outputs=[CellOutput(output_type="display_data", content={"text/html": "<b>hi</b>"})],
        ))
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[display]" in result
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_converters/test_llm_optimizer.py::TestFullModeEdgeCases -v`

Expected: PASS (all 5 new tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_converters/test_llm_optimizer.py
git commit -m "test: add edge case coverage for LLM optimizer output formatting"
```

---

### Task 1.3: Ipynb Loader Edge Case Coverage

**Files:**
- Modify: `notebookllm/loaders/ipynb.py`
- Test: `tests/test_loaders/test_ipynb.py`

**Context:** Several branches in the ipynb loader are untested: ijson ImportError fallback (line 44-47), `_extract_metadata` binary tail edge cases, error output type with traceback, fallback in `_dump_output`, and raw cell dump (line 255).

- [ ] **Step 1: Write tests for uncovered ipynb branches**

Add to `tests/test_loaders/test_ipynb.py`:

```python
class TestIpynbEdgeCases:
    def test_load_streaming_fallback_no_ijson(self, tmp_path, monkeypatch):
        """When ijson is not installed, streaming should fall back to nbformat."""
        monkeypatch.setattr("builtins.__import__", lambda name, *a, **kw: (_ for _ in ()).throw(ImportError()) if name == "ijson" else __import__(name, *a, **kw))
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert len(doc.cells) == 3

    def test_metadata_tail_unicode_decode_error(self, tmp_path):
        """Binary tail data should return empty metadata."""
        f = tmp_path / "binary_tail.ipynb"
        # Write JSON header then 64KB+ of random binary
        header = b'{"cells": [{"cell_type":"code","source":"x=1","metadata":{},"outputs":[],"id":"c1"}],"metadata":'
        import os
        f.write_bytes(header + os.urandom(70000) + b', "nbformat": 4}')
        result = IpynbLoader._extract_metadata(f, file_size=f.stat().st_size)
        assert result == {}

    def test_dump_raw_cell(self):
        """Dumping a raw cell should produce valid output."""
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.RAW, source="raw content"))
        result = dumper.dump(doc)
        import json
        data = json.loads(result)
        assert data["cells"][0]["cell_type"] == "raw"

    def test_dump_error_output(self):
        """Dumping an error output should preserve traceback."""
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="1/0",
                          outputs=[CellOutput(output_type="error", content="ZeroDivisionError")]))
        import json
        result = json.loads(dumper.dump(doc))
        assert result["cells"][0]["outputs"][0]["output_type"] == "error"

    def test_dump_unknown_output_fallback(self):
        """Unknown output types should get a fallback."""
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x",
                          outputs=[CellOutput(output_type="custom_type", content="data")]))
        import json
        result = json.loads(dumper.dump(doc))
        assert result["cells"][0]["outputs"][0]["output_type"] == "custom_type"
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_loaders/test_ipynb.py -v --tb=short`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_loaders/test_ipynb.py
git commit -m "test: add edge case coverage for ipynb loader/dumper"
```

---

### Task 1.4: Marimo Loader Edge Case Coverage

**Files:**
- Modify: `notebookllm/loaders/marimo.py`
- Test: `tests/test_loaders/test_marimo.py`

**Context:** Untested branches: `__generated_with` via `ast.AnnAssign` (line 42-46), `@cell` decorator without `app.` prefix (line 69-70), Python <3.8 compat (`ast.Str`, line 38-39, 45-46), `@app.cell` without `return` statement (line 90-93 `end_lineno` fallback).

- [ ] **Step 1: Write tests for uncovered marimo branches**

Add to `tests/test_loaders/test_marimo.py`:

```python
class TestMarimoEdgeCases:
    def test_annotated_assignment_generated_with(self):
        """Marimo v0.8+ uses annotated assignment for __generated_with."""
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "__generated_with: str = \"0.8.0\"\n"
            "app = marimo.App()\n"
            "\n"
            "@app.cell\n"
            "def f():\n"
            "    x = 1\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert doc.metadata.get("generated_with") == "0.8.0"

    def test_cell_decorator_without_app(self):
        """The @cell decorator (without app.) should still be recognized."""
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "app = marimo.App()\n"
            "\n"
            "@cell\n"
            "def f():\n"
            "    x = 1\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 1

    def test_empty_marimo_no_syntax_error(self):
        """Empty string should not cause a SyntaxError."""
        loader = MarimoLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_syntax_error_returns_empty(self):
        """Invalid Python should return empty notebook."""
        loader = MarimoLoader()
        doc = loader.loads("import marimo\n\n@app.cell\ndef (\n")
        assert len(doc.cells) == 0
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_loaders/test_marimo.py -v --tb=short`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_loaders/test_marimo.py
git commit -m "test: add edge case coverage for marimo loader"
```

---

### Task 1.5: Close Remaining Coverage Holes

**Files:**
- Modify: `notebookllm/loaders/markdown.py`, `notebookllm/utils/detect.py`, `notebookllm/cli/commands.py`, `notebookllm/mcp/session.py`
- Test: Various test files

**Context:** Small remaining misses — YAML frontmatter parse error, RAW cell in markdown dumper, `detect_format` file read error, session key error in `get_filepath`, CLI `server` transport paths.

- [ ] **Step 1: Write tests for remaining uncovered lines**

Add to `tests/test_loaders/test_markdown.py`:

```python
def test_load_bad_frontmatter(self):
    """Invalid YAML frontmatter should not crash."""
    loader = MarkdownLoader()
    text = "---\n  broken yaml : [\n---\n\nHello\n"
    doc = loader.loads(text)
    assert doc.metadata == {}
    assert len(doc.cells) >= 1
```

Add to `tests/test_loaders/test_detect.py`:

```python
def test_py_read_error_fallback(self, tmp_path, monkeypatch):
    """If reading .py file fails, fallback to treating as percent."""
    f = tmp_path / "script.py"
    f.write_text("import marimo\n")
    # Mock read to fail
    original_read_text = f.read_text
    def failing_read(*args, **kwargs):
        raise OSError("read failed")
    monkeypatch.setattr(Path, "read_text", failing_read)
    assert detect_format(f) == "percent"
```

Add to `tests/test_mcp_session.py`:

```python
def test_get_filepath_nonexistent(self, manager):
    with pytest.raises(KeyError, match="Session not found"):
        manager.get_filepath("missing")
```

- [ ] **Step 2: Remove dead CLI code**

In `notebookllm/cli/commands.py`, the `server` command `main(transport=transport)` at lines 95-96 is never called directly from test. Remove the dead code at line 96:

```python
def server(transport: str):
    """Start MCP server."""
    from notebookllm.mcp.server import main
    main(transport=transport)  # This is the only line — keep it
```

The actual dead-path issues are in `search` command line 72-73 (no matches branch) and `load_file` error paths. These are already tested via CLI tests.

- [ ] **Step 3: Run full coverage check**

Run: `uv run pytest --cov=notebookllm --cov-report=term-missing --tb=short -q`

Expected: Coverage increased to **90%+**

- [ ] **Step 4: Commit**

```bash
git add tests/ notebookllm/
git commit -m "test: close remaining coverage holes to 90%+"
```

---

## Phase 2: Token Analytics & Benchmark Harness

### Task 2.1: Token Counter Utility

**Files:**
- Create: `notebookllm/utils/tokenizer.py`
- Create: `tests/test_loaders/test_tokenizer.py`

**Context:** The primary value prop of notebookllm is "reduce token usage by up to 80%." But there's no actual token counting — users can't verify the savings. We need a token counter that estimates tokens for a given text string, optionally with per-cell breakdown.

- [ ] **Step 1: Design the token counter API**

The tokenizer module will:
1. Count tokens using `tiktoken` (for OpenAI models) with fallback to a character-based estimate (~4 chars/token)
2. Accept an optional `encoding_name` parameter (default: "cl100k_base" for GPT-4)
3. Provide a `count_tokens(text: str, encoding_name: str = "cl100k_base") -> int` function
4. Provide a `NotebookTokenReport` dataclass for per-cell breakdown
5. Integrate into `NotebookDocument.token_breakdown()` method

- [ ] **Step 2: Write token counter tests**

Create `tests/test_loaders/test_tokenizer.py`:

```python
"""Tests for notebookllm.utils.tokenizer — token counting utilities."""
import pytest

from notebookllm.utils.tokenizer import NotebookTokenReport, count_tokens, tokenize_notebook
from notebookllm.models import Cell, CellType, NotebookDocument


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_simple_text(self):
        count = count_tokens("Hello, world!")
        assert count > 0

    def test_code_vs_markdown(self):
        code = 'import pandas as pd\ndf = pd.read_csv("data.csv")\nprint(df.head())'
        md = "# Analysis\n\nThis is a gentle introduction to pandas."
        code_tokens = count_tokens(code)
        md_tokens = count_tokens(md)
        assert code_tokens > 0
        assert md_tokens > 0

    def test_encoding_fallback(self, monkeypatch):
        """When tiktoken is not available, fall back to character estimate."""
        monkeypatch.setattr("notebookllm.utils.tokenizer.tiktoken", None)
        count = count_tokens("Hello, world! This is a test of the fallback estimator.")
        assert count > 0

    def test_custom_encoding(self):
        count = count_tokens("Hello", encoding_name="r50k_base")
        assert count > 0

    def test_unknown_encoding(self):
        """Unknown encoding should fall back gracefully."""
        count = count_tokens("Hello", encoding_name="nonexistent_encoding")
        assert count > 0

    def test_large_text(self):
        text = "word " * 10000
        count = count_tokens(text)
        assert count > 0
        # ~2500 tokens for 10000 words (roughly 4 chars/token)
        assert 1500 < count < 10000


class TestTokenizeNotebook:
    def test_empty_notebook(self):
        doc = NotebookDocument()
        report = tokenize_notebook(doc)
        assert report.total_tokens == 0
        assert len(report.cell_tokens) == 0

    def test_notebook_with_cells(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        report = tokenize_notebook(doc, mode="minimal")
        assert report.total_tokens > 0
        assert len(report.cell_tokens) == 2
        assert report.cell_tokens[0].cell_index == 0
        assert report.cell_tokens[1].cell_index == 1

    def test_token_report_includes_mode(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        report_minimal = tokenize_notebook(doc, mode="minimal")
        report_full = tokenize_notebook(doc, mode="full")
        assert report_minimal.mode == "minimal"
        assert report_full.mode == "full"

    def test_token_count_varies_by_mode(self):
        """FULL mode should produce more tokens than MINIMAL for cells with outputs."""
        doc = NotebookDocument()
        from notebookllm.models import CellOutput
        doc.add_cell(Cell(
            cell_type=CellType.CODE, source="print('hello')",
            outputs=[CellOutput(output_type="stream", content="hello\n", name="stdout")],
        ))
        minimal_tokens = tokenize_notebook(doc, mode="minimal").total_tokens
        full_tokens = tokenize_notebook(doc, mode="full").total_tokens
        assert full_tokens >= minimal_tokens
```

- [ ] **Step 3: Run the (failing) tests**

Run: `uv run pytest tests/test_loaders/test_tokenizer.py -v`

Expected: FAIL with ImportError — module doesn't exist yet

- [ ] **Step 4: Implement token counter**

Create `notebookllm/utils/tokenizer.py`:

```python
"""Token counting utilities for notebookllm — estimate LLM token usage.

Uses tiktoken when available, falls back to character-based estimation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from notebookllm.models import NotebookDocument, OutputMode

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore[assignment]

# Default encoding for OpenAI models (GPT-4, GPT-3.5-turbo, etc.)
DEFAULT_ENCODING = "cl100k_base"
# Fallback: ~4 characters per token for English text
CHARS_PER_TOKEN = 4.0


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count the number of tokens in text.

    Uses tiktoken for accurate counts with OpenAI-compatible encodings.
    Falls back to character-based estimation (~4 chars/token) when tiktoken
    is not installed or the encoding is unknown.
    """
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except (KeyError, ValueError):
            pass

    # Fallback: character-based estimation
    return max(1, int(len(text) / CHARS_PER_TOKEN))


@dataclass
class CellTokenInfo:
    """Token usage for a single cell."""
    cell_index: int
    cell_type: str
    tokens: int
    preview: str


@dataclass
class NotebookTokenReport:
    """Token usage report for an entire notebook."""
    total_tokens: int
    cell_tokens: list[CellTokenInfo] = field(default_factory=list)
    mode: str = "minimal"
    num_cells: int = 0

    @property
    def token_summary(self) -> str:
        """Human-readable summary of token usage."""
        if not self.cell_tokens:
            return "Empty notebook (0 tokens)"
        return (
            f"Total: {self.total_tokens} tokens across {self.num_cells} cells"
            f" ({self.mode} mode)"
        )


def tokenize_notebook(
    doc: NotebookDocument,
    mode: str = "minimal",
    encoding_name: str = DEFAULT_ENCODING,
) -> NotebookTokenReport:
    """Analyze token usage of a notebook in the given output mode."""
    output_mode = OutputMode(mode)
    full_text = doc.to_text(mode=output_mode)
    total = count_tokens(full_text, encoding_name=encoding_name)

    cell_tokens: list[CellTokenInfo] = []
    for i, cell in enumerate(doc.cells):
        # Estimate per-cell tokens by counting individual cell text
        cell_text = cell.source
        ct = count_tokens(cell_text, encoding_name=encoding_name)
        preview = cell.source[:50].replace("\n", " ")
        cell_tokens.append(CellTokenInfo(
            cell_index=i, cell_type=cell.cell_type.value,
            tokens=ct, preview=preview,
        ))

    return NotebookTokenReport(
        total_tokens=total,
        cell_tokens=cell_tokens,
        mode=mode,
        num_cells=len(doc.cells),
    )
```

- [ ] **Step 5: Integrate token counting into NotebookDocument**

Modify `notebookllm/models.py`. Add import and method to `NotebookDocument`:

```python
def token_breakdown(self, mode: OutputMode = OutputMode.MINIMAL) -> NotebookTokenReport:
    """Get token usage breakdown for this notebook."""
    from notebookllm.utils.tokenizer import tokenize_notebook
    return tokenize_notebook(self, mode=mode.value)
```

Add to imports in `models.py`:
```python
from __future__ import annotations
# (already present)
```

- [ ] **Step 6: Add model to __init__.py exports**

Modify `notebookllm/__init__.py`:

```python
from notebookllm.utils.tokenizer import NotebookTokenReport, count_tokens, tokenize_notebook

__all__ = [
    # ... existing items ...
    "count_tokens",
    "tokenize_notebook",
    "NotebookTokenReport",
]
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/test_loaders/test_tokenizer.py -v`

Expected: PASS (7 tests)

- [ ] **Step 8: Commit**

```bash
git add notebookllm/utils/tokenizer.py notebookllm/models.py notebookllm/__init__.py tests/test_loaders/test_tokenizer.py
git commit -m "feat: add token counting utility with tiktoken support"
```

---

### Task 2.2: Add `tiktoken` to Optional Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add tiktoken optional dep**

Modify `pyproject.toml`:

```toml
[project.optional-dependencies]
token = [
    "tiktoken>=0.7",
]
all = [
    "notebookllm[cli,mcp,execute,stream,yaml,token]",
]
```

- [ ] **Step 2: Verify install**

Run: `uv pip install -e ".[token]" && uv run python -c "import tiktoken; print(tiktoken.__version__)"`

Expected: Version string printed

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add tiktoken as optional [token] dependency"
```

---

### Task 2.3: Token CLI Command

**Files:**
- Modify: `notebookllm/cli/commands.py`
- Test: `tests/test_cli.py`

**Context:** Users should be able to run `notebookllm tokens notebook.ipynb` to get a token usage report.

- [ ] **Step 1: Write CLI test for token command**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run test (should fail)**

Run: `uv run pytest tests/test_cli.py -v --tb=short -k "token"`

Expected: FAIL — "No such command 'tokens'"

- [ ] **Step 3: Implement token CLI command**

Add to `notebookllm/cli/commands.py`:

```python
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="Output mode for token estimation")
@click.option("--breakdown", is_flag=True, help="Show per-cell token breakdown")
def tokens(file: str, mode: str, breakdown: bool):
    """Estimate token usage for a notebook."""
    doc = _load_or_abort(file)
    from notebookllm.utils.tokenizer import tokenize_notebook
    report = tokenize_notebook(doc, mode=mode)
    click.echo(report.token_summary)
    if breakdown and report.cell_tokens:
        click.echo()
        for ct in report.cell_tokens:
            click.echo(f"  [{ct.cell_index:4d}] {ct.cell_type:10s} {ct.tokens:6d}  {ct.preview}")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli.py -v --tb=short -k "token"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/cli/commands.py tests/test_cli.py
git commit -m "feat: add tokens CLI command for token estimation"
```

---

### Task 2.4: Benchmark Harness

**Files:**
- Create: `tests/benchmarks/test_speed.py`
- Create: `tests/benchmarks/test_token_efficiency.py`
- Create: `tests/benchmarks/__init__.py`
- Modify: `pyproject.toml`

**Context:** A standardized benchmark suite lets us track performance regressions and verify optimization claims (like "80% token reduction"). We'll use `pytest-benchmark` for speed and custom assertions for token efficiency.

- [ ] **Step 1: Add pytest-benchmark dev dependency**

Modify `pyproject.toml`:

```toml
dev = [
    # ... existing deps ...
    "pytest-benchmark>=4.0",
]
```

- [ ] **Step 2: Write speed benchmark**

Create `tests/benchmarks/__init__.py`:
```python
"""Benchmark suite for notebookllm."""
```

Create `tests/benchmarks/test_speed.py`:
```python
"""Speed benchmarks for notebookllm loaders and converters."""
from pathlib import Path

import pytest

from notebookllm.loaders import dump_file, load_file
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadSpeed:
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
    def test_to_text_minimal_speed(self, benchmark):
        doc = load_file(FIXTURES / "sample.ipynb")
        result = benchmark(doc.to_text)
        assert len(result) > 0

    def test_to_text_full_speed(self, benchmark):
        doc = load_file(FIXTURES / "sample.ipynb")
        from notebookllm.models import OutputMode
        result = benchmark(doc.to_text, mode=OutputMode.FULL)
        assert len(result) > 0

    def test_dump_ipynb_speed(self, benchmark):
        doc = load_file(FIXTURES / "sample.ipynb")
        result = benchmark(dump_file, doc, Path("/dev/null"))
        assert result is not None


class TestLargeFileSpeed:
    """Speed benchmarks for large notebook processing (requires streaming)."""

    @pytest.mark.slow
    def test_stream_large_notebook_speed(self, benchmark, tmp_path):
        from tests.test_loaders.test_ipynb import _generate_large_notebook
        from notebookllm.loaders.ipynb import IpynbLoader

        nb_path = _generate_large_notebook(tmp_path, 10000)
        loader = IpynbLoader()
        loader.streaming_threshold = 0

        doc = benchmark(loader.load, nb_path)
        assert len(doc.cells) == 10000
```

- [ ] **Step 3: Write token efficiency benchmark**

Create `tests/benchmarks/test_token_efficiency.py`:
```python
"""Token efficiency benchmarks — verify LLM token reduction claims."""
from pathlib import Path

import pytest

from notebookllm.loaders import load_file
from notebookllm.models import NotebookDocument, OutputMode

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
    def _count_raw_tokens(doc: NotebookDocument) -> int:
        """Simulate raw token count of the original ipynb JSON."""
        import json
        from notebookllm.loaders.ipynb import IpynbDumper
        dumper = IpynbDumper()
        raw_json = dumper.dump(doc)
        return count_tokens(raw_json)

    def test_minimal_vs_raw_reduction(self):
        """MINIMAL mode should use fewer tokens than the raw .ipynb JSON."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        minimal_text = doc.to_text(mode=OutputMode.MINIMAL)
        minimal_tokens = count_tokens(minimal_text)
        assert minimal_tokens < raw_tokens, (
            f"MINIMAL ({minimal_tokens}) should be less than raw ({raw_tokens})"
        )

    def test_minimal_vs_full_tokens(self):
        """MINIMAL should use fewer tokens than FULL mode."""
        doc = load_file(FIXTURES / "sample.ipynb")
        minimal = count_tokens(doc.to_text(mode=OutputMode.MINIMAL))
        full = count_tokens(doc.to_text(mode=OutputMode.FULL))
        assert minimal <= full, f"MINIMAL ({minimal}) > FULL ({full})"

    def test_token_reduction_percentage(self):
        """MINIMAL mode should reduce tokens by at least 50% vs raw .ipynb."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        minimal_text = doc.to_text(mode=OutputMode.MINIMAL)
        minimal_tokens = count_tokens(minimal_text)
        reduction = (raw_tokens - minimal_tokens) / raw_tokens * 100
        assert reduction >= 50, (
            f"Token reduction only {reduction:.1f}% (expected >= 50%)"
        )

    def test_token_reduction_with_outputs(self):
        """FULL mode should still provide reduction vs raw for notebooks with outputs."""
        doc = load_file(FIXTURES / "sample.ipynb")
        raw_tokens = self._count_raw_tokens(doc)
        full_text = doc.to_text(mode=OutputMode.FULL)
        full_tokens = count_tokens(full_text)
        reduction = (raw_tokens - full_tokens) / raw_tokens * 100
        assert reduction >= 40, (
            f"FULL mode reduction only {reduction:.1f}% (expected >= 40%)"
        )
```

- [ ] **Step 4: Run the benchmark tests**

Run: `uv run pytest tests/benchmarks/ -v --tb=short`

Expected: Speed benchmarks run and pass. Token efficiency benchmarks may skip if tokenizer module not available.

- [ ] **Step 5: Mark slow benchmarks**

Add `pytest.ini_options` to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
markers = [
    "slow: marks tests as slow (e.g., large notebook streaming)",
]
```

- [ ] **Step 6: Commit**

```bash
git add tests/benchmarks/ pyproject.toml
git commit -m "feat: add benchmark harness for speed and token efficiency"
```

---

## Phase 3: Format Expansion

### Task 3.1: R Markdown Support (.Rmd)

**Files:**
- Create: `notebookllm/loaders/rmarkdown.py`
- Create: `tests/test_loaders/test_rmarkdown.py`
- Modify: `notebookllm/loaders/__init__.py`
- Modify: `notebookllm/utils/detect.py`
- Add: `tests/fixtures/sample_rmarkdown.Rmd`

**Context:** `.Rmd` files are currently detected as "markdown". They should be detected as a distinct format that properly handles R code chunks and YAML frontmatter. R Markdown uses ````{r}` code chunks (like Quarto but with `r` instead of `python`).

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_rmarkdown.Rmd`:
```rmd
---
title: "R Analysis"
author: "Data Scientist"
output: html_document
---

## Setup

Load libraries and data.

```{r}
library(ggplot2)
data(mtcars)
```

## Visualization

```{r scatterplot, echo=FALSE}
ggplot(mtcars, aes(x=wt, y=mpg)) +
  geom_point() +
  geom_smooth(method="lm")
```

## Summary

```{python}
# Python cell inside Rmd
import pandas as pd
print("hello from python")
```
```

- [ ] **Step 2: Write R Markdown loader tests**

Create `tests/test_loaders/test_rmarkdown.py`:

```python
"""Tests for notebookllm.loaders.rmarkdown — R Markdown format (.Rmd)."""
from pathlib import Path

from notebookllm.loaders.rmarkdown import RMarkdownLoader, RMarkdownDumper
from notebookllm.models import Cell, CellType, NotebookDocument

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestRMarkdownLoader:
    def test_load_sample(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        assert isinstance(doc, NotebookDocument)
        assert doc.source_format == "rmarkdown"
        assert len(doc.cells) >= 2

    def test_preserves_r_code_cells(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        r_cells = [c for c in code_cells if c.metadata.get("language") == "r"]
        assert len(r_cells) >= 1

    def test_preserves_python_code_cells(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        py_cells = [c for c in code_cells if c.metadata.get("language") == "python"]
        assert len(py_cells) >= 1

    def test_loads_markdown_between_chunks(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        md_cells = [c for c in doc.cells if c.cell_type == CellType.MARKDOWN]
        assert len(md_cells) >= 1

    def test_parses_frontmatter(self):
        loader = RMarkdownLoader()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        assert doc.metadata.get("title") == "R Analysis"

    def test_load_no_frontmatter(self):
        loader = RMarkdownLoader()
        text = "```{r}\nx <- 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1

    def test_empty_file(self):
        loader = RMarkdownLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_loads_from_string(self):
        loader = RMarkdownLoader()
        text = "```{r}\nx <- 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE


class TestRMarkdownDumper:
    def test_dump_to_string(self):
        dumper = RMarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x <- 1", metadata={"language": "r"}))
        result = dumper.dump(doc)
        assert "```{r}" in result
        assert "x <- 1" in result

    def test_dump_mixed_cells(self):
        dumper = RMarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="## Setup"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x <- 1", metadata={"language": "r"}))
        result = dumper.dump(doc)
        assert "## Setup" in result
        assert "```{r}" in result

    def test_roundtrip(self):
        loader = RMarkdownLoader()
        dumper = RMarkdownDumper()
        doc = loader.load(FIXTURES / "sample_rmarkdown.Rmd")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
```

- [ ] **Step 3: Run tests (should fail)**

Run: `uv run pytest tests/test_loaders/test_rmarkdown.py -v`

Expected: FAIL — ImportError

- [ ] **Step 4: Implement R Markdown loader/dumper**

Create `notebookllm/loaders/rmarkdown.py`:

```python
"""R Markdown format loader/dumper — .Rmd files with ```{r} chunks."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
R_CHUNK_RE = re.compile(r"```\{(\w+)\}\s*\n(.*?)```", re.DOTALL)


class RMarkdownLoader(BaseLoader):
    """Load .Rmd files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells: list[Cell] = []
        metadata: dict[str, object] = {}

        fm_match = FRONTMATTER_RE.match(content)
        if fm_match:
            try:
                metadata = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                metadata = {}
            content = content[fm_match.end():]

        last_end = 0
        for match in R_CHUNK_RE.finditer(content):
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            lang = match.group(1)
            code = match.group(2).strip()
            cell_metadata: dict[str, object] = {"language": lang}

            if lang in ("r", "python", "julia"):
                cells.append(Cell(
                    cell_type=CellType.CODE, source=code, metadata=cell_metadata,
                ))
            else:
                cells.append(Cell(
                    cell_type=CellType.RAW, source=code, metadata=cell_metadata,
                ))

            last_end = match.end()

        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="rmarkdown")


class RMarkdownDumper(BaseDumper):
    """Dump to .Rmd format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []
        if doc.metadata:
            parts.append("---")
            parts.append(yaml.dump(doc.metadata, default_flow_style=False).strip())
            parts.append("---")
            parts.append("")

        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                lang = cell.metadata.get("language", "r") if cell.metadata else "r"
                parts.append(f"```{{{lang}}}")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                lang = cell.metadata.get("language", "raw") if cell.metadata else "raw"
                parts.append(f"```{{{lang}}}")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
```

- [ ] **Step 5: Update format detection**

Modify `notebookllm/utils/detect.py`:

In `detect_format()`, add `.Rmd` case before `.md`:
```python
elif ext == ".rmd":
    return "rmarkdown"
```

Remove `.rmd` from the `markdown` case (currently line 19):
```python
elif ext in (".md",):
    return "markdown"
```

In `detect_text_format()`, add R Markdown detection before quarto:
```python
# Check for R Markdown chunks
for line in lines:
    stripped = line.strip()
    if stripped.startswith("```{r}"):
        return "rmarkdown"
```

- [ ] **Step 6: Update dispatch**

Modify `notebookllm/loaders/__init__.py`:

In `load_file()`, add after quarto block:
```python
elif fmt == "rmarkdown":
    from notebookllm.loaders.rmarkdown import RMarkdownLoader
    return RMarkdownLoader().load(filepath)
```

In `dump_file()`, add:
```python
elif fmt == "rmarkdown":
    from notebookllm.loaders.rmarkdown import RMarkdownDumper
    RMarkdownDumper().dump(doc, filepath)
```

In `loads_text()`, add:
```python
elif source_format == "rmarkdown":
    from notebookllm.loaders.rmarkdown import RMarkdownLoader
    return RMarkdownLoader().loads(text)
```

Update `validate_output_format()` in `notebookllm/utils/validation.py`:
```python
valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown"}
```

- [ ] **Step 7: Add roundtrip test**

Add to `tests/test_roundtrip.py`:

```python
class TestRMarkdownRoundtrip:
    def test_roundtrip_via_dispatch(self, tmp_path):
        doc = load_file(FIXTURES / "sample_rmarkdown.Rmd")
        out = tmp_path / "roundtrip.Rmd"
        dump_file(doc, out)
        doc2 = load_file(out)
        assert len(doc2.cells) == len(doc.cells)
        assert doc2.source_format == "rmarkdown"

    def test_rmd_to_percent(self, tmp_path):
        doc = load_file(FIXTURES / "sample_rmarkdown.Rmd")
        out = tmp_path / "converted.py"
        dump_file(doc, out)
        doc2 = load_file(out)
        assert doc2.source_format == "percent"
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/test_loaders/test_rmarkdown.py tests/test_roundtrip.py -v --tb=short`

Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add notebookllm/loaders/rmarkdown.py notebookllm/loaders/__init__.py notebookllm/utils/detect.py notebookllm/utils/validation.py tests/test_loaders/test_rmarkdown.py tests/test_roundtrip.py tests/fixtures/sample_rmarkdown.Rmd
git commit -m "feat: add R Markdown (.Rmd) format support"
```

---

### Task 3.2: Update README for R Markdown

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README format list**

Change "Multi-format support" bullet to include `R Markdown`:
```markdown
- **Multi-format support**: Load and save `.ipynb`, percent scripts (`# %%`), Quarto, Markdown, Marimo, and R Markdown formats.
```

Update the output formats list:
```markdown
Output formats: `ipynb`, `percent` (`# %%` markers), `quarto` (`.qmd`), `markdown`, `marimo`, `rmarkdown` (`.Rmd`).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document R Markdown format support"
```

---

## Phase 4: Script Export (Flat .py)

### Task 4.1: ScriptFormat Dumper

**Files:**
- Create: `notebookllm/loaders/script.py`
- Create: `tests/test_loaders/test_script.py`
- Modify: `notebookllm/loaders/__init__.py`
- Modify: `notebookllm/utils/validation.py`

**Context:** Unlike percent format (which uses `# %%` markers), script format produces a plain `.py` file — code cells concatenated, markdown cells as comments, raw cells as comments. This is useful for running notebooks as standalone scripts.

- [ ] **Step 1: Write script format tests**

Create `tests/test_loaders/test_script.py`:

```python
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
        comment_lines = [l for l in lines if l.startswith("#")]
        assert any("Title" in l for l in comment_lines)

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
```

- [ ] **Step 2: Run tests (should fail)**

Run: `uv run pytest tests/test_loaders/test_script.py -v`

Expected: FAIL — ImportError

- [ ] **Step 3: Implement script dumper**

Create `notebookllm/loaders/script.py`:

```python
"""Script format dumper — flat .py without cell markers.

Converts notebooks to standalone scripts: code cells become code,
markdown/raw cells become comments. This is a ONE-WAY export format
(no loader) — there's no way to reconstruct cell boundaries from
a flat script.
"""
from __future__ import annotations

from pathlib import Path

from notebookllm.loaders.base import BaseDumper
from notebookllm.models import CellType, NotebookDocument


class ScriptDumper(BaseDumper):
    """Dump to flat script format (no cell markers)."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                parts.append(cell.source.rstrip("\n"))
            elif cell.cell_type == CellType.MARKDOWN:
                # Markdown becomes comment lines
                for line in cell.source.split("\n"):
                    if line.strip():
                        parts.append(f"# {line}")
                    else:
                        parts.append("#")
            elif cell.cell_type == CellType.RAW:
                for line in cell.source.split("\n"):
                    if line.strip():
                        parts.append(f"# {line}")
                    else:
                        parts.append("#")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
```

- [ ] **Step 4: Register script format in dispatch**

Modify `notebookllm/loaders/__init__.py`:

In `dump_file()` function, add before the `else`:
```python
elif fmt == "script":
    from notebookllm.loaders.script import ScriptDumper
    ScriptDumper().dump(doc, filepath)
```

- [ ] **Step 5: Add "script" to valid formats**

In `notebookllm/utils/validation.py`:
```python
valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown", "script"}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_loaders/test_script.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebookllm/loaders/script.py notebookllm/loaders/__init__.py notebookllm/utils/validation.py tests/test_loaders/test_script.py
git commit -m "feat: add script format dumper (flat .py export)"
```

---

## Phase 5: CI/CD & Infrastructure

### Task 5.1: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Context:** No CI pipeline exists. Every PR should run: lint (ruff), type check (mypy), tests (pytest with coverage), and build check.

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --group dev

      - name: Lint with ruff
        run: uv run ruff check .

      - name: Type check with mypy
        run: uv run mypy notebookllm

      - name: Test with pytest
        run: uv run pytest --cov=notebookllm --cov-report=xml --tb=short -q

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

- [ ] **Step 2: Verify workflow syntax**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('Valid YAML')"`

Expected: "Valid YAML"

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI with ruff, mypy, pytest"
```

---

### Task 5.2: Sphinx Docs Build Fix

**Files:**
- Modify: `docs/Makefile` (if exists) or `docs/conf.py`

**Context:** The Sphinx docs exist but don't build locally because `sphinx` and `sphinx_rtd_theme` are not in the dev dependencies.

- [ ] **Step 1: Add Sphinx deps to pyproject.toml**

Modify `pyproject.toml`:

```toml
dev = [
    # ... existing deps ...
    "sphinx>=7.0",
    "sphinx-rtd-theme>=2.0",
]

docs = [
    "sphinx>=7.0",
    "sphinx-rtd-theme>=2.0",
]
```

- [ ] **Step 2: Fix Sphinx autodoc imports**

Ensure `docs/conf.py` can find the package. The current `sys.path.insert` may fail if running from the wrong directory. Add a `Makefile` fix or a `docs/requirements.txt`.

Create `docs/requirements.txt`:
```
sphinx>=7.0
sphinx-rtd-theme>=2.0
```

- [ ] **Step 3: Verify build**

Run: `uv pip install sphinx sphinx-rtd-theme && cd docs && uv run make html 2>&1 | tail -20`

Expected: Build succeeds, output in `docs/_build/html/`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml docs/requirements.txt
git commit -m "build: add Sphinx docs dependencies and requirements"
```

---

## Phase 6: MCP Server Enhancements

### Task 6.1: Token Tool for MCP

**Files:**
- Modify: `notebookllm/mcp/server.py`
- Test: `tests/test_mcp.py`

**Context:** The MCP server should expose a `count_tokens` tool that analyzes token usage for a session notebook.

- [ ] **Step 1: Write MCP token tool test**

Add to `tests/test_mcp.py`, inside `TestMCPAppCreation` or a new class:

```python
@pytest.mark.asyncio
class TestMCPTokenTool:
    async def test_count_tokens(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("count_tokens", {
            "session_id": "test-session",
        })
        text = _get_text(result)
        assert "tokens" in text.lower()

    async def test_count_tokens_missing_session(self, app):
        result = await app.call_tool("count_tokens", {"session_id": "missing"})
        assert "not found" in _get_text(result).lower()

    async def test_count_tokens_with_mode(self, app_with_session):
        app, _ = app_with_session
        result = await app.call_tool("count_tokens", {
            "session_id": "test-session",
            "mode": "full",
        })
        text = _get_text(result)
        assert "tokens" in text.lower()
```

- [ ] **Step 2: Run test (should fail)**

Run: `uv run pytest tests/test_mcp.py::TestMCPTokenTool -v`

Expected: FAIL — tool not found

- [ ] **Step 3: Implement token tool in MCP server**

Add to `notebookllm/mcp/server.py`, inside `create_app()`:

```python
@mcp.tool()
def count_tokens(session_id: str, mode: str = "minimal") -> str:
    """Count tokens in the session notebook."""
    doc = _get_doc_safe(session_manager, session_id)
    if doc is None:
        return f"Session not found: {session_id}"
    from notebookllm.utils.tokenizer import tokenize_notebook
    report = tokenize_notebook(doc, mode=mode)
    return report.token_summary
```

- [ ] **Step 4: Update tool count assertion**

In `test_create_app`, update `len(tool_names) == 11` to `len(tool_names) == 12`.

- [ ] **Step 5: Update README tool table**

Add to README tool table:
```markdown
| `count_tokens` | Count tokens in the session notebook (modes: minimal, standard, full) |
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_mcp.py -v --tb=short`

Expected: All MCP tests pass

- [ ] **Step 7: Commit**

```bash
git add notebookllm/mcp/server.py tests/test_mcp.py README.md
git commit -m "feat: add count_tokens tool to MCP server"
```

---

## Phase 7: Final Verification & Polish

### Task 7.1: End-to-End Coverage Gate

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest --cov=notebookllm --cov-report=term-missing --tb=short -q
```

Expected: All tests pass. Target coverage: **90%+** overall.

Current targets per module:
- `mcp/server.py`: 85%+ (from 67%)
- `loaders/ipynb.py`: 90%+ (from 81%)
- `converters/llm_optimizer.py`: 95%+ (from 81%)
- `loaders/marimo.py`: 92%+ (from 80%)
- All others: 95%+

- [ ] **Step 2: Run benchmark suite**

```bash
uv run pytest tests/benchmarks/ -v --tb=short
```

Expected: All benchmarks pass. Record baseline times.

- [ ] **Step 3: Run all quality gates**

```bash
uv run ruff check . && uv run mypy notebookllm && echo "Quality gates PASS"
```

Expected: ruff 0 errors, mypy 0 errors

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final polish and coverage improvements"
```

---

## Appendix A: Architecture Map

```
notebookllm/
├── __init__.py              # Public API exports
├── models.py                # Core: NotebookDocument, Cell, CellType, OutputMode
├── cli/
│   └── commands.py           # CLI entry points (convert, inspect, search, get, server, tokens)
├── converters/
│   └── llm_optimizer.py      # Notebook → LLM-optimized text (minimal/standard/full)
├── loaders/
│   ├── base.py               # BaseLoader, BaseDumper ABCs
│   ├── ipynb.py              # .ipynb loader/dumper (with ijson streaming)
│   ├── percent.py            # .py percent format (# %% markers)
│   ├── marimo.py             # .py marimo format (@app.cell decorators)
│   ├── markdown.py           # .md format (```python blocks)
│   ├── quarto.py             # .qmd format
│   ├── rmarkdown.py          # .Rmd format [NEW]
│   ├── script.py             # Flat .py export (no markers) [NEW]
│   └── __init__.py           # Format dispatch (load_file, dump_file, loads_text)
├── mcp/
│   ├── server.py             # MCP server (11→12 tools)
│   └── session.py            # SessionManager
└── utils/
    ├── detect.py             # Format detection (extension + content sniffing)
    ├── validation.py         # Input validation utilities
    └── tokenizer.py          # Token counting [NEW]
```

## Appendix B: Dependency Graph

```
Phase 1 (Coverage) ──→ Phase 5 (CI/CD)
     │                        │
     ├──→ Phase 2 (Tokens) ───┤
     │         │               │
     │         └──→ Phase 6 (MCP Token Tool)
     │
     ├──→ Phase 3 (R Markdown)
     │
     └──→ Phase 4 (Script Export)
                           │
                           └──→ Phase 7 (Final Verification)

Phases 1, 3, 4 can run in PARALLEL (independent).
Phase 2 must run before Phase 6.
Phase 7 must run last (integrates everything).
```

## Appendix C: Benchmark Baseline Targets

| Benchmark | Target | Measurement |
|-----------|--------|-------------|
| Load .ipynb (3 cells) | <10ms | pytest-benchmark |
| Load .ipynb (10,000 cells, streaming) | <2s | time.monotonic() |
| to_text MINIMAL | <1ms | pytest-benchmark |
| to_text FULL | <2ms | pytest-benchmark |
| Token reduction (MINIMAL vs raw) | >=50% | token_efficiency test |
| Token reduction (FULL vs raw) | >=40% | token_efficiency test |
| Memory (10,000 cell streaming) | <200MB | via memory_profiler (optional) |
