---
name: notebookllm
description: Convert, inspect, and optimize Jupyter notebooks for LLM consumption. Supports 8 formats (ipynb, percent, marimo, quarto, markdown, rmarkdown, deepnote, script). Exposes a full MCP server with tools, resources, and prompts for programmatic notebook operations.
---

# notebookllm

CLI tool and Python library for converting and optimizing Jupyter notebooks for LLM consumption. Supports 8 notebook formats, session-based editing, token counting with budget mode, and an MCP server.

## Triggers

Use when the user asks to:
- convert a notebook to or from any supported format (including batch convert)
- optimize a notebook for LLM input (minimal/standard/full/token-budget output modes)
- count tokens in a notebook or control output size with a token budget
- inspect notebook structure (cells, types, imports, functions)
- search notebook cells by content (optionally by cell type)
- get, add, edit, delete, or move cells by index
- analyze a notebook (count tokens, compute fingerprint/diff)
- execute code cells via a Jupyter kernel
- work with notebook sessions programmatically via MCP

## CLI Commands

### `notebookllm convert`

Convert notebook files to LLM-optimized text or between formats.

```bash
# Single file to stdout (minimal mode)
notebookllm convert notebook.ipynb

# Single file to file with explicit format
notebookllm convert notebook.ipynb -o notebook.py -f percent

# Full output mode (includes cell outputs)
notebookllm convert notebook.ipynb -m full

# Batch convert: multiple files to stdout
notebookllm convert a.ipynb b.qmd c.py

# Batch convert: multiple files to output directory
notebookllm convert a.ipynb b.qmd --outdir ./out

# Batch convert with specific format
notebookllm convert a.ipynb b.qmd --outdir ./out -f markdown
```

### `notebookllm inspect`

Inspect notebook structure — cell count, format, language, and a preview of each cell.

```bash
notebookllm inspect notebook.ipynb
```

### `notebookllm search`

Search cells by content. Optionally filter by cell type.

```bash
notebookllm search notebook.ipynb pandas
notebookllm search notebook.py "import" -t code
```

### `notebookllm get`

Get a specific cell by index (0-based).

```bash
notebookllm get notebook.ipynb 5
```

### `notebookllm tokens`

Estimate token usage for a notebook. Uses tiktoken (cl100k_base) when available, falls back to len/4 heuristic.

```bash
# Total token count (minimal mode)
notebookllm tokens notebook.ipynb

# Full mode with all outputs
notebookllm tokens notebook.ipynb -m full

# Per-cell breakdown table
notebookllm tokens notebook.ipynb --breakdown
```

### `notebookllm server`

Start the MCP server for AI agent integration.

```bash
notebookllm server              # stdio transport (default)
notebookllm server --transport sse  # SSE transport
```

## Supported Formats

| Extension | Format | Load | Dump |
|-----------|--------|------|------|
| `.ipynb` | Jupyter Notebook | ✅ | ✅ |
| `.py` (percent) | Python with `# %%` markers | ✅ | ✅ |
| `.py` (marimo) | Marimo notebooks (`@app.cell`) | ✅ | ✅ |
| `.qmd` | Quarto documents | ✅ | ✅ |
| `.md` | Markdown with code blocks | ✅ | ✅ |
| `.rmd` | R Markdown | ✅ | ✅ |
| `.deepnote` / `.snapshot.deepnote` | Deepnote YAML project | ✅ | ✅ |

## Output Modes

Used with `notebookllm convert` for LLM-optimized text:

- **minimal** (default) — Cell markers + source only. Cleanest for LLM input.
- **standard** — Cell markers + source + metadata (type, execution count, tags).
- **full** — Cell markers + source + metadata + execution outputs.
- **token-budget** — Drops cells to stay within a max_tokens budget. Prioritizes markdown, then code with outputs, then bare code.

## Token Counting

The token feature measures notebook token consumption for LLM context planning.

**Three entry points:**

