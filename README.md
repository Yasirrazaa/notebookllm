# notebookllm

[![PyPI](https://img.shields.io/pypi/v/notebookllm?label=pypi%20package)](https://pypi.org/project/notebookllm)
![PyPI - Downloads](https://img.shields.io/pypi/dm/notebookllm)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/notebookllm?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/notebookllm)

Convert, inspect, and optimize Jupyter notebooks for LLMs.

`notebookllm` converts notebooks to a clean, LLM-optimized plain text format, reducing token usage by up to 80%. It reads and writes 8 formats — `.ipynb`, percent scripts, Quarto, Markdown, Marimo, R Markdown, Deepnote, and flat scripts — through a single unified API. Use it from the CLI, Python library, or MCP server.

## Quick Start

```bash
pip install notebookllm[cli]

# Convert to LLM-optimized text
notebookllm convert notebook.ipynb

# Convert between formats
notebookllm convert notebook.ipynb -o output.py -f percent

# Count tokens
notebookllm tokens notebook.ipynb --breakdown

# Inspect structure
notebookllm inspect notebook.ipynb
```

```python
from notebookllm import load_file

doc = load_file("notebook.ipynb")
print(doc.to_text())                            # minimal LLM text
print(doc.to_text(mode="token-budget", max_tokens=2000))  # budget mode
```

## Why?

Raw `.ipynb` files waste LLM context. The JSON structure, metadata, execution counts, and base64-encoded image outputs burn tokens without adding value. `notebookllm` strips all that noise and produces clean text that LLMs can reason over effectively. It also writes notebooks back, enabling LLM-driven editing workflows.

## Features

- **8 formats**: Load and save `.ipynb`, percent (`# %%`), Quarto (`.qmd`), Markdown (`.md`), Marimo (`.py`), R Markdown (`.Rmd`), Deepnote (`.deepnote`), and flat scripts.
- **4 output modes**: `minimal` (source only), `standard` (+ metadata), `full` (+ outputs), `token-budget` (drops cells to fit a token limit).
- **Token counting**: Per-notebook and per-cell token measurement via tiktoken (GPT-4) or built-in fallback. Budget mode drops lowest-priority cells automatically.
- **Batch conversion**: Convert multiple files at once with `--outdir` for auto-named output.
- **Cell operations**: Add, edit, delete, move, and search cells programmatically.
- **Cell execution**: Run code cells via Jupyter kernels.
- **Streaming**: Handle notebooks larger than 10 MB via ijson streaming.
- **MCP server**: Expose all operations as MCP tools, resources, and prompts for LLM clients.

## Installation

```bash
pip install notebookllm          # core: format conversion, streaming, execution
pip install notebookllm[cli]     # + CLI (click, rich)
pip install notebookllm[mcp]     # + MCP server
pip install notebookllm[token]   # + accurate token counting (tiktoken)
pip install notebookllm[all]     # everything
```

The base install includes all core features: format conversion, streaming, cell execution, and the Python API. Extras add the CLI, MCP server, and tiktoken-based token counting.

Without `[token]`, token counting uses a `len(text)/4` heuristic — instant but approximate (±20%). With `[token]`, it uses GPT-4's `cl100k_base` encoding for exact counts.

## CLI

```bash
notebookllm convert <file>              # to LLM text (stdout)
notebookllm convert <file> -o out.py    # to file
notebookllm convert <file> -f percent   # explicit format
notebookllm convert <file> -m full      # include outputs
notebookllm convert a.ipynb b.qmd       # batch to stdout
notebookllm convert *.ipynb --outdir ./out  # batch to directory
notebookllm convert *.ipynb --outdir ./out -f markdown  # batch + format

notebookllm inspect <file>              # structure table
notebookllm search <file> <query>       # search cells
notebookllm search <file> <query> -t code  # filter by type
notebookllm get <file> <index>          # extract cell

notebookllm tokens <file>               # token count
notebookllm tokens <file> --breakdown   # per-cell table
notebookllm tokens <file> -m full       # count with outputs

notebookllm server                      # MCP server (stdio)
notebookllm server --transport sse      # MCP server (SSE)
```

## Python API

### Loading and Saving

```python
from notebookllm import NotebookDocument, load_file, dump_file, loads_text

# Load (auto-detects format from extension)
doc = load_file("notebook.ipynb")
doc = load_file("analysis.qmd")

# Load from string
doc = loads_text("# %% [code]\nprint('hi')\n", source_format="percent")

# Class method
doc = NotebookDocument.from_file("notebook.ipynb")

# Save
doc.to_file("output.ipynb")
doc.to_file("output.py", fmt="percent")
dump_file(doc, "output.md", fmt="markdown")
```

### Converting to LLM Text

```python
from notebookllm import OutputMode

text = doc.to_text()                                  # minimal (default)
text = doc.to_text(mode=OutputMode.STANDARD)          # + execution counts, tags
text = doc.to_text(mode=OutputMode.FULL)              # + cell outputs
text = doc.to_text(mode="token-budget", max_tokens=5000)  # budget mode
```

### Token Counting

```python
from notebookllm import tokenize_notebook, count_tokens

# Notebook-level
report = tokenize_notebook(doc, mode="minimal")
print(report.token_summary)  # "Total: 420 tokens across 8 cells"
for ct in report.cell_tokens:
    print(f"  [{ct.index}] {ct.cell_type}: {ct.tokens} tokens — {ct.preview}")

# Single string
n = count_tokens("hello world")  # 2 tokens (tiktoken) or 3 (fallback)

# Convenience method
report = doc.token_breakdown(mode="minimal")
```

### Cell Operations

```python
from notebookllm import Cell, CellType

# Add
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
# Search (returns list of (index, cell) tuples)
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

## MCP Server

The MCP server exposes notebook operations for LLM clients (Claude Desktop, VS Code, Zed, etc.).

### Setup

```bash
notebookllm server
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "notebookllm": {
      "command": "notebookllm-server"
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
        "command": "notebookllm-server"
      }
    }
  }
}
```

### Tools (18 unique, 26 with aliases)

| Tool | Description | Destructive |
|------|-------------|:---:|
| `load` / `load_notebook` | Load a notebook into a session | No |
| `create` / `create_notebook` | Create an empty notebook session | No |
| `list_sessions` | List all active sessions | No |
| `close_session` | Close session and clean up its kernel | No |
| `save` / `save_notebook` | Save session to file | Yes |
| `to_text` | Convert to LLM text (supports `max_tokens` for budget mode) | No |
| `list_cells` | List cells with index, type, preview | No |
| `get_cell` | Get a cell by index | No |
| `add_cell` | Add a new cell | No |
| `edit_cell` | Edit an existing cell | Yes |
| `delete_cell` | Delete a cell | Yes |
| `move_cell` | Move a cell | No |
| `search_cells` | Search cells by content | No |
| `count_tokens` | Count tokens in session | No |
| `convert` / `convert_format` | Convert to another format | No |
| `execute` / `execute_cell` | Execute a code cell | Yes |
| `execute_all` / `execute_all_cells` | Execute all code cells | Yes |
| `list_kernels` | List available Jupyter kernels | No |
| `fingerprint` | Session summary (cells, imports, functions) | No |
| `diff` | Compare two sessions | No |

### Resources

| URI | Description |
|-----|-------------|
| `notebook://{session_id}` | Full notebook as LLM text |
| `notebook://{session_id}/cells` | Cell listing |
| `notebook://{session_id}/cells/{index}` | Specific cell |

### Prompts

| Prompt | Description |
|--------|-------------|
| `summarize_notebook(session_id)` | Summarize notebook contents |
| `review_code(session_id)` | Review code quality |
| `explain_notebook(session_id)` | Explain step by step |

## Development

```bash
git clone https://github.com/yasirrazaa/notebookllm.git
cd notebookllm
uv sync && uv pip install -e ".[dev]"

uv run pytest                    # run tests
uv run pytest --cov=notebookllm  # with coverage
uv run ruff check .              # lint
uv run mypy notebookllm          # type check
```

## License

MIT
