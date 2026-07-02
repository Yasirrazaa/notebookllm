---
name: notebookllm
description: Convert, inspect, and optimize Jupyter notebooks for LLM consumption. CLI tool and Python library supporting 8 formats with token counting and budget mode.
---

# notebookllm

CLI tool and Python library for converting and optimizing Jupyter notebooks for LLMs. Supports 8 formats, token counting with budget mode, and batch conversion.

## Triggers

Use when the user asks to:
- convert a notebook between formats (ipynb, percent, quarto, markdown, rmarkdown, marimo, deepnote, script)
- batch convert multiple notebooks at once
- optimize a notebook for LLM input (minimal/standard/full output modes)
- count tokens in a notebook or limit output to a token budget
- inspect notebook structure (cell count, types, previews)
- search cells by content or type
- get, add, edit, delete, or move cells
- execute code cells via Jupyter kernel

## CLI Commands

### `notebookllm convert`

Convert between formats or to LLM-optimized text. Supports single files and batch mode.

```bash
# To LLM-optimized text (stdout)
notebookllm convert notebook.ipynb

# To a specific format
notebookllm convert notebook.ipynb -o output.py -f percent

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

Start the MCP server for AI agent integration.

```bash
notebookllm server                  # stdio (default)
notebookllm server --transport sse  # SSE
```

## Supported Formats

| Extension | Format | Load | Dump |
|-----------|--------|------|------|
| `.ipynb` | Jupyter Notebook | Yes | Yes |
| `.py` (percent) | Python with `# %%` markers | Yes | Yes |
| `.py` (marimo) | Marimo notebooks (`@app.cell`) | Yes | Yes |
| `.qmd` | Quarto documents | Yes | Yes |
| `.md` | Markdown with code blocks | Yes | Yes |
| `.rmd` | R Markdown | Yes | Yes |
| `.deepnote` | Deepnote YAML project | Yes | Yes |

## Output Modes

Controls how much detail appears in the LLM-optimized text output from `convert`:

- **minimal** (default) — `# %% [type]` markers + source code only. Cleanest for LLM input.
- **standard** — Adds execution count and metadata per cell.
- **full** — Adds cell execution outputs (stdout, results, errors).
- **token-budget** — Drops lowest-priority cells to stay within a `max_tokens` budget. Drop order: bare code (first) → code with outputs → markdown (last, kept longest).

## Token Counting

Measures notebook token consumption for LLM context planning.

**CLI**: `notebookllm tokens <file>` prints total token count. `--breakdown` shows per-cell table with index, type, tokens, and preview.

**Library**: `doc.token_breakdown(mode)` returns a `NotebookTokenReport` with `total_tokens`, `cell_tokens` list, and `token_summary` string.

**Budget mode**: `doc.to_text(mode="token-budget", max_tokens=5000)` drops cells to fit within the token limit.

**Accuracy**: Uses tiktoken (GPT-4 cl100k_base encoding) when `[token]` extra is installed. Otherwise falls back to `len(text)/4` heuristic — fast but approximate.

## Python API

```python
from notebookllm import NotebookDocument, load_file, dump_file, loads_text
from notebookllm.models import Cell, CellType, OutputMode

# ── Load ──────────────────────────────────────────
doc = NotebookDocument.from_file("notebook.ipynb")     # auto-detect format
doc = load_file("notebook.py")                          # same thing
doc = loads_text("# %% [code]\nprint('hi')\n")         # from string
doc = NotebookDocument.from_text(text, source_format="quarto")

# ── Inspect ───────────────────────────────────────
print(f"{len(doc.cells)} cells, format={doc.source_format}, lang={doc.language}")
for i, cell in enumerate(doc.cells):
    print(f"  [{i}] {cell.cell_type.value:10s} {cell.source[:60]}")

# ── Convert to LLM text ──────────────────────────
text = doc.to_text()                                        # minimal (default)
text = doc.to_text(mode=OutputMode.STANDARD)                # + execution counts
text = doc.to_text(mode=OutputMode.FULL)                    # + outputs
text = doc.to_text(mode="token-budget", max_tokens=5000)    # budget mode

# ── Token counting ────────────────────────────────
report = doc.token_breakdown(mode="minimal")
print(report.token_summary)  # "Total: 420 tokens across 8 cells"
for ct in report.cell_tokens:
    print(f"  [{ct.index}] {ct.cell_type}: {ct.tokens} tokens — {ct.preview}")

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
pip install notebookllm            # core (format conversion, streaming, execution)
pip install notebookllm[cli]       # + CLI (click, rich)
pip install notebookllm[token]     # + accurate token counting (tiktoken)
pip install notebookllm[all]       # everything
```
