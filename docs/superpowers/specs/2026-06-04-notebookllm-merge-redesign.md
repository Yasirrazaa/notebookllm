# notebookllm Merge & Redesign — Design Spec

**Date:** 2026-06-04
**Status:** Approved
**Scope:** Merge `notebookllm` (core, v2.0) + `notebookllm-mcp` (v0.4.0) into a single production-ready package

---

## 1. Problem Statement

Two separate packages (`notebookllm` on PyPI with 500+ downloads, `notebookllm-mcp` with 6000+ downloads) share near-identical MCP server code. The core library:

- Only supports `.ipynb` — no `.py`, `.qmd`, `.md`, or marimo
- Has extremely naive parsing (`textwrap.dedent` destroys indentation, no marker-in-code protection, lossy round-trips)
- MCP server exposes only 6 tools (no delete/edit/search), uses global mutable state
- `mcp[cli]` is a required dependency (should be optional)
- Has zero tests, stale build artifacts, empty placeholder files
- Competes with `@deepnote/convert` (npm) which already does bidirectional conversion across formats

**Goal:** Merge into one package with multi-format support, robust parsing, CLI + MCP server + agent skill, comprehensive tests, and maximum performance.

---

## 2. Architecture Approach: Loader Pattern (Approach A)

A dispatch-based architecture where each format has a dedicated parser (loader/dumper) that converts to/from a **unified internal model** (`NotebookDocument` dataclass). The core library owns format detection, parsing, and conversion logic.

```
Format → Loader → NotebookDocument → Dumper → Format
                  (universal model)
```

**Why not jupytext?** Jupytext is designed for notebook format conversion, not LLM optimization. The value-add is the LLM-optimized output modes — custom code regardless. Keeping dependencies minimal (nbformat + Python stdlib) is critical for speed. `@deepnote/convert` is the direct competitor; differentiation must come from LLM-specific features, not format coverage parity.

---

## 3. Package Structure

```
notebookllm/
├── pyproject.toml                    # Single package, extras: [cli], [mcp], [execute]
├── notebookllm/
│   ├── __init__.py                   # Public API: NotebookDocument, load(), convert()
│   ├── models.py                     # NotebookDocument, Cell, CellType, OutputMode
│   ├── loaders/
│   │   ├── __init__.py               # Auto-detect format from extension/content
│   │   ├── base.py                   # Abstract BaseLoader, BaseDumper
│   │   ├── ipynb.py                  # .ipynb loader (nbformat, streaming JSON)
│   │   ├── percent.py                # .py percent format (# %% markers)
│   │   ├── marimo.py                 # .py marimo format (@app.cell AST parsing)
│   │   ├── quarto.py                 # .qmd format
│   │   └── markdown.py               # .md / Jupytext markdown format
│   ├── converters/
│   │   ├── __init__.py
│   │   └── llm_optimizer.py          # Configurable output modes (minimal/standard/full)
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py               # Rich CLI with subcommands
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py                 # FastMCP server, session-scoped state
│   │   └── session.py                # SessionManager for multi-user support
│   └── utils/
│       ├── __init__.py
│       ├── detect.py                 # Format detection (extension + content sniffing)
│       └── validation.py             # Input/output validation
├── skills/
│   └── notebookllm/
│       └── SKILL.md                  # Agent skill for CLI usage
├── tests/
│   ├── fixtures/                     # Sample notebooks in all formats
│   ├── test_loaders.py               # Per-format parser tests
│   ├── test_converters.py            # LLM optimizer tests
│   ├── test_cli.py                   # CLI integration tests
│   ├── test_mcp.py                   # MCP server tool tests
│   └── test_roundtrip.py             # Format A → B → A fidelity tests
└── docs/
```

### Package Extras

- `notebookllm[cli]` — adds `click` for CLI
- `notebookllm[mcp]` — adds `mcp[cli]` for MCP server
- `notebookllm[execute]` — adds `jupyter_client` for kernel execution
- `notebookllm[all]` — all extras

Core dependencies (minimal): `nbformat`, `pydantic` (already transitive via nbformat)

---

## 4. Core Data Model

