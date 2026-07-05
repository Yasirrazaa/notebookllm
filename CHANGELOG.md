# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-07-05

### Major — Package Unification

The two previously separate packages — `notebookllm` and `notebookllm-mcp` — have been unified into a single `notebookllm` package. This eliminates dependency drift, version mismatch, and the confusion of maintaining two repos that must always be in sync.

**Before (separate packages):**

| Package | Version | Purpose |
|---------|---------|---------|
| `notebookllm` | 1.1.0 / 2.0 | Core conversion library + basic MCP server |
| `notebookllm-mcp` | 0.4.0 / 2.0.11 | Standalone MCP server wrapping notebookllm |

**After (unified):**

| Package | Version | Purpose |
|---------|---------|---------|
| `notebookllm` | 2.0.0 | Everything — core, CLI, MCP server, token counting |

The old `notebookllm-mcp` package is deprecated. Users should migrate to `notebookllm[mcp]`.

---

### Added

#### 8 Notebook Formats (was: 1)
- **`ipynb`** — Jupyter Notebook (original format, now with streaming for large files)
- **`percent`** — Python with `# %%` cell markers (old plain-text format, now proper format)
- **`quarto`** — Quarto `.qmd` documents with YAML frontmatter and code chunks
- **`markdown`** — Standard `.md` with fenced code blocks
- **`marimo`** — Marimo reactive notebooks with `@app.cell` decorators (AST-parsed)
- **`rmarkdown`** — R Markdown `.Rmd` with R/Python code blocks
- **`deepnote`** — Deepnote YAML project format with block groups and content hashing
- **`script`** — Flat `.py` export (one-way: markdown/raw → comments)

#### Format-Agnostic Canonical Intermediate Representation (CIR)
- `NotebookDocument` — universal notebook container (was: `nbformat.NotebookNode` wrapper)
- `Cell` dataclass with `cell_type`, `source`, `execution_count`, `outputs`, `metadata`, `cell_id`, plus Deepnote-compatible fields (`language`, `block_type`, `block_group`, `content_hash`, `sorting_key`)
- `CellType` enum (`CODE`, `MARKDOWN`, `RAW`)
- `CellOutput` dataclass for unified output representation
- `OutputMode` enum (`MINIMAL`, `STANDARD`, `FULL`)
- Serialization via `to_json()` / `from_json()` with version-tolerant schema (CIR v2)

#### Loader/Dumper Architecture
- `BaseLoader` / `BaseDumper` abstract base classes
- Format-specific implementations: `IpynbLoader/Dumper`, `PercentLoader/Dumper`, `QuartoLoader/Dumper`, `MarkdownLoader/Dumper`, `MarimoLoader/Dumper`, `RMarkdownLoader/Dumper`, `DeepnoteLoader/Dumper`, `ScriptDumper`
- Auto-detection via `detect_format()` (file extension) and `detect_text_format()` (content sniffing)
- `load_file()`, `dump_file()`, `loads_text()` dispatch functions

#### LLM-Optimized Text Output (4 modes)
- **`minimal`** — `# %% [type]` markers + source only (default)
- **`standard`** — Adds execution count and cell tags
- **`full`** — Adds cell execution outputs
- **`token-budget`** — Drops lowest-priority cells to fit a `max_tokens` budget (drop order: bare code → code with outputs → markdown)
- Intelligent output summarization: DataFrame shape/columns detection, image size metadata, traceback compression
- Configurable `max_line_length` and `summarize_outputs`

#### Token Counting
- `tiktoken`-based counting (GPT-4 `cl100k_base`) when `[token]` extra is installed
- Heuristic fallback (`len(text) / 4`) — instant but approximate (±20%)
- `tokenize_notebook(doc, mode)` → `NotebookTokenReport` with per-cell breakdown
- `count_tokens(text)` for single-string counting
- CLI: `notebookllm tokens <file> [--breakdown]`

#### Rich CLI (was: basic argparse)
- `notebookllm convert` — single/batch conversion with `-o`, `--outdir`, `-f`, `-m` options
- `notebookllm inspect` — structure table with cell types and previews (rich tables)
- `notebookllm search` — case-insensitive cell search with `-t` type filter (rich highlighting)
- `notebookllm get` — extract single cell by index (syntax-highlighted)
- `notebookllm tokens` — token counting with `--breakdown` option
- `notebookllm server` — start MCP server with `--transport` (stdio/sse)
- Batch conversion: `notebookllm convert *.ipynb --outdir ./out`
- Cross-format batch: `notebookllm convert *.ipynb --outdir ./out -f markdown`

#### MCP Server (was: 5 basic tools)
- 18 unique MCP tools (26 with backward-compatible aliases):
  - Session management: `load`, `create`, `list_sessions`, `close_session`, `save`
  - Cell operations: `list_cells`, `get_cell`, `add_cell`, `edit_cell`, `delete_cell`, `move_cell`
  - Content: `to_text` (supports `max_tokens` budget), `search_cells`, `convert`
  - Execution: `execute`, `execute_all`, `list_kernels`
  - Analysis: `count_tokens`, `fingerprint`, `diff`
