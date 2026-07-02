# notebookllm

[![PyPI](https://img.shields.io/pypi/v/notebookllm?label=pypi%20package)](https://pypi.org/project/notebookllm)
![PyPI - Downloads](https://img.shields.io/pypi/dm/notebookllm)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/notebookllm?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/notebookllm)

Convert, inspect, and optimize Jupyter notebooks for Large Language Models.

`notebookllm` provides a universal notebook representation that works across multiple formats — `.ipynb`, percent scripts (`.py`), Quarto (`.qmd`), Markdown (`.md`), Marimo (`.py`), Deepnote (`.deepnote`), and R Markdown (`.Rmd`). It includes a CLI, a Python API, and an MCP server for LLM-native notebook manipulation.

## Why?

LLMs struggle with raw `.ipynb` files — the verbose JSON structure, metadata, and base64-encoded outputs waste tokens and context windows. `notebookllm` converts notebooks to a clean, LLM-optimized plain text format, reducing token usage by up to 80%. It also converts plain text _back_ to notebooks, enabling LLM-driven notebook editing workflows.

## Features

- **Multi-format support**: Load and save `.ipynb`, percent scripts (`# %%`), Quarto, Markdown, Marimo, Deepnote (`.deepnote`), and R Markdown formats.
- **LLM-optimized output**: Four verbosity modes — `minimal` (source only), `standard` (+ execution counts, tags), `full` (+ cell outputs), `token-budget` (drops cells to stay within a token limit).
- **Token counting**: Measure token usage per notebook and per cell using tiktoken (GPT-4 encoding) or built-in fallback. Supports per-cell breakdown and budget-based cell dropping.
- **CLI tools**: Convert between formats (including batch), inspect notebook structure, search cell contents, extract individual cells, estimate token usage.
- **MCP server**: Expose notebook operations as tools, resources, and prompts for LLMs (session-based, with cell CRUD, search, and execution).
- **Streaming**: Load notebooks larger than 10 MB via `ijson` streaming.
- **Cell execution**: Execute code cells via Jupyter kernels.

## Installation

```bash
pip install notebookllm
```

The base install includes all core features: format conversion, streaming for large notebooks, and cell execution via Jupyter kernels.

Optional extras for CLI, MCP server, and advanced token counting:

```bash
pip install notebookllm[cli]      # CLI tools (click, rich)
pip install notebookllm[mcp]      # MCP server (mcp[cli])
pip install notebookllm[token]    # Accurate token counting via tiktoken
pip install notebookllm[all]      # Everything above
```

> **Note**: Without the `[token]` extra, token counting uses a built-in `len(text)/4` heuristic which is fast but less accurate. With `[token]`, it uses tiktoken's `cl100k_base` encoding (GPT-4 family).

## CLI Usage

```bash
# Convert a notebook to LLM-optimized text (stdout)
notebookllm convert notebook.ipynb

# Convert between formats
notebookllm convert notebook.ipynb -o script.py
notebookllm convert script.py -o notebook.ipynb
notebookllm convert notebook.qmd -o notebook.md

# Specify output format explicitly
notebookllm convert notebook.ipynb -f markdown -o notebook.md

# LLM output modes: minimal (default), standard, full
notebookllm convert notebook.ipynb -m standard
notebookllm convert notebook.ipynb -m full

# Batch convert multiple files (print all to stdout)
notebookllm convert notebook.ipynb script.py notebook.qmd

# Batch convert with output directory (auto-named: {stem}_converted.{ext})
notebookllm convert notebook.ipynb script.py --outdir ./converted

# Batch convert to a specific format
notebookllm convert notebook.ipynb script.py --outdir ./converted -f markdown

# Inspect notebook structure (cells, types, previews)
notebookllm inspect notebook.ipynb

# Search cells by content
notebookllm search notebook.ipynb "import pandas"
notebookllm search notebook.ipynb "def train" -t code

# Extract a specific cell
notebookllm get notebook.ipynb 3

# Estimate token usage
notebookllm tokens notebook.ipynb
notebookllm tokens notebook.ipynb -m full --breakdown

# Start the MCP server
notebookllm server

# MCP server with SSE transport
notebookllm server --transport sse
```

Output formats: `ipynb`, `percent` (`# %%` markers), `quarto` (`.qmd`), `markdown`, `marimo`, `rmarkdown` (`.Rmd`), `deepnote` (`.deepnote`), `script` (flat `.py` export).

## Python API

```python
from notebookllm import NotebookDocument, OutputMode, CellType, Cell

# Load from file (auto-detects format)
doc = NotebookDocument.from_file("notebook.ipynb")

# Load from text content
doc = NotebookDocument.from_text("# %% [code]\nprint('hello')\n")

# Inspect
print(f"{len(doc.cells)} cells, format: {doc.source_format}")

for i, cell in enumerate(doc.cells):
    print(f"[{i}] {cell.cell_type.value}: {cell.source[:60]}...")

# Convert to LLM-optimized text
text = doc.to_text(mode=OutputMode.MINIMAL)
text = doc.to_text(mode=OutputMode.STANDARD)  # + execution counts
text = doc.to_text(mode=OutputMode.FULL)      # + cell outputs

# Token-budget mode: drop cells to stay within a token limit
text = doc.to_text(mode="token-budget", max_tokens=5000)

# Token counting
from notebookllm import tokenize_notebook, count_tokens
report = tokenize_notebook(doc, mode="minimal")
print(f"Total: {report.total_tokens} tokens across {len(report.cell_tokens)} cells")
for ct in report.cell_tokens:
    print(f"  [{ct.index}] {ct.cell_type}: {ct.tokens} tokens")

# Manipulate cells
cell = Cell(cell_type=CellType.CODE, source="print('hello')")
doc.add_cell(cell)

doc.edit_cell(0, source="print('updated')", cell_type=CellType.CODE)
doc.delete_cell(1)
doc.move_cell(from_index=2, to_index=0)

# Search
results = doc.search("def train", cell_type=CellType.CODE)
for idx, cell in results:
    print(f"[{idx}] {cell.source}")

# Filter
code_cells = doc.filter_cells(cell_type=CellType.CODE)
train_cells = doc.filter_cells(query="train")

# Save
doc.to_file("output.ipynb")
doc.to_file("output.py", fmt="percent")
doc.to_file("output.qmd", fmt="quarto")

# Direct loader access (auto-detect)
from notebookllm import load_file, dump_file, loads_text

doc = load_file("notebook.ipynb")
dump_file(doc, "output.py")
doc = loads_text("# %% [code]\nx = 1\n")
```

Supported formats: `ipynb`, `percent`, `quarto`, `markdown`, `marimo`, `rmarkdown`, `deepnote`, `script`.

## MCP Server

`notebookllm` includes a built-in MCP (Model Context Protocol) server that exposes notebook operations as tools, resources, and prompts for LLM clients (Claude Desktop, VS Code, Zed, etc.).

### Starting the Server

```bash
# Via CLI
notebookllm server

# Via module
python -m notebookllm.mcp.server

# Via uvx (no installation needed)
uvx notebookllm-server
```

### Configuration

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

**Zed** (`settings.json`):

```json
{
  "mcp_servers": {
    "notebookllm": {
      "command": "uvx",
      "args": ["notebookllm-server"]
    }
  }
}
```

### Tools (18 unique, 26 total with aliases)

| Tool | Description | Destructive |
|------|-------------|:---:|
| `load` / `load_notebook` | Load a notebook file into a session | No |
| `create` / `create_notebook` | Create a new empty notebook session | No |
| `list_sessions` | List all active sessions | No |
| `close_session` | Close a session and clean up its kernel | No |
| `save` / `save_notebook` | Save session to file | Yes |
| `to_text` | Convert session to LLM-optimized text (supports `max_tokens` for budget mode) | No |
| `list_cells` | List cells with index, type, and preview | No |
| `get_cell` | Get a specific cell by index | No |
| `add_cell` | Add a new cell at a position | No |
| `edit_cell` | Edit an existing cell | Yes |
| `delete_cell` | Delete a cell by index | Yes |
| `move_cell` | Move a cell to another position | No |
| `search_cells` | Search cells by content (case-insensitive) | No |
| `count_tokens` | Count tokens in the session notebook | No |
| `convert` / `convert_format` | Convert session to another format | No |
| `execute` / `execute_cell` | Execute a single code cell via Jupyter kernel | Yes |
| `execute_all` / `execute_all_cells` | Execute all code cells sequentially | Yes |
| `list_kernels` | List available Jupyter kernels | No |
| `fingerprint` | Summary/fingerprint of a notebook session | No |
| `diff` | Compare two sessions text | No |

### Resources

| URI | Description |
|-----|-------------|
| `notebook://{session_id}` | Full notebook as minimal-mode LLM text |
| `notebook://{session_id}/cells` | Cell listing with index, type, and preview |
| `notebook://{session_id}/cells/{index}` | Specific cell source |

### Prompts

| Prompt | Description |
|--------|-------------|
| `summarize_notebook(session_id)` | Summarize a notebook session's contents and purpose |
| `review_code(session_id)` | Review code quality in a notebook session |
| `explain_notebook(session_id)` | Explain a notebook step by step |

## Development

```bash
git clone https://github.com/yasirrazaa/notebookllm.git
cd notebookllm

# Install with uv
uv sync
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=notebookllm

# Lint
uv run ruff check .

# Type check
uv run mypy notebookllm
```

## License

MIT