```python
# models.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class CellType(Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"

class OutputMode(Enum):
    MINIMAL = "minimal"      # Code/markdown text only, structure markers
    STANDARD = "standard"    # Text + cell metadata (type, execution count)
    FULL = "full"            # Text + metadata + outputs + execution state

@dataclass
class CellOutput:
    """Represents output from a cell execution."""
    output_type: str         # "stream", "execute_result", "display_data", "error"
    content: str | dict      # Text for streams, data dict for display
    name: str | None = None  # "stdout" or "stderr" for stream type

@dataclass
class Cell:
    """Universal cell representation."""
    cell_type: CellType
    source: str
    execution_count: int | None = None
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    cell_id: str | None = None

@dataclass
class NotebookDocument:
    """Universal notebook representation — format-agnostic."""
    cells: list[Cell] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    kernel_name: str | None = None
    language: str = "python"
    source_format: str | None = None  # Original format: "ipynb", "percent", "marimo", etc.

    # File I/O
    @classmethod
    def from_file(cls, filepath: str) -> "NotebookDocument": ...
    def to_file(self, filepath: str, fmt: str | None = None) -> None: ...

    # Text conversion
    def to_text(self, mode: OutputMode = OutputMode.MINIMAL) -> str: ...
    @classmethod
    def from_text(cls, text: str, source_format: str | None = None) -> "NotebookDocument":
        """Parse text content into NotebookDocument.
        
        If source_format is None, attempts auto-detection by content sniffing:
        - Lines starting with '# %% [' → percent format
        - Lines starting with '@app.cell' → marimo format
        - Lines starting with '```{python}' → quarto format
        - Lines starting with '```python' → markdown format
        - Fallback: treat as single code cell (percent format)
        """
        ...

    # Cell operations
    def filter_cells(self, cell_type: CellType | None = None, query: str | None = None) -> list[Cell]: ...
    def get_cell(self, index: int) -> Cell: ...
    def add_cell(self, cell: Cell, position: int | None = None) -> None: ...
    def edit_cell(self, index: int, source: str, cell_type: CellType | None = None) -> None: ...
    def delete_cell(self, index: int) -> None: ...
    def move_cell(self, from_index: int, to_index: int) -> None: ...
    def search(self, query: str, cell_type: CellType | None = None) -> list[tuple[int, Cell]]:
        """Search cells by content (case-insensitive substring match).
        
        Returns list of (index, cell) tuples for cells containing query.
        If cell_type is provided, only search cells of that type.
        """
        ...
```

### Key Design Decisions

- `NotebookDocument` is the single source of truth — all operations go through it
- `Cell` wraps cell type + source + optional outputs/metadata
- `OutputMode` enum controls LLM output verbosity
- `.from_file()` auto-detects format via extension + content sniffing
- `.to_file()` auto-detects output format from extension, or explicit `fmt` param
- `.search()` enables agents to find relevant cells before editing
- `CellOutput` captures execution results for `FULL` mode

---

## 5. Format Loaders

### Base Classes

```python
# loaders/base.py
from abc import ABC, abstractmethod

class BaseLoader(ABC):
    @abstractmethod
    def load(self, source: str | Path) -> NotebookDocument:
        """Load from file path."""
        ...

    @abstractmethod
    def loads(self, content: str) -> NotebookDocument:
        """Load from string content."""
        ...

class BaseDumper(ABC):
    @abstractmethod
    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        """Dump to string or file."""
        ...
```

### Format Detection (`utils/detect.py`)

```python
def detect_format(filepath: Path, content: str | None = None) -> str:
    """Detect notebook format from extension and optionally content sniffing."""
    ext = filepath.suffix.lower()
    if ext == ".ipynb":
        return "ipynb"
    elif ext == ".qmd":
        return "quarto"
    elif ext in (".md", ".rmd"):
        return "markdown"
    elif ext == ".py":
        if content is None:
            content = filepath.read_text(encoding="utf-8")
        if "import marimo" in content or "@app.cell" in content:
            return "marimo"
        if "# %%" in content:
            return "percent"
        return "percent"  # Default for .py
    raise ValueError(f"Cannot detect format for {filepath}")
```

### Format-Specific Parsers

| Format | Detection | Parser Strategy | Edge Cases |
|--------|-----------|-----------------|------------|
| `.ipynb` | Extension `.ipynb` | nbformat + streaming JSON for large files | Malformed JSON, v3 notebooks |
| `.py` percent | Extension `.py` + `# %%` markers | Regex state machine for `# %% [code/markdown]` | Markers inside code comments |
| `.py` marimo | Extension `.py` + `@app.cell` / `import marimo` | Python `ast` module to extract cell bodies | Nested decorators, `@app.function` |
| `.qmd` | Extension `.qmd` or content has `{python}` chunks | Regex: `` ```{python}...``` `` + YAML frontmatter | YAML parsing errors |
| `.md` | Extension `.md` + ```` ```python ```` blocks | Regex: ```` ```python...```` `` blocks | Markdown with code-like content |

### Streaming for Large `.ipynb` Files

For notebooks >10MB, use `ijson` to stream-parse JSON instead of loading the entire file:

```python
# ipynb.py
def _load_streaming(self, filepath: Path) -> NotebookDocument:
    """Stream-parse large ipynb files to avoid memory spike."""
    import ijson
    cells = []
    with open(filepath, "rb") as f:
        for cell in ijson.items(f, "cells.item"):
            cells.append(Cell(
                cell_type=CellType(cell["cell_type"]),
                source="".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"],
                execution_count=cell.get("execution_count"),
                outputs=self._parse_outputs(cell.get("outputs", [])),
            ))
    return NotebookDocument(cells=cells, ...)
```

### Marimo Parser (AST-based)

```python
# marimo.py
import ast

def _parse_marimo(self, content: str) -> NotebookDocument:
    """Parse marimo notebooks by extracting cell bodies from @app.cell decorators."""
    tree = ast.parse(content)
    cells = []
    for node in ast.iter_child_nodes(tree):
        if (isinstance(node, ast.FunctionDef) and
            any(self._is_app_decorator(d) for d in node.decorator_list)):
            body_lines = ast.get_source_segment(content, node)
            cell_source = self._extract_cell_body(body_lines)
            cells.append(Cell(cell_type=CellType.CODE, source=cell_source))
    return NotebookDocument(cells=cells, source_format="marimo")
```

---

## 6. LLM Optimizer (Output Modes)

```python
# converters/llm_optimizer.py
class LLMOptimizer:
    """Converts NotebookDocument to LLM-optimized text."""
    
    def __init__(self, mode: OutputMode = OutputMode.MINIMAL,
                 include_cell_markers: bool = True,
                 max_line_length: int | None = None,
                 strip_outputs: bool = True):
        self.mode = mode
        self.include_cell_markers = include_cell_markers
        self.max_line_length = max_line_length
        self.strip_outputs = strip_outputs

    def optimize(self, doc: NotebookDocument) -> str:
        """Produce optimized text based on mode."""
        ...
```

### Output Examples

**MINIMAL** (default) — cleanest for LLM consumption:
```
# %% [code]
import pandas as pd
df = pd.read_csv("data.csv")
df.head()

# %% [markdown]
## Analysis Results
```

**STANDARD** — includes metadata hints:
```
# %% [code]
# exec_count: 3
# tags: analysis, important
import pandas as pd
```

**FULL** — includes outputs:
```
# %% [code]
# execution_count: 3
import pandas as pd
df = pd.read_csv("data.csv")
# --- outputs ---
# [output] (5 rows × 3 columns)
# [error] FileNotFoundError: No such file
```

---

## 7. CLI Design

Uses `click` (already in MCP's dependency tree). Subcommands: `convert`, `inspect`, `search`, `get`, `server`.

```bash
# Convert .ipynb to LLM-optimized text (stdout)
notebookllm convert notebook.ipynb

# Convert to percent .py format
notebookllm convert notebook.ipynb -o notebook.py -f percent

# Inspect notebook structure
notebookllm inspect notebook.ipynb

# Search cells
notebookllm search notebook.ipynb "pandas" -t code

# Get specific cell
notebookllm get notebook.ipynb 5

# Start MCP server
notebookllm server start [--transport stdio|sse]
```

---

## 8. MCP Server

Session-scoped state. Each MCP connection gets its own session via `SessionManager`. 11 tools (up from 6):

| Tool | Description |
|------|-------------|
| `load_notebook` | Load a notebook file into session |
| `save_notebook` | Save current notebook to file |
| `to_text` | Convert to LLM-optimized text |
| `list_cells` | List all cells with index/type/preview |
| `get_cell` | Get specific cell by index |
| `add_cell` | Add a new cell |
| `edit_cell` | Edit existing cell source/type |
| `delete_cell` | Delete cell by index |
| `move_cell` | Move cell between positions |
| `search_cells` | Search cells by content |
| `execute_cell` | Execute code cell via Jupyter kernel |

### Kernel Lifecycle (execute_cell)

The `execute_cell` tool requires the `[execute]` extra (`jupyter_client`). Kernel management:

1. On first `execute_cell` call in a session, start a Jupyter kernel matching the notebook's `kernel_name` (default: `python3`)
2. Kernel stays alive for the session's lifetime
3. `execute_cell` sends source to kernel, captures stdout/stderr/display_data/error
4. Results are stored as `CellOutput` objects on the cell
5. Kernel is shut down when the session is deleted or the MCP connection closes
6. Timeout parameter controls max wait per execution (default: 60s)

### Session Manager

```python
class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
    
    def store(self, session_id: str, doc: NotebookDocument, filepath: str | None = None): ...
    def get(self, session_id: str) -> NotebookDocument: ...
    def delete(self, session_id: str): ...
    def list_sessions(self) -> list[str]: ...
```

---

## 9. Agent Skill

CLI wrapper skill at `skills/notebookllm/SKILL.md`. Teaches agents to use `notebookllm` CLI commands for notebook operations. Triggers on: `convert notebook`, `optimize notebook for LLM`, `notebook to text`, `inspect notebook`, `search notebook cells`.

---

## 10. Testing Strategy

```
tests/
├── fixtures/
│   ├── sample.ipynb              # Standard Jupyter notebook
│   ├── sample_percent.py         # Percent format (.py)
│   ├── sample_marimo.py          # Marimo format
│   ├── sample_quarto.qmd         # Quarto markdown
│   ├── sample_markdown.md        # Jupytext markdown
│   ├── large_notebook.ipynb      # 1000+ cells (streaming test)
│   └── edge_cases/               # Empty notebooks, malformed files
├── test_models.py                # NotebookDocument, Cell, CellType, OutputMode
├── test_loaders/
│   ├── test_ipynb.py             # .ipynb parsing
│   ├── test_percent.py           # Percent format parsing
│   ├── test_marimo.py            # Marimo parsing
│   ├── test_quarto.py            # .qmd parsing
│   ├── test_markdown.py          # .md parsing
│   └── test_detect.py            # Format detection
├── test_converters/
│   └── test_llm_optimizer.py     # Minimal/standard/full output modes
├── test_cli.py                   # CLI integration (click.testing.CliRunner)
├── test_mcp.py                   # MCP server tool tests
└── test_roundtrip.py             # Format A → B → A fidelity tests
```

**Key test scenarios:**
- Round-trip fidelity: load → dump → load preserves cell content
- Large file streaming: 1000+ cell notebooks parse without OOM
- Edge cases: empty cells, markers in code, malformed JSON, v3 notebooks
- CLI integration: all subcommands with various flag combinations
- MCP tools: each tool with session management

---

## 11. Performance Targets

- Streaming JSON via `ijson` for `.ipynb` files >10MB
- Lazy loading — only parse cells when accessed
- Format detection from extension (no content sniffing unless needed)
- Minimal dependencies: `nbformat` + Python stdlib for core; `mcp[cli]` only if MCP extra installed

---

## 12. Migration Plan

1. **New package structure** — scaffold the new directory layout
2. **Core data model** — `NotebookDocument`, `Cell`, `CellType`, `OutputMode`
3. **Format loaders** — one at a time, starting with `.ipynb` (most critical)
4. **LLM optimizer** — configurable output modes
5. **CLI** — `convert`, `inspect`, `search`, `get`, `server`
6. **MCP server** — session-scoped, 11 tools
7. **Agent skill** — CLI wrapper SKILL.md
8. **Test suite** — fixtures, per-format tests, round-trip tests
9. **Cleanup** — remove stale `build/`, `main.py`, root `__init__.py`, `mcp_llm.md`
10. **Publish** — merge into single `notebookllm` package on PyPI