- Resources: `notebook://{session_id}`, `notebook://{session_id}/cells`, `notebook://{session_id}/cells/{index}`
- Prompts: `summarize_notebook`, `review_code`, `explain_notebook`
- SQLite-persisted sessions with automatic cleanup (max 100 sessions)
- KernelPool for thread-safe execution via Jupyter kernels
- `SessionManager` with XDG-compliant data directory

#### Validation & Utilities
- `validate_notebook(doc)` → `ValidationReport` with errors/warnings
- `validate_cell_types`, `validate_no_orphan_outputs`, `validate_no_empty_cells`
- `validate_filepath`, `validate_output_format`, `validate_cell_index`, `validate_cell_type`
- `atomic_write()` — atomic file writing via temp file + rename

#### Documentation
- Sphinx docs with `sphinx-rtd-theme` (auto-built in CI)
- Comprehensive README with CLI reference, Python API docs, and MCP configuration examples
- `SKILL.md` for AI agent integration

#### Infrastructure
- GitHub Actions CI/CD: lint (ruff), type check (mypy), test (pytest with 80% coverage), docs build, PyPI publish
- Benchmark tests (informational) and token efficiency benchmarks
- Editable install extras: `[cli]`, `[mcp]`, `[token]`, `[all]`, `[dev]`
- Python 3.11+ support

### Changed

#### Architecture (from old `notebookllm` v2.0)
- **Monolithic `Notebook` class → modular package**: The old `Notebook` class in a single `notebookllm.py` file wrapped `nbformat.NotebookNode` directly. Now `NotebookDocument` and `Cell` are format-agnostic dataclasses with loaders/dumpers for each format.
- **CLI overhaul**: Old CLI had two commands (`to_text`, `to_ipynb`). New CLI has 6 commands (`convert`, `inspect`, `search`, `get`, `tokens`, `server`) with rich formatting.
- **API surface**: Old `Notebook` class methods (`add_code_cell`, `add_markdown_cell`, `execute_cell`, `save`, etc.) replaced by `NotebookDocument` methods (`add_cell`, `edit_cell`, `delete_cell`, `move_cell`, `search`, `to_text`, `to_file`, etc.)
- **MCP architecture**: Old server used global mutable state (`loaded_notebook`, `loaded_notebook_path`). New server uses session-based architecture with SQLite persistence, KernelPool, and resource/prompt support.
- **Dependencies**: `mcp[cli]` moved from required to optional (`[mcp]` extra). `tiktoken` added as optional (`[token]` extra). `click`, `rich` added as optional (`[cli]` extra).
- **Python version**: Raised minimum from 3.10 to 3.11.

#### Architecture (from old `notebookllm-mcp` v0.4.0)
- **Integrated, not separate**: The old `notebookllm-mcp` package was a thin wrapper with 5 tools. The new MCP server has 18+ tools, resources, prompts, sessions, and kernel management — all in the main package.
- **Session-based**: Old server used a single global notebook. New server supports unlimited concurrent sessions with SQLite persistence.
- **Tool names**: Old tools (`load_notebook`, `notebook_to_plain_text`, etc.) preserved as aliases for backward compatibility.

### Removed

- **Separate `notebookllm-mcp` package**: No longer needed — use `notebookllm[mcp]` instead.
- **Old CLI commands**: `to_text`, `to_ipynb` — replaced by `notebookllm convert`.
- **Global mutable state in MCP server**: Replaced by session-based architecture.
- **`mcp[cli]` as required dependency**: Now optional (`[mcp]` extra).

---

### Previous Versions (Legacy)

These versions existed in the separate `notebookllm` and `notebookllm-mcp` packages before unification.

#### [2.0] — 2025-05 (notebookllm, standalone)
- Initial `Notebook` class with `.ipynb` load/save/execute
- `to_plain_text()` and `from_plain_text()` conversion
- Basic MCP server with `mcp_server.py`
- CLI with `to_text` and `to_ipynb` commands

#### [1.1.0] — 2025-05 (notebookllm, standalone)
- Initial PyPI release

#### [2.0.11] — 2025-09 (notebookllm-mcp, standalone)
- MCP server using FastMCP v2
- 5 tools: load, convert to/from plain text, add cells, save

#### [0.4.0] — 2025-09 (notebookllm-mcp, standalone)
- Initial PyPI release of separate MCP package

[2.0.0]: https://github.com/yasirrazaa/notebookllm/releases/tag/v2.0.0
[2.0]: https://github.com/yasirrazaa/notebookllm/releases/tag/v2.0
[1.1.0]: https://pypi.org/project/notebookllm/1.1.0/
[2.0.11]: https://pypi.org/project/notebookllm-mcp/2.0.11/
[0.4.0]: https://pypi.org/project/notebookllm-mcp/0.4.0/
