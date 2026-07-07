---
name: notebookllm
description: Convert, inspect, and optimize Jupyter notebooks for AI Agents. CLI tool, Python library, and MCP server supporting 8+ formats with token counting, budget mode, and batch conversion.
---

# notebookllm — Notebook Toolkit for AI Agents

CLI tool, Python library, and MCP server for converting, inspecting, and optimizing Jupyter notebooks for AI Agent consumption. Supports **8+ notebook formats**, **token counting with budget mode**, **batch conversion**, **cell editing/execution**, and **MCP server integration** for autonomous agents.

> **⚡ Unified Package**
> The standalone `notebookllm-mcp` server is now fully integrated into the core `notebookllm` package. Install `notebookllm[mcp]` for everything.

## Triggers

Use notebookllm when the user asks to:
- convert a notebook between formats (ipynb, percent, quarto, markdown, rmarkdown, marimo, deepnote, script)
- batch convert multiple notebooks at once
- optimize a notebook for AI Agent input (minimal/standard/full output modes)
- count tokens in a notebook or limit output to a token budget
- inspect notebook structure (cell count, types, previews)
- search cells by content or type
- get, add, edit, delete, or move cells
- execute code cells via Jupyter kernel
- compare two notebook versions (diff)
- get a notebook fingerprint (imports, functions, cell counts)
- start an MCP server for agent integration

## CLI Commands

### `notebookllm convert`

Convert between formats or to Agent-optimized text. Supports single files and batch mode.

```bash
# To Agent-optimized text (stdout)
notebookllm convert notebook.ipynb

# To a specific format
notebookllm convert notebook.ipynb -o output.py -f percent
notebookllm convert notebook.ipynb -o output.qmd -f quarto

# Output mode: minimal (default), standard, full
notebookllm convert notebook.ipynb -m full

# Batch: multiple files to stdout
notebookllm convert a.ipynb b.qmd c.py

# Batch: multiple files to directory (auto-named {stem}_converted.{ext})
notebookllm convert a.ipynb b.qmd --outdir ./out

# Batch: specific format
notebookllm convert a.ipynb b.qmd --outdir ./out -f markdown
```

### `notebookllm inspect`

Show notebook structure — format, language, cell count, and a table of cells with previews.

```bash
notebookllm inspect notebook.ipynb
```

### `notebookllm search`

Search cells by content. Use `-t` to filter by cell type (code, markdown, raw).

```bash
notebookllm search notebook.ipynb "import pandas"
notebookllm search notebook.ipynb "def train" -t code
```

### `notebookllm get`

Extract a single cell by index (0-based).

```bash
notebookllm get notebook.ipynb 3
```

### `notebookllm tokens`

Estimate token usage. Add `--breakdown` for a per-cell table.

```bash
notebookllm tokens notebook.ipynb
notebookllm tokens notebook.ipynb -m full --breakdown
```

### `notebookllm server`

Start the MCP server for AI Agent integration.

```bash
notebookllm server                  # stdio (default — for Claude Desktop, VS Code, Zed)
notebookllm server --transport sse  # SSE (for HTTP-based connections)
```

## Supported Formats

| Extension | Format | Load | Dump |
|-----------|--------|:----:|:----:|
| `.ipynb` | Jupyter Notebook | ✅ | ✅ |
| `.py` (percent) | Python with `# %%` markers | ✅ | ✅ |
| `.py` (marimo) | Marimo notebooks (`@app.cell`) | ✅ | ✅ |
| `.qmd` | Quarto documents | ✅ | ✅ |
| `.md` | Markdown with code blocks | ✅ | ✅ |
| `.Rmd` | R Markdown | ✅ | ✅ |
| `.deepnote` | Deepnote YAML project | ✅ | ✅ |
| `.py` | Flat script (one-way export) | ❌ | ✅ |

## Output Modes

Controls how much detail appears in the Agent-optimized text output:

- **minimal** (default) — `# %% [type]` markers + source code only. Cleanest for Agent input.
- **standard** — Adds execution count and metadata per cell.
- **full** — Adds cell execution outputs (stdout, results, errors).
- **token-budget** — Drops lowest-priority cells to stay within a `max_tokens` budget. Drop order: bare code (first) → code with outputs → markdown (last, kept longest).

