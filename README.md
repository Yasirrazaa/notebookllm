# notebookllm

[![PyPI](https://img.shields.io/pypi/v/notebookllm?label=pypi%20package)](https://pypi.org/project/notebookllm)
![PyPI - Downloads](https://img.shields.io/pypi/dm/notebookllm)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/notebookllm?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/notebookllm)

Convert, inspect, and optimize Jupyter notebooks for Large Language Models.

`notebookllm` provides a universal notebook representation that works across multiple formats — `.ipynb`, percent scripts (`.py`), Quarto (`.qmd`), Markdown (`.md`), and Marimo (`.py`). It includes a CLI, a Python API, and an MCP server for LLM-native notebook manipulation.

## Why?

LLMs struggle with raw `.ipynb` files — the verbose JSON structure, metadata, and base64-encoded outputs waste tokens and context windows. `notebookllm` converts notebooks to a clean, LLM-optimized plain text format, reducing token usage by up to 80%. It also converts plain text _back_ to notebooks, enabling LLM-driven notebook editing workflows.

## Features

- **Multi-format support**: Load and save `.ipynb`, percent scripts (`# %%`), Quarto, Markdown, and Marimo formats.
- **LLM-optimized output**: Three verbosity modes — `minimal` (source only), `standard` (+ execution counts, tags), `full` (+ cell outputs).
- **CLI tools**: Convert between formats, inspect notebook structure, search cell contents, extract individual cells.
- **MCP server**: Expose notebook operations as tools for LLMs (session-based, with cell CRUD, search, and execution).
- **Streaming**: Load notebooks larger than 10 MB via `ijson` streaming (optional `[stream]` extra).
- **Cell execution**: Execute code cells via Jupyter kernels (optional `[execute]` extra).

## Installation

```bash
pip install notebookllm
```

With extras:

```bash
pip install notebookllm[cli]      # CLI tools (click, rich)
pip install notebookllm[mcp]      # MCP server
pip install notebookllm[execute]  # Cell execution via jupyter_client
pip install notebookllm[stream]   # Streaming for large notebooks (ijson)
pip install notebookllm[all]      # Everything above
```

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

# Inspect notebook structure (cells, types, previews)
notebookllm inspect notebook.ipynb

# Search cells by content
notebookllm search notebook.ipynb "import pandas"
notebookllm search notebook.ipynb "def train" --type code

# Extract a specific cell
notebookllm get notebook.ipynb 3

# Start the MCP server
notebookllm server

# MCP server with SSE transport
notebookllm server --transport sse
```

Output formats: `ipynb`, `percent` (`# %%` markers), `quarto` (`.qmd`), `markdown`, `marimo`.

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

Supported formats: `ipynb`, `percent`, `quarto`, `markdown`, `marimo`.

## MCP Server

`notebookllm` includes a built-in MCP (Model Context Protocol) server that exposes notebook operations as tools for LLM clients (Claude Desktop, VS Code, Zed, etc.).

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

### Available Tools

| Tool | Purpose |
|------|---------|
| `load_notebook` | Load a notebook into a session (returns session ID) |
| `save_notebook` | Save the session notebook to file |
| `to_text` | Convert session notebook to LLM-optimized text (modes: minimal, standard, full) |
| `list_cells` | List all cells with index, type, and preview |
| `get_cell` | Get a specific cell by index |
| `add_cell` | Add a new code, markdown, or raw cell |
| `edit_cell` | Edit an existing cell's source and/or type |
| `delete_cell` | Delete a cell by index |
| `move_cell` | Move a cell from one position to another |
| `search_cells` | Search cells by content (case-insensitive) |
| `execute_cell` | Execute a code cell via Jupyter kernel (requires `[execute]`) |

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