- **CLI**: `notebookllm tokens <file>` — prints "Total: N tokens across M cells". Add `--breakdown` for a per-cell table.
- **MCP**: `count_tokens(session_id, mode)` — returns the summary string.
- **Library**: `doc.token_breakdown(mode)` — returns a `NotebookTokenReport` with `total_tokens`, `cell_tokens` list, and `token_summary`.

**Token budget mode** (`max_tokens=N`): When converting with `to_text(mode="token-budget", max_tokens=5000)`, the optimizer drops lowest-priority cells to stay within the budget. Drop priority: code without outputs (drop first) → code with outputs → markdown (keep longest).

**Accuracy**: With `[token]` extra (tiktoken), uses GPT-4's cl100k_base encoding. Without it, uses `len(text)/4` heuristic.

## MCP Server

The MCP server (`notebookllm server`) exposes tools, resources, and prompts for programmatic notebook operations.

### Tools (18 unique, 26 total with aliases)

| Tool | Description | Destructive |
|------|-------------|:---:|
| `load` / `load_notebook` | Load a notebook file into session | No |
| `create` / `create_notebook` | Create an empty notebook session | No |
| `list_sessions` | List all active sessions | No |
| `close_session` | Close a session and clean up its kernel | No |
| `save` / `save_notebook` | Save session to file | Yes |
| `to_text` | Convert session to LLM text (supports `max_tokens` for budget mode) | No |
| `list_cells` | List cells with index, type, preview | No |
| `get_cell` | Get a specific cell by index | No |
| `add_cell` | Add a new cell at position | No |
| `edit_cell` | Edit an existing cell | Yes |
| `delete_cell` | Delete a cell by index | Yes |
| `move_cell` | Move a cell to another position | No |
| `search_cells` | Search cells by content | No |
| `count_tokens` | Count tokens in the session | No |
| `convert` / `convert_format` | Convert session to another format | No |
| `execute` / `execute_cell` | Execute a single code cell | Yes |
| `execute_all` / `execute_all_cells` | Execute all code cells | Yes |
| `list_kernels` | List available Jupyter kernels | No |
| `fingerprint` | Summary/fingerprint of a session | No |
| `diff` | Compare two sessions text | No |

### Resources

| URI | Description |
|-----|-------------|
| `notebook://{session_id}` | Full notebook as minimal-mode LLM text |
| `notebook://{session_id}/cells` | Cell listing with index, type, preview |
| `notebook://{session_id}/cells/{index}` | Specific cell source |

### Prompts

| Prompt | Description |
|--------|-------------|
| `summarize_notebook(session_id)` | Summarize a notebook session's contents and purpose |
| `review_code(session_id)` | Review code quality in a notebook session |
| `explain_notebook(session_id)` | Explain a notebook step by step |

## Python API

```python
from notebookllm import NotebookDocument
from notebookllm.models import Cell, CellType, OutputMode

# Load a notebook (auto-detects format)
doc = NotebookDocument.from_file("notebook.ipynb")

# Convert to LLM-optimized text
text = doc.to_text(mode=OutputMode.MINIMAL)

# Token-budget mode (keeps cells within budget)
text = doc.to_text(mode="token-budget", max_tokens=2000)

# Token counting
report = doc.token_breakdown(mode="minimal")
print(f"{report.total_tokens} tokens across {len(report.cell_tokens)} cells")

# Edit cells
cell = doc.get_cell(0)
doc.edit_cell(0, source="new code")
doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# New Section"))

# Save to a different format
doc.to_file("output.py", fmt="percent")
```

## Installation

```bash
# Core (nbformat + jupyter_client + ijson + pyyaml)
pip install notebookllm

# With CLI (rich, click)
pip install notebookllm[cli]

# With MCP server
pip install notebookllm[mcp]

# With accurate token counting (tiktoken)
pip install notebookllm[token]

# All extras
pip install notebookllm[all]
```