## Token Counting

Measures notebook token consumption for AI Agent context planning.

**CLI**: `notebookllm tokens <file>` prints total token count. `--breakdown` shows per-cell table with index, type, tokens, and preview.

**Library**: `doc.token_breakdown(mode)` returns a `NotebookTokenReport` with `total_tokens`, `cell_tokens` list, and `token_summary` string.

**Budget mode**: `doc.to_text(mode="token-budget", max_tokens=5000)` drops cells to fit within the token limit.

**Accuracy**: Uses tiktoken (GPT-4 cl100k_base encoding) when `[token]` extra is installed. Otherwise falls back to `len(text)/4` heuristic — fast but approximate (±20%).

## Python API

```python
from notebookllm import NotebookDocument, load_file, dump_file, loads_text
from notebookllm.models import Cell, CellType, OutputMode

# ── Load ──────────────────────────────────────────
doc = NotebookDocument.from_file("notebook.ipynb")     # auto-detect format
doc = load_file("notebook.py")                          # same thing
doc = loads_text("# %% [code]\nprint('hi')\n")         # from string (auto-detected)
doc = NotebookDocument.from_text(text, source_format="quarto")

# ── Inspect ───────────────────────────────────────
print(f"{len(doc.cells)} cells, format={doc.source_format}, lang={doc.language}")
for i, cell in enumerate(doc.cells):
    print(f"  [{i}] {cell.cell_type.value:10s} {cell.source[:60]}")

# ── Convert to Agent text ──────────────────────────
text = doc.to_text()                                        # minimal (default)
text = doc.to_text(mode=OutputMode.STANDARD)                # + execution counts
text = doc.to_text(mode=OutputMode.FULL)                    # + outputs
text = doc.to_text(mode="token-budget", max_tokens=5000)    # budget mode

# ── Token counting ────────────────────────────────
report = doc.token_breakdown(mode="minimal")
print(report.token_summary)  # "Total: 420 tokens across 8 cells"
for ct in report.cell_tokens:
    print(f"  [{ct.cell_index}] {ct.cell_type}: {ct.tokens} tokens — {ct.preview}")

# ── Cell operations ───────────────────────────────
doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Results"), position=0)
doc.edit_cell(0, source="x = 2")
doc.delete_cell(2)
doc.move_cell(from_index=0, to_index=2)
cell = doc.get_cell(0)

# ── Search ────────────────────────────────────────
results = doc.search("import pandas", cell_type=CellType.CODE)
for idx, cell in results:
    print(f"  [{idx}] {cell.source[:60]}")

code_cells = doc.filter_cells(cell_type=CellType.CODE)
matches = doc.filter_cells(query="train")

# ── Save ──────────────────────────────────────────
doc.to_file("output.ipynb")
doc.to_file("output.py", fmt="percent")
doc.to_file("output.qmd", fmt="quarto")
dump_file(doc, "output.md", fmt="markdown")
```

## Installation

```bash
pip install notebookllm            # Core: format conversion, streaming, execution
pip install notebookllm[cli]       # + CLI (click, rich)
pip install notebookllm[mcp]       # + MCP server
pip install notebookllm[token]     # + Accurate token counting (tiktoken)
pip install notebookllm[all]       # Everything
```

## MCP Server Integration

When the user wants to set up the MCP server, configure their client:

**Claude Desktop** (`claude_desktop_config.json`):
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

Using ``uvx``:
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

Using ``pip``:
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

The MCP server exposes 20 tools (load, create, save, to_text, list_cells, get_cell, add_cell, edit_cell, delete_cell, move_cell, search_cells, count_tokens, convert, execute, execute_all, list_kernels, close_session, fingerprint, diff, list_sessions) plus 3 resource templates and 3 prompts.

## Output Summarization

When using token-budget mode or `summarize_outputs=True`:

- **DataFrames**: `# [DataFrame(1000, 5)] Columns: col1, col2, col3 (values hidden)`
- **Images**: `# [Plot: image/png, ~42KB]`
- **Tracebacks**: `# [error] ValueError: invalid literal for int()`
- **Long text**: Truncated at 500 chars with remainder note
