# notebookllm

[![PyPI](https://img.shields.io/pypi/v/notebookllm?label=pypi%20package)](https://pypi.org/project/notebookllm)
![PyPI - Downloads](https://img.shields.io/pypi/dm/notebookllm)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/notebookllm?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/notebookllm)

> **⚡ Unified Package — One Install, Everything You Need**
>
> The standalone `notebookllm-mcp` server has been fully integrated into the core `notebookllm` package. Both the Python library and MCP server now ship together — one `pip install`, zero headaches. The legacy `notebookllm-mcp` package is deprecated. Install `notebookllm[mcp]` to get everything.

**Convert, inspect, and optimize Jupyter notebooks for AI Agents (Claude Code, Cursor, GitHub Copilot, Claude Desktop, VS Code, Zed, and more).**

`notebookllm` is the Swiss Army knife for notebook manipulation. It converts notebooks to a clean, Agent-optimized plain-text format — reducing token usage by up to **80%** — and reads/writes **8+ formats** through a single unified API. Use it from the CLI, as a Python library, or as an MCP server for AI Agent integration.

---

## Key Features

- **8+ Notebook Formats** — Load and save `.ipynb`, percent (`# %%`), Quarto (`.qmd`), Markdown (`.md`), Marimo (`.py`), R Markdown (`.Rmd`), Deepnote (`.deepnote`), and flat scripts. One API to rule them all.
- **AI Agent–Optimized Output** — Strip JSON noise, metadata, and base64 blobs. Produce clean text that AI Agents can reason over effectively. Four verbosity modes: `minimal`, `standard`, `full`, and `token-budget`.
- **Smart Token Budget** — Automatically drop lowest-priority cells to fit within a token limit. Markdown (explanatory) → code with outputs → bare code (dropped first).
- **Token Counting** — Per-notebook and per-cell token measurement via tiktoken (GPT-4 `cl100k_base`) or built-in heuristic fallback.
- **Intelligent Output Summarization** — DataFrames get shape/column summaries, images get size metadata, tracebacks get compressed to the last line.
- **Batch Conversion** — Convert entire directories of notebooks in one command.
- **Cell Operations** — Add, edit, delete, move, search, and execute cells programmatically.
- **Streaming** — Handle notebooks larger than 10 MB via ijson streaming (cell-by-cell, no memory spike).
- **MCP Server** — Expose all operations as MCP tools, resources, and prompts for any MCP-compatible AI Agent client (Claude Desktop, VS Code, Zed, Cursor, Claude Code).
- **Validation & Atomic Writes** — Detect orphaned outputs, empty cells, and invalid types. Crash-safe file saves via temp-file + rename.

---

## Quick Start

```bash
pip install notebookllm[cli]

# Convert a notebook to Agent-optimized text
notebookllm convert notebook.ipynb

# Convert between formats
notebookllm convert notebook.ipynb -o output.py -f percent

# Count tokens
notebookllm tokens notebook.ipynb --breakdown

# Inspect notebook structure
notebookllm inspect notebook.ipynb
```

```python
from notebookllm import load_file

# Load any notebook format — auto-detected
doc = load_file("notebook.ipynb")

# Convert to AI Agent–optimized text
print(doc.to_text())                                      # minimal (default)
print(doc.to_text(mode="token-budget", max_tokens=2000))  # budget mode
```

---

## Why notebookllm?

Raw `.ipynb` files waste AI Agent context. The JSON structure, execution metadata, and base64-encoded image outputs burn tokens without adding value. `notebookllm` strips all that noise and produces clean, structured text that Agents can reason over effectively.

But it doesn't stop at one-way conversion. `notebookllm` is a **bidirectional notebook toolkit**: it reads, writes, edits, searches, executes, and converts notebooks across 8+ formats. Whether you're feeding a notebook into Claude Code, building a VS Code extension, or automating a data pipeline, `notebookllm` has you covered.

---

## Installation

> **Migrating from `notebookllm-mcp`?** The separate MCP package is now deprecated. Everything is built in. Just `pip install notebookllm[mcp]`.

```bash
pip install notebookllm            # Core: format conversion, streaming, execution
pip install notebookllm[cli]       # + CLI (click, rich tables, syntax highlighting)
pip install notebookllm[mcp]       # + MCP server for AI Agent integration
pip install notebookllm[token]     # + Accurate token counting via tiktoken
pip install notebookllm[all]       # Everything (CLI + MCP + token)
```

**Dependency breakdown:**

| Extra | What you get |
|-------|-------------|
| *(base)* | `nbformat`, `jupyter_client`, `ijson`, `pyyaml` — format conversion, streaming, cell execution |
| `[cli]` | `click`, `rich` — CLI with formatted output |
| `[mcp]` | `mcp[cli]` — MCP server for AI Agent clients |
| `[token]` | `tiktoken` — GPT-4 token counting (without it, uses `len(text)/4` heuristic, ±20%) |

---

## CLI Reference

### `notebookllm convert`

Convert notebook(s) between formats or to Agent-optimized text.

```bash
# Single file to Agent text (stdout)
notebookllm convert notebook.ipynb

# Single file to a specific format
notebookllm convert notebook.ipynb -o output.py -f percent
notebookllm convert notebook.ipynb -o output.qmd -f quarto

# Output verbosity
notebookllm convert notebook.ipynb              # minimal (default)
notebookllm convert notebook.ipynb -m standard  # + execution counts, tags
notebookllm convert notebook.ipynb -m full      # + cell outputs

# Batch: multiple files to stdout
notebookllm convert a.ipynb b.qmd c.py

# Batch: multiple files to directory (auto-named)
notebookllm convert *.ipynb --outdir ./out
notebookllm convert a.ipynb b.qmd --outdir ./out -f markdown
```

### `notebookllm inspect`

Show notebook structure — format, language, cell count, and a formatted table of cells with previews.

```bash
notebookllm inspect notebook.ipynb
```

### `notebookllm search`

Search cells by content (case-insensitive substring match). Filter by type with `-t`.

```bash
notebookllm search notebook.ipynb "import pandas"
notebookllm search notebook.ipynb "def train" -t code
```

### `notebookllm get`

Extract a single cell by 0-based index. Rich syntax highlighting included.

```bash
notebookllm get notebook.ipynb 3
```

### `notebookllm tokens`

Estimate token usage. Uses tiktoken when available, falls back to heuristic.

```bash
notebookllm tokens notebook.ipynb              # total tokens
notebookllm tokens notebook.ipynb --breakdown  # per-cell table
notebookllm tokens notebook.ipynb -m full      # count with outputs
```

### `notebookllm server`

Start the MCP server for AI Agent integration.

```bash
notebookllm server                    # stdio (default — Claude Desktop, VS Code, Zed)
notebookllm server --transport sse    # SSE (HTTP-based connections)
```

---

## Python API

### Loading and Saving

```python
from notebookllm import NotebookDocument, load_file, dump_file, loads_text

# Load — auto-detects format from extension
doc = load_file("notebook.ipynb")
doc = load_file("analysis.qmd")
doc = load_file("report.Rmd")

# Load from string with auto-detection
doc = loads_text("# %% [code]\nprint('hi')\n")  # auto-detected as "percent"

# Explicit format
doc = loads_text(text, source_format="quarto")

# Convenience class methods
doc = NotebookDocument.from_file("notebook.ipynb")
doc = NotebookDocument.from_text(text, source_format="quarto")

# Save — auto-detects format from extension
doc.to_file("output.ipynb")
doc.to_file("output.py", fmt="percent")

# Serialize/deserialize (CIR JSON)
json_str = doc.to_json()
restored = NotebookDocument.from_json(json_str)
```

### Converting to AI Agent Text

```python
from notebookllm import OutputMode

# Four output verbosity modes
text = doc.to_text()                                       # minimal (default)
text = doc.to_text(mode=OutputMode.STANDARD)               # + execution counts, tags
text = doc.to_text(mode=OutputMode.FULL)                   # + cell outputs
text = doc.to_text(mode="token-budget", max_tokens=5000)   # budget mode
```

**Output examples:**

```python
# MINIMAL — clean, token-efficient
# %% [code]
import pandas as pd
df = pd.read_csv("data.csv")

# STANDARD — includes metadata
# %% [code]
# exec_count: 3
# tags: preprocessing, cleaning
df = df.dropna()

# FULL — includes outputs
# %% [code]
print(df.head())
# --- outputs ---
# [stdout]    col1  col2
# 0     1     2
```

### Token Counting

```python
from notebookllm import tokenize_notebook, count_tokens

# Notebook-level token analysis
report = tokenize_notebook(doc, mode="minimal")
print(report.token_summary)  # "Total: 420 tokens across 8 cells (minimal mode)"
for ct in report.cell_tokens:
    print(f"  [{ct.cell_index}] {ct.cell_type}: {ct.tokens} tokens — {ct.preview}")

# Single string
n = count_tokens("hello world")  # 2 tokens (tiktoken) or 3 (fallback)

# Convenience method on the document
report = doc.token_breakdown(mode="minimal")
```

### Cell Operations

```python
from notebookllm import Cell, CellType

# Add cells
doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"), position=0)

# Edit
doc.edit_cell(0, source="x = 2")
doc.edit_cell(0, source="# New", cell_type=CellType.MARKDOWN)

# Delete and move
doc.delete_cell(2)
doc.move_cell(from_index=0, to_index=2)

# Get
cell = doc.get_cell(0)
print(cell.source, cell.cell_type, cell.execution_count)
```

### Search and Filter

```python
# Search with optional type filter
results = doc.search("import pandas", cell_type=CellType.CODE)
for idx, cell in results:
    print(f"[{idx}] {cell.source[:60]}")

# Filter
code_cells = doc.filter_cells(cell_type=CellType.CODE)
matches = doc.filter_cells(query="train")
```

### Inspection

```python
print(len(doc.cells))           # cell count
print(doc.source_format)        # "ipynb", "percent", "quarto", etc.
print(doc.language)             # "python", "r", etc.
print(doc.kernel_name)          # "python3", etc.
```

### Validation

```python
from notebookllm.utils.validation import validate_notebook

report = validate_notebook(doc)
print(report.summary)       # "Validation passed." or "Validation found 2 errors, 3 warnings."
print(report.format_text()) # human-readable error/warning listing
print(report.is_valid)      # True if no errors
```

---

## Supported Formats

| Extension | Format | Load | Dump |
|-----------|--------|:----:|:----:|
| `.ipynb` | Jupyter Notebook | ✅ | ✅ |
| `.py` | Percent script (`# %%` markers) | ✅ | ✅ |
| `.py` | Marimo (`@app.cell` decorators) | ✅ | ✅ |
| `.qmd` | Quarto document | ✅ | ✅ |
| `.md` | Markdown with fenced code blocks | ✅ | ✅ |
| `.Rmd` | R Markdown | ✅ | ✅ |
| `.deepnote` | Deepnote YAML project | ✅ | ✅ |
| `.py` | Flat script (one-way export) | ❌ | ✅ |

---

## MCP Server for AI Agent Integration

The MCP server exposes every notebookllm operation as MCP tools, resources, and prompts. This lets any MCP-compatible AI Agent client (Claude Desktop, VS Code, Zed, Cursor, Claude Code) manipulate notebooks on your behalf.

### Setup

Start the MCP server:

```bash
notebookllm server
```

### Configuration

Configure your MCP client using either ``uvx`` (recommended) or ``pip`` with ``python -m``.

#### Using uvx (zero-config, no manual install)

``uvx`` automatically fetches ``notebookllm`` from PyPI and runs the server in an isolated environment.

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "notebookllm": {
      "command": "uvx",
      "args": ["notebookllm-server"]
    }
  }
}
```

To pin a specific version or extras:
```json
{
  "mcpServers": {
    "notebookllm": {
      "command": "uvx",
      "args": ["--from", "notebookllm[all]", "notebookllm-server"]
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`):
```json
{
  "mcp": {
    "servers": {
      "notebookllm": {
        "command": "uvx",
        "args": ["notebookllm-server"]
      }
    }
  }
}
```

**Zed** (`~/.config/zed/mcp.json`):
```json
{
  "notebookllm": {
    "command": "uvx",
    "args": ["notebookllm-server"]
  }
}
```

#### Using pip (manual install)

Install the package first, then reference the installed server module:

```bash
pip install notebookllm[mcp]
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "notebookllm": {
      "command": "python",
      "args": ["-m", "notebookllm.mcp.server"]
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`):
```json
{
  "mcp": {
    "servers": {
      "notebookllm": {
        "command": "python",
        "args": ["-m", "notebookllm.mcp.server"]
      }
    }
  }
}
```

**Zed** (`~/.config/zed/mcp.json`):
```json
{
  "notebookllm": {
    "command": "python",
    "args": ["-m", "notebookllm.mcp.server"]
  }
}
```

### Tools (26 total — 20 unique + 6 aliases)

| Primary Name | Description | Destructive |
|-------------|-------------|:-----------:|
| `load` | Load a notebook file into a new session | No |
| `create` | Create an empty notebook session | No |
| `list_sessions` | List all active sessions | No |
| `close_session` | Close session and clean up its kernel | No |
| `save` | Save session to file | Yes |
| `to_text` | Convert to Agent-optimized text | No |
| `list_cells` | List cells with index, type, preview | No |
| `get_cell` | Get a cell by index | No |
| `add_cell` | Add a new cell | No |
| `edit_cell` | Edit an existing cell | Yes |
| `delete_cell` | Delete a cell | Yes |
| `move_cell` | Move a cell to a new position | No |
| `search_cells` | Search cells by content | No |
| `count_tokens` | Count tokens in a session | No |
| `convert` | Convert session to another format | No |
| `execute` | Execute a code cell via Jupyter kernel | Yes |
| `execute_all` | Execute all code cells sequentially | Yes |
| `list_kernels` | List available Jupyter kernels | No |
| `fingerprint` | Session summary (cells, imports, functions) | No |
| `diff` | Compare two sessions using unified diff | No |

**Aliases** (backward-compatible with old `notebookllm-mcp`): `load_notebook`, `create_notebook`, `save_notebook`, `convert_format`, `execute_cell`, `execute_all_cells`.

### Resources

| URI | Description |
|-----|-------------|
| `notebook://{session_id}` | Full notebook as Agent-optimized text |
| `notebook://{session_id}/cells` | Cell listing with index, type, preview |
| `notebook://{session_id}/cells/{index}` | Specific cell by index |

### Prompts

| Prompt | Description |
|--------|-------------|
| `summarize_notebook(session_id)` | Summarize notebook contents and purpose |
| `review_code(session_id)` | Review code quality in a notebook |
| `explain_notebook(session_id)` | Explain the notebook step by step |

### Session Management

The MCP server maintains up to **100 concurrent sessions**, persisted to a local SQLite database at `~/.local/share/notebookllm/sessions.db`. Sessions survive server restarts. Each session optionally has a Jupyter kernel for code execution. Sessions are auto-evicted (oldest first) when the limit is reached.

---

## Agent Skill

For autonomous AI Agents (Claude Code, Cursor, Claude Desktop, GitHub Copilot Workspaces), `notebookllm` includes a **native agent skill** at `skills/notebookllm/SKILL.md`.

This skill document teaches AI Agents exactly how to use `notebookllm` to manipulate and inspect notebooks on your behalf. To equip your agent:

1. Ensure the `skills/` directory is discoverable by your agent
2. Or instruct the agent to read `skills/notebookllm/SKILL.md` directly

The skill covers: CLI commands, Python API usage, output modes, token counting, format conversion, and MCP server integration.

---

## Output Modes

Controls how much detail appears in the Agent-optimized text output:

| Mode | What's Included | Best For |
|------|----------------|----------|
| `minimal` | `# %% [type]` markers + source code only | Agent input — cleanest, most token-efficient |
| `standard` | Adds execution count and metadata tags | Understanding notebook execution history |
| `full` | Adds all cell outputs (stdout, results, errors) | Complete notebook state analysis |
| `token-budget` | Drops lowest-priority cells to fit `max_tokens` | Strict context window limits |

**Token-budget drop priority** (highest-value kept longest):
1. Markdown cells (explanatory — never dropped if only one remains)
2. Code cells with outputs (executed, have results)
3. Code cells without outputs (scaffolding — dropped first)

---

## Output Summarization

When using `token-budget` mode or with `summarize_outputs=True`, long and rich outputs are automatically compressed:

- **DataFrames**: Shape and column names extracted from the ASCII repr — `# [DataFrame(1000, 5)] Columns: col1, col2, col3 (values hidden)`
- **Images**: MIME type and approximate size — `# [Plot: image/png, ~42KB]`
- **Tracebacks**: Last line only — `# [error] ValueError: invalid literal for int()`
- **Long text**: Truncated at 500 characters with a remainder note

---

## Cell Execution

Run code cells via Jupyter kernels through the MCP server's `execute` and `execute_all` tools. Execution is async and thread-pooled, keeping the server responsive. Kernels are started lazily per session and cleaned up when the session is closed.

```bash
# via MCP server tools:
#   execute(session_id="...", index=0)
#   execute_all(session_id="...")
#   list_kernels()
```

---

## Development

```bash
git clone https://github.com/yasirrazaa/notebookllm.git
cd notebookllm
uv sync && uv pip install -e ".[dev]"

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=notebookllm

# Run benchmarks
uv run pytest tests/benchmarks --benchmark-only

# Lint and type check
uv run ruff check .
uv run mypy notebookllm

# Build this documentation
uv run sphinx-build -b html -E docs docs/_build
```

---

## Architecture Overview

```
                 ┌──────────────┐
                 │  CLI (click) │
                 └──────┬───────┘
                        │
┌──────────┐    ┌───────┴────────┐    ┌──────────────┐
│  MCP     │◄──►│  Loaders/      │◄──►│  Notebook    │
│  Server  │    │  Dumpers       │    │  Document    │
│          │    │  (8 formats)   │    │  (CIR model) │
└──────────┘    └───────┬────────┘    └──────┬───────┘
                        │                    │
                 ┌───────┴────────┐    ┌──────┴────────┐
                 │  Format        │    │  LLM          │
                 │  Detection     │    │  Optimizer    │
                 └────────────────┘    └──────┬────────┘
                                              │
                                     ┌────────┴────────┐
                                     │  Token Counter  │
                                     │  (tiktoken)     │
                                     └─────────────────┘
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
