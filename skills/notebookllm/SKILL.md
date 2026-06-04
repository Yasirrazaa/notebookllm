# notebookllm Skill

A CLI tool and library for converting and optimizing Jupyter notebooks for LLMs. Supports multiple notebook formats: `.ipynb`, `.py` (percent/marimo), `.qmd` (quarto), and `.md` (markdown).

## Triggers

Use when the user asks to:
- "convert notebook" between formats
- "optimize notebook for LLM" consumption
- "notebook to text" for LLM input
- "inspect notebook" structure
- "search notebook cells" for content
- "get cell" by index from a notebook

## Available Commands

### `notebookllm convert`

Convert a notebook file to LLM-optimized text or to another format.

**Examples:**
```bash
# Convert to LLM-optimized text (stdout, minimal mode)
notebookllm convert notebook.ipynb

# Convert to percent .py format
notebookllm convert notebook.ipynb -o notebook.py -f percent

# Full output mode (includes cell outputs)
notebookllm convert notebook.ipynb -m full

# Convert quarto to markdown
notebookllm convert analysis.qmd -o output.md -f markdown
```

### `notebookllm inspect`

Inspect notebook structure — shows cell count, format, language, and a preview of each cell.

**Example:**
```bash
notebookllm inspect notebook.ipynb
```

### `notebookllm search`

Search cells by content. Optionally filter by cell type.

**Examples:**
```bash
# Search all cells for "pandas"
notebookllm search notebook.ipynb pandas

# Search only code cells
notebookllm search notebook.py "import" -t code
```

### `notebookllm get`

Get a specific cell by index (0-based).

**Example:**
```bash
notebookllm get notebook.ipynb 5
```

### `notebookllm server`

Start the MCP server for AI agent integration.

**Example:**
```bash
# Using stdio transport (default)
notebookllm server

# Using SSE transport
notebookllm server --transport sse
```

## Supported Formats

| Extension | Format | Load | Dump |
|-----------|--------|------|------|
| `.ipynb` | Jupyter Notebook | ✅ | ✅ |
| `.py` (percent) | Python with `# %%` markers | ✅ | ✅ |
| `.py` (marimo) | Marimo notebooks with `@app.cell` | ✅ | ❌ |
| `.qmd` | Quarto documents | ✅ | ✅ |
| `.md` | Markdown with code blocks | ✅ | ✅ |

## Output Modes

For LLM consumption via `notebookllm convert`:

- `minimal` (default) — Cell markers + source only. Cleanest for LLM input.
- `standard` — Cell markers + source + cell metadata (type, execution count, tags).
- `full` — Cell markers + source + metadata + cell execution outputs.

## MCP Server

The MCP server exposes 11 tools for programmatic notebook operations:
`load_notebook`, `save_notebook`, `to_text`, `list_cells`, `get_cell`, `add_cell`, `edit_cell`, `delete_cell`, `move_cell`, `search_cells`, `execute_cell`.

## Python API

```python
from notebookllm import NotebookDocument
from notebookllm.models import Cell, CellType, OutputMode

# Load a notebook (auto-detects format)
doc = NotebookDocument.from_file("notebook.ipynb")

# Convert to LLM-optimized text
text = doc.to_text(mode=OutputMode.MINIMAL)

# Edit cells
cell = doc.get_cell(0)
doc.edit_cell(0, source="new code")
doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# New Section"))

# Save to a different format
doc.to_file("output.py", fmt="percent")
```

## Installation

```bash
# Core (nbformat + pyyaml)
pip install notebookllm

# With CLI
pip install notebookllm[cli]

# With MCP server
pip install notebookllm[mcp]

# All extras
pip install notebookllm[all]
```
