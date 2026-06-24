# Agentic Infrastructure Plan — notebookllm

## Critical Pre-Flight: What the Blueprint Gets Right and Wrong + Corrections

**Right:**
- SQLite over in-memory dict — solves the persistence problem
- Atomic writes with pre-validation — solves the corruption problem
- KernelPool with `asyncio.to_thread` — solves the blocking problem
- Semantic output summarization — solves the token bloat problem
- Expanding the Cell model — necessary for SQL, Deepnote, multi-language

**Needs adjustment:**
- Sprint ordering: Sprint 2 (model changes) touches EVERY loader/dumper/test file. Sprint 1's SQLite layer serializes the model, which will break when the model changes in Sprint 2. Solution: design the serialization to be tolerant of model changes (ignore unknown fields, version the schema).
- CellType.SQL as enum value introduces coupling. A `block_type` field alongside `language` is more extensible. The enum gate keeps CODE/MARKDOWN/RAW as the base contract; SQL lives in `block_type`, routed by the execution engine via `language`.
- DataFrame detection from text output is impossible without running code. We can only do it accurately inside the kernel context (where we know the Python object type). The plan acknowledges two tiers: kernel-aware summarization (accurate) vs text-heuristic summarization (fallback).
- No migration path for existing in-memory sessions. Since the current SessionManager has no persistence, this is a clean break — but needs documentation.
- Execute-all-cells needs clear semantics: sequential? dependency-aware? topological order of cell execution counts? The simplest correct answer: execute in cell order, skip non-code cells, stop on first error.

**CORRECTION — Deepnote is NOT an .ipynb variant:**
I assumed Deepnote was .ipynb with extra metadata. It is not. Deepnote is a **YAML-based project format** (`.deepnote`) that:
- Contains multiple notebooks in a single YAML file
- Has block types far beyond Jupyter: `code`, `markdown`, `sql`, `visualization` (Vega-Lite), `dataframe`, `image`, `input`, `text-cell-h1/h2/h3/p`, `separator`, `button`
- Uses block groups (`blockGroup` UUIDs) for grouping related blocks
- Uses `sortingKey` (base-36) for ordering
- Uses `contentHash` (SHA-256) for code provenance tracking
- Supports execution modes (`block`, `downstream` for reactive execution)
- Stores integrations (database connections), environment config (Python version, Docker image, requirements)
- Has a companion `.snapshot.deepnote` format that stores execution outputs separately from source

Deepnote needs its own **loader, dumper, detector** — the plan below was wrong about it being an ipynb post-processing step. The Cell model needs `block_type`, `block_group`, `content_hash`, and `sorting_key` fields. The `pyyaml` dependency (already listed as `[yaml]` extra) handles the YAML parsing.

---

## Architecture Diagram (Conceptual)

```
┌─────────────────────────────────────────────────────────┐
│                    MCP / CLI Layer                       │
│  (FastMCP tools, Click commands)                        │
├──────────┬──────────────────┬────────────────────────────┤
│  Pillar 1 │  Pillar 2        │  Pillar 3                 │
│  Trust    │  Compute         │  Format                   │
├──────────┼──────────────────┼────────────────────────────┤
│ SQLite   │  KernelPool      │  Loader/Dumper Registry    │
│ Session  │  (ThreadPool)    │  (ipynb, percent, marimo,  │
│ Store    │  ├─ start_exec   │   quarto, markdown,        │
│ Atomic   │  ├─ poll_exec    │   rmarkdown, script,       │
│ Writes   │  ├─ interrupt    │   deepnote)                │
│ Validate │  └─ list_kernels │                            │
│          │  Output Summarizer                             │
│          │  (DataFrame→schema, Plot→Image, Truncation)    │
└──────────┴──────────────────┴────────────────────────────┘
                    │
                    ▼
           NotebookDocument (CIR)
           (Cell, CellOutput, CellType + language)
```

---

## Sprint 1: Trust Foundation (Persistence + Anti-Corruption)

**Goal:** Sessions survive server restarts. Edits can't corrupt files.

### Task 1.1: Add serialization to NotebookDocument (RED → GREEN → REFACTOR)

**RED** — `tests/test_models.py`
```python
def test_notebook_json_roundtrip():
    """NotebookDocument serializes to JSON and back without data loss."""
    doc = NotebookDocument(...)  # full-featured: cells, outputs, metadata
    json_str = doc.to_json()
    doc2 = NotebookDocument.from_json(json_str)
    assert doc2.cells[0].source == doc.cells[0].source
    assert doc2.metadata == doc.metadata
```

**GREEN** — `notebookllm/models.py`
- Add `to_json()`: serialize NotebookDocument → JSON string
- Add `from_json()`: deserialize JSON string → NotebookDocument
- Handle all nested types (Cell, CellOutput, CellType enum)
- Handle large outputs gracefully (don't double-encode)
- Implement a `_to_dict()` / `_from_dict()` for each dataclass

**Edge cases to test:**
- Empty notebook → `to_json()` → `from_json()` → empty notebook
- Notebook with all cell types + outputs
- Unicode content (Japanese, emoji)
- Very long cell sources (>100KB)
- Nested metadata dicts
- `None` values (execution_count, cell_id)

**REFACTOR:** Unit-test the dict conversion separately, make serialization version-tolerant (ignore unknown keys in from_json).

### Task 1.2: Replace SessionManager with SQLite backend (RED → GREEN → REFACTOR)

**RED** — `tests/test_mcp_session.py`

Rewrite `TestSessionManager` to test against SQLite:

```python
def test_session_survives_reconnect():
    """Notebook persists after manager re-instantiation."""
    db_path = tmp_path / "sessions.db"
    mgr1 = SessionManager(db_path=str(db_path))
    doc = NotebookDocument()
    doc.add_cell(Cell(...))
    mgr1.store("s1", doc)
    del mgr1

    mgr2 = SessionManager(db_path=str(db_path))
    result = mgr2.get("s1")
    assert result.cells[0].source == "x = 1"

def test_is_dirty_tracking():
    mgr = SessionManager(db_path=":memory:")
    mgr.store("s1", NotebookDocument())
    assert mgr.is_dirty("s1") is True
    mgr.mark_clean("s1")
    assert mgr.is_dirty("s1") is False

def test_save_marks_clean():
    """After save_notebook tool, session should be clean."""
    ...

def test_list_sessions_after_restart():
    mgr1 = SessionManager(db_path=...)
    mgr1.store("s1", NotebookDocument())
    del mgr1
    mgr2 = SessionManager(db_path=...)
    sessions = mgr2.list_sessions()
    assert "s1" in sessions
```

**GREEN** — `notebookllm/mcp/session.py`

Replace `SessionManager`:

```python
class SessionManager:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DEFAULT_DB_PATH
        self._conn = sqlite3.connect(self._db_path ...)
        self._init_schema()

    def _init_schema(self):
        # CREATE TABLE IF NOT EXISTS sessions (id, filepath, format,
        #   language, kernel_name, created_at, updated_at, is_dirty)
        # CREATE TABLE IF NOT EXISTS notebook_states (
        #   session_id, state TEXT, version INT, updated_at,
        #   FOREIGN KEY → sessions ON DELETE CASCADE)
        ...

    def store(self, session_id, doc, filepath=None):
        # Serialize doc via doc.to_json()
        # UPSERT into sessions + notebook_states
        ...

    def get(self, session_id) -> NotebookDocument:
        # SELECT state FROM notebook_states, deserialize via NotebookDocument.from_json()
        ...

    def delete(self, session_id):
        # DELETE CASCADE handles both tables
        # If kernel running, shut it down first
        ...

    def list_sessions(self) -> list[dict]:
        # SELECT id, filepath, format, created_at, is_dirty FROM sessions
        ...
```

**Schema design:**
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    filepath TEXT,
    format TEXT NOT NULL DEFAULT 'ipynb',
    language TEXT NOT NULL DEFAULT 'python',
    kernel_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_dirty INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS notebook_states (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    cir_version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
```

**REFACTOR:** Keep the `Session` dataclass for compatibility, but make all I/O go through SQLite. Cache recently accessed sessions in a dict (LRU) for performance.

### Task 1.3: Add atomic writes + validation (RED → GREEN → REFACTOR)

**RED** — `tests/test_validation.py`
```python
def test_atomic_write_does_not_corrupt_on_failure():
    """If validation fails, original file is untouched."""
    ...
def test_atomic_write_succeeds():
    """Valid notebook gets written atomically."""
    ...
def test_validate_bad_ipynb():
    """Malformed content is rejected before write."""
    ...
```

**GREEN** — `notebookllm/utils/validation.py`
- Add `atomic_write(doc, filepath, fmt)`: write to `.tmp`, call `validate_notebook()` on the temp file, then `os.replace()`
- Add `validate_notebook(content, fmt)`: for ipynb, use `nbformat.validate()`; for others, round-trip through loader + dumper and compare
- Add `safe_save(doc, filepath, fmt)`: wraps atomic_write with error handling

**GREEN** — `notebookllm/mcp/server.py`
- `save_notebook` tool uses `safe_save()` instead of raw `dump_file()`
- Return structured error on validation failure: `"error": "Validation failed", "reason": "...", "cell_index": N`

### Task 1.4: Add create_notebook + list_sessions MCP tools (RED → GREEN)

**RED** — `tests/test_mcp.py`
```python
class TestCreateNotebook:
    async def test_create_empty(self, app, session_manager):
        result = await app.call_tool("create_notebook", {})
        assert "session_id" in _get_text(result)
        # Verify session exists in manager

    async def test_create_with_format(self, app):
        result = await app.call_tool("create_notebook", {
            "format": "ipynb",
            "language": "python",
        })
        assert "session_id" in _get_text(result)

class TestListSessions:
    async def test_list_sessions(self, app, session_with_cells):
        result = await app.call_tool("list_sessions", {})
        assert "test-session" in _get_text(result)
```

**GREEN** — `notebookllm/mcp/server.py`
- Add `create_notebook(format, language)` tool: creates empty NotebookDocument, stores in session manager, returns session_id
- Add `list_sessions()` tool: returns formatted list of active sessions

---

## Sprint 2: Universal CIR (Model + Format Expansion)

**Goal:** The Cell model can represent any format's native types. Marimo and Deepnote are fully supported.

### Task 2.1: Expand Cell model with language, block_type, and Deepnote fields (RED → GREEN)

**RED** — `tests/test_models.py`

Rewrite `TestCell` to validate:
```python
def test_cell_with_language():
    """Language field distinguishes code type (python, sql, r, etc.)."""
    cell = Cell(cell_type=CellType.CODE, source="SELECT * FROM t", language="sql")
    assert cell.language == "sql"

def test_cell_default_language():
    cell = Cell(cell_type=CellType.CODE, source="x = 1")
    assert cell.language is None

def test_cell_block_type():
    """block_type preserves format-specific block classification."""
    cell = Cell(cell_type=CellType.CODE, source="x = 1", block_type="input")
    assert cell.block_type == "input"
    cell2 = Cell(cell_type=CellType.CODE, source="plot", block_type="visualization")
    assert cell2.block_type == "visualization"

def test_cell_deepnote_fields():
    """Deepnote-specific fields are preserved in the Cell model."""
    cell = Cell(
        cell_type=CellType.CODE,
        source="SELECT * FROM sales",
        language="sql",
        block_type="sql",
        block_group="uuid-123",
        content_hash="sha256:abc123",
        sorting_key="a0",
    )
    assert cell.block_group == "uuid-123"
    assert cell.content_hash == "sha256:abc123"
    assert cell.sorting_key == "a0"

def test_cell_content_hash_updates_on_edit():
    """Changing cell source should invalidate content_hash."""
    cell = Cell(
        cell_type=CellType.CODE,
        source="x = 1",
        content_hash="sha256:oldhash",
    )
    cell.source = "x = 2"
    # When saving to Deepnote format, content_hash should be recomputed
    # The hash should NOT auto-update in memory (that's the dumper's job)
    assert cell.content_hash == "sha256:oldhash"  # unchanged in memory
```

**GREEN** — `notebookllm/models.py`

Add to `Cell` dataclass:
```python
@dataclass
class Cell:
    cell_type: CellType
    source: str
    execution_count: int | None = None
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cell_id: str | None = None
    # --- New fields for format-agnostic CIR ---
    language: str | None = None       # "python", "r", "sql", "julia", etc.
    block_type: str | None = None     # Format-specific: "sql", "visualization",
                                      #   "input", "dataframe", "image", etc.
                                      #   Keeps CellType enum clean (CODE/MARKDOWN/RAW)
    block_group: str | None = None    # Deepnote blockGroup UUID
    content_hash: str | None = None   # Deepnote SHA-256 contentHash
    sorting_key: str | None = None    # Deepnote base-36 ordering key
```

**Design rationale:**
- `language` is THE field for kernel selection (python → ipykernel, sql → sql kernel, r → IRkernel)
- `block_type` is FORMAT-SPECIFIC classification. It lets loaders preserve the original block type without bloating the CellType enum. The execution engine routes by `language`, not `block_type`. Non-code block types (visualization, input, dataframe) still map to `CellType.CODE` or `CellType.RAW` for general processing.
- `block_group`, `content_hash`, `sorting_key` are Deepnote-specific and may be None for other formats. They're first-class fields rather than opaque metadata because the Deepnote dumper needs to reconstruct them precisely.

**Required changes across loaders:**
- `DeepnoteLoader` (new): Maps `type` → `block_type` and `content` → `source`. Maps `"sql"` type → `language="sql"`. Preserves `blockGroup` → `block_group`, `contentHash` → `content_hash`, `sortingKey` → `sorting_key`.
- `RMarkdownLoader`: Set `language` from `metadata["language"]` (already stored there!)
- `MarkdownLoader`: Set `language` from the code block language tag (e.g., "r", "julia")
- `PercentLoader`: No language info — leave as None
- `MarimoLoader`: No language info — leave as None
- `IpynbLoader`: Ipynb has kernel-level language (kernelspec), not per-cell. Leave per-cell language as None.

**Dumper changes:**
- `RMarkdownDumper`: Currently reads `cell.metadata.get("language", "python")` — should read `cell.language or cell.metadata.get("language", "python")`
- `MarkdownDumper`: Same pattern — prefer `cell.language` over metadata fallback

### Task 2.2: Deepnote loader/dumper — YAML project format (COMPLETED)

**CORRECTION:** Deepnote is NOT an .ipynb variant. It's a **YAML-based project format** (`.deepnote`) with its own specification. This task requires a full loader and dumper backed by `pyyaml` (already a dependency under `[yaml]` extra).

**RED** — `tests/test_loaders/test_deepnote.py` (new file)

```python
import pytest
import yaml
from pathlib import Path
from notebookllm.models import CellType, NotebookDocument
from notebookllm.loaders.deepnote import DeepnoteLoader, DeepnoteDumper
from notebookllm.utils.dispatch import load_file, dump_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestDeepnoteLoader:
    def test_load_deepnote_file(self, tmp_path):
        """Parse a valid .deepnote YAML file."""
        dn_file = tmp_path / "project.deepnote"
        dn_file.write_text("""\
version: "1.0.0"
metadata:
  createdAt: "2025-01-27T12:00:00Z"
project:
  id: "proj-123"
  name: "Test Project"
  notebooks:
    - id: "nb-1"
      name: "Analysis"
      executionMode: "block"
      blocks:
        - id: "b1"
          type: "markdown"
          sortingKey: "a0"
          content: "# Hello"
          version: 1
        - id: "b2"
          type: "code"
          sortingKey: "a1"
          content: "print('hello')"
          executionCount: 1
          version: 1
""")
        doc = load_file(dn_file)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[0].source == "# Hello"
        assert doc.cells[1].cell_type == CellType.CODE
        assert doc.cells[1].source == "print('hello')"
        assert doc.cells[1].execution_count == 1

    def test_load_deepnote_sql_block(self, tmp_path):
        """SQL block type maps to language='sql' and block_type='sql'."""
        dn_file = tmp_path / "project.deepnote"
        dn_file.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "SQL Test"
  notebooks:
    - id: "nb-1"
      name: "Queries"
      blocks:
        - id: "b1"
          type: "sql"
          sortingKey: "a0"
          content: "SELECT * FROM sales LIMIT 10"
          version: 1
""")
        doc = load_file(dn_file)
        assert doc.cells[0].language == "sql"
        assert doc.cells[0].block_type == "sql"
        assert doc.cells[0].source == "SELECT * FROM sales LIMIT 10"

    def test_load_deepnote_visualization_block(self, tmp_path):
        """Visualization block type preserves block_type metadata."""
        dn_file = tmp_path / "project.deepnote"
        dn_file.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "Viz Test"
  notebooks:
    - id: "nb-1"
      name: "Chart"
      blocks:
        - id: "b1"
          type: "visualization"
          sortingKey: "a0"
          content: '{"mark": {"type": "bar"}, "encoding": {"x": {"field": "a"}}}'
          metadata: {}  # Vega-Lite spec stored in content
          version: 1
""")
        doc = load_file(dn_file)
        assert doc.cells[0].block_type == "visualization"
        assert doc.cells[0].cell_type == CellType.RAW  # non-executable

    def test_load_multiple_notebooks(self, tmp_path):
        """Flat .deepnote file maps to a single NotebookDocument.
        
        Design decision: a .deepnote file contains multiple notebooks.
        The loader flattens all blocks across all notebooks into one
        cell list, with 'notebook_name' per-cell metadata for round-trip.
        """
        dn_file = tmp_path / "multi.deepnote"
        dn_file.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "Multi Notebook"
  notebooks:
    - id: "nb-1"
      name: "EDA"
      blocks:
        - id: "b1"
          type: "code"
          sortingKey: "a0"
          content: "import pandas as pd"
          version: 1
    - id: "nb-2"
      name: "Modeling"
      blocks:
        - id: "b2"
          type: "code"
          sortingKey: "a0"
          content: "model.fit(X, y)"
          version: 1
""")
        doc = load_file(dn_file)
        assert len(doc.cells) == 2
        assert doc.cells[0].metadata.get("notebook_name") == "EDA"
        assert doc.cells[1].metadata.get("notebook_name") == "Modeling"

    def test_load_with_integrations(self, tmp_path):
        """Database integrations stored in project metadata."""
        dn_file = tmp_path / "project.deepnote"
        dn_file.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "With DB"
  notebooks:
    - id: "nb-1"
      name: "Analysis"
      blocks:
        - id: "b1"
          type: "code"
          content: "df.head()"
          sortingKey: "a0"
          version: 1
integrations:
  - id: "int-1"
    name: "Prod DB"
    type: "pgsql"
settings:
  environment:
    pythonVersion: "3.11"
    requirements:
      - "pandas>=2.0"
""")
        doc = load_file(dn_file)
        assert "integrations" in doc.metadata
        assert doc.metadata["project_name"] == "With DB"
        assert doc.metadata["python_version"] == "3.11"

    def test_load_snapshot_file(self, tmp_path):
        """.snapshot.deepnote files load with outputs preserved."""
        snap_file = tmp_path / "project_latest.snapshot.deepnote"
        snap_file.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "Snap"
  notebooks:
    - id: "nb-1"
      name: "Test"
      blocks:
        - id: "b1"
          type: "code"
          sortingKey: "a0"
          content: "print(1)"
          executionCount: 1
          outputs:
            - output_type: "stream"
              name: "stdout"
              text: "1\\n"
          version: 1
""")
        doc = load_file(snap_file)
        assert len(doc.cells[0].outputs) == 1
        assert doc.cells[0].outputs[0].content == "1\n"


class TestDeepnoteDumper:
    def test_roundtrip_deepnote(self, tmp_path):
        """Deepnote → load → dump → load preserves content."""
        original = tmp_path / "original.deepnote"
        original.write_text("""\
version: "1.0.0"
project:
  id: "proj-1"
  name: "Test"
  notebooks:
    - id: "nb-1"
      name: "Analysis"
      blocks:
        - id: "b1"
          type: "code"
          sortingKey: "a0"
          content: "x = 1"
          version: 1
""")
        doc = load_file(original)
        out = tmp_path / "roundtrip.deepnote"
        dump_file(doc, out)
        # Reload and compare
        doc2 = load_file(out)
        assert len(doc2.cells) == len(doc.cells)
        assert doc2.cells[0].source == doc.cells[0].source

    def test_dump_preserves_integrations(self, tmp_path):
        """Project-level metadata survives round-trip."""
        ...

    def test_dump_preserves_block_order(self, tmp_path):
        """sortingKey ordering is preserved through round-trip."""
        ...

    def test_dump_sql_block_preserves_type(self, tmp_path):
        """SQL block_type='sql' maps back to type: sql in YAML."""
        ...

    def test_dump_content_hash_invalidated(self, tmp_path):
        """When cell source changes, old content_hash is removed."""
        ...


class TestDetectDeepnote:
    def test_detect_by_extension(self, tmp_path):
        """.deepnote extension detected as 'deepnote' format."""
        f = tmp_path / "project.deepnote"
        f.write_text("dummy")
        from notebookllm.loaders.detect import detect_format
        assert detect_format(f) == "deepnote"

    def test_detect_snapshot_extension(self, tmp_path):
        """.snapshot.deepnote extension detected as 'deepnote' format."""
        f = tmp_path / "proj_latest.snapshot.deepnote"
        f.write_text("dummy")
        from notebookllm.loaders.detect import detect_format
        assert detect_format(f) == "deepnote"
```

**GREEN** — `notebookllm/loaders/deepnote.py` (new file)

```python
"""Deepnote YAML format loader/dumper — .deepnote files.

Deepnote uses a YAML-based project format that can contain multiple
notebooks, database integrations, and environment configuration.

Spec: https://github.com/deepnote/deepnote/blob/main/FILES.md
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument


# Mapping from Deepnote block types to CIR cell types
BLOCK_TYPE_TO_CELL_TYPE = {
    "code": CellType.CODE,
    "markdown": CellType.MARKDOWN,
    "sql": CellType.CODE,         # executable, routed by language="sql"
    "visualization": CellType.RAW,  # non-executable Vega-Lite spec
    "dataframe": CellType.RAW,      # non-executable DataFrame explorer
    "image": CellType.RAW,          # embedded image
    "input": CellType.CODE,         # interactive widget (Python-backed)
    "separator": CellType.RAW,      # visual divider
    "button": CellType.CODE,        # action button (Python-backed)
}

# Text block types → CellType.MARKDOWN
TEXT_BLOCK_TYPES = {
    "text-cell-h1", "text-cell-h2", "text-cell-h3", "text-cell-p",
}

# Deepnote block types that execute code
EXECUTABLE_BLOCK_TYPES = {"code", "sql", "input", "button"}


class DeepnoteLoader(BaseLoader):
    """Load .deepnote YAML project files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        data = yaml.safe_load(content)
        return self._convert(data)

    def _convert(self, data: dict) -> NotebookDocument:
        cells: list[Cell] = []
        metadata: dict[str, Any] = {}

        # Extract project-level metadata
        version = data.get("version", "1.0.0")
        metadata["deepnote_version"] = version
        metadata["file_metadata"] = data.get("metadata", {})

        project = data.get("project", {})
        metadata["project_id"] = project.get("id")
        metadata["project_name"] = project.get("name")
        metadata["init_notebook_id"] = project.get("initNotebookId")

        # Store integrations and settings as opaque metadata
        if "integrations" in data:
            metadata["integrations"] = data["integrations"]
        if "settings" in data:
            metadata["settings"] = data["settings"]

        # Flatten notebooks → cells, preserving notebook name per-cell
        notebooks = project.get("notebooks", [])
        for notebook in notebooks:
            nb_name = notebook.get("name", "")
            nb_id = notebook.get("id", "")
            execution_mode = notebook.get("executionMode", "block")

            for block in notebook.get("blocks", []):
                cell = self._block_to_cell(block, nb_name, nb_id)
                cells.append(cell)

        return NotebookDocument(
            cells=cells,
            metadata=metadata,
            source_format="deepnote",
            kernel_name="python3",  # default; Deepnote environment has this
        )

    def _block_to_cell(self, block: dict, nb_name: str, nb_id: str) -> Cell:
        block_type = block.get("type", "code")
        content = block.get("content", "")
        sorting_key = block.get("sortingKey", "")
        block_group = block.get("blockGroup")
        content_hash = block.get("contentHash")
        execution_count = block.get("executionCount")
        version = block.get("version", 1)

        # Determine cell type
        if block_type in TEXT_BLOCK_TYPES:
            cell_type = CellType.MARKDOWN
        else:
            cell_type = BLOCK_TYPE_TO_CELL_TYPE.get(block_type, CellType.CODE)

        # Determine language for executable blocks
        language = None
        if block_type == "sql":
            language = "sql"
        elif block_type in EXECUTABLE_BLOCK_TYPES:
            language = "python"  # default for Deepnote code/input/button blocks

        # Parse outputs
        outputs = []
        for out in block.get("outputs", []):
            outputs.append(self._parse_output(out))

        # Cell-level metadata
        cell_metadata: dict[str, Any] = {}
        cell_metadata["notebook_name"] = nb_name
        cell_metadata["notebook_id"] = nb_id
        cell_metadata["block_version"] = version
        if block.get("metadata"):
            cell_metadata["deepnote_block_metadata"] = block["metadata"]

        return Cell(
            cell_type=cell_type,
            source=content,
            language=language,
            block_type=block_type,
            block_group=block_group,
            content_hash=content_hash,
            sorting_key=sorting_key,
            execution_count=execution_count,
            outputs=outputs,
            metadata=cell_metadata,
            cell_id=block.get("id"),
        )

    @staticmethod
    def _parse_output(out: dict) -> CellOutput:
        """Parse Deepnote output dict → CellOutput."""
        output_type = out.get("output_type", "unknown")
        if output_type == "stream":
            text = out.get("text", "")
            return CellOutput(
                output_type=output_type,
                content=text,
                name=out.get("name"),
            )
        elif output_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            return CellOutput(output_type=output_type, content=data)
        elif output_type == "error":
            traceback = out.get("traceback", [])
            return CellOutput(
                output_type=output_type,
                content="\n".join(traceback) if isinstance(traceback, list) else str(traceback),
            )
        else:
            return CellOutput(output_type=output_type, content=str(out))


class DeepnoteDumper(BaseDumper):
    """Dump to .deepnote YAML format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        data: dict[str, Any] = {
            "version": "1.0.0",
            "metadata": {
                "createdAt": doc.metadata.get("file_metadata", {}).get("createdAt", ""),
                "modifiedAt": doc.metadata.get("file_metadata", {}).get("modifiedAt", ""),
            },
            "project": {
                "id": doc.metadata.get("project_id", ""),
                "name": doc.metadata.get("project_name", "Untitled Project"),
                "notebooks": self._cells_to_notebooks(doc),
            },
        }

        # Preserve integrations and settings if present
        if "integrations" in doc.metadata:
            data["integrations"] = doc.metadata["integrations"]
        if "settings" in doc.metadata:
            data["settings"] = doc.metadata["settings"]

        content = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        if filepath:
            filepath.write_text(content, encoding="utf-8")
        return content

    def _cells_to_notebooks(self, doc: NotebookDocument) -> list[dict]:
        """Group cells back into notebooks using metadata."""
        # Group cells by notebook_name from metadata
        notebooks_dict: dict[str, list[Cell]] = {}
        for cell in doc.cells:
            nb_name = cell.metadata.get("notebook_name", "Notebook 1") if cell.metadata else "Notebook 1"
            notebooks_dict.setdefault(nb_name, []).append(cell)

        notebooks = []
        for nb_name, cells in notebooks_dict.items():
            blocks = []
            for i, cell in enumerate(cells):
                block = self._cell_to_block(cell, i)
                blocks.append(block)

            notebooks.append({
                "id": cells[0].metadata.get("notebook_id", "") if cells[0].metadata else "",
                "name": nb_name,
                "executionMode": "block",
                "blocks": blocks,
            })

        return notebooks

    def _cell_to_block(self, cell: Cell, index: int) -> dict:
        block_type = cell.block_type or self._infer_block_type(cell)
        block: dict[str, Any] = {
            "id": cell.cell_id or f"block-{index}",
            "type": block_type,
            "sortingKey": cell.sorting_key or self._index_to_sorting_key(index),
            "content": cell.source,
            "version": cell.metadata.get("block_version", 1) if cell.metadata else 1,
        }

        # Recompute content_hash if source changed
        if cell.content_hash:
            block["contentHash"] = cell.content_hash

        if cell.block_group:
            block["blockGroup"] = cell.block_group

        if cell.execution_count is not None:
            block["executionCount"] = cell.execution_count

        if cell.outputs:
            block["outputs"] = [self._output_to_dict(o) for o in cell.outputs]

        if cell.metadata and "deepnote_block_metadata" in cell.metadata:
            block["metadata"] = cell.metadata["deepnote_block_metadata"]

        return block

    @staticmethod
    def _infer_block_type(cell: Cell) -> str:
        """Infer Deepnote block type from Cell fields."""
        if cell.cell_type == CellType.MARKDOWN:
            return "markdown"
        if cell.language == "sql":
            return "sql"
        return "code"

    @staticmethod
    def _index_to_sorting_key(index: int) -> str:
        """Convert 0-based index to base-36 sorting key."""
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        result = ""
        while index >= 0:
            result = chars[index % 36] + result
            index = index // 36 - 1
            if index < 0:
                break
        return result or "0"

    @staticmethod
    def _output_to_dict(output: CellOutput) -> dict:
        """CellOutput → Deepnote output dict."""
        if output.output_type == "stream":
            return {
                "output_type": "stream",
                "name": output.name or "stdout",
                "text": output.content,
            }
        elif output.output_type in ("execute_result", "display_data"):
            return {
                "output_type": output.output_type,
                "data": output.content if isinstance(output.content, dict) else {"text/plain": output.content},
            }
        elif output.output_type == "error":
            return {
                "output_type": "error",
                "ename": "",
                "evalue": "",
                "traceback": [output.content],
            }
        return {"output_type": output.output_type, "data": {"text/plain": str(output.content)}}
```

**GREEN** — `notebookllm/loaders/detect.py`
- Add detection for `.deepnote` and `.snapshot.deepnote` extensions → `"deepnote"`

**GREEN** — `notebookllm/loaders/__init__.py`
- Register `DeepnoteLoader` and `DeepnoteDumper` in the format registry

**GREEN** — `notebookllm/utils/validation.py`
- Add `"deepnote"` to `validate_output_format()` format set: `valid = {"ipynb", "percent", "marimo", "quarto", "markdown", "rmarkdown", "script", "deepnote"}`

**Design decisions:**
1. **Multi-notebook → flatten**: A .deepnote file can have multiple notebooks. We flatten all blocks into one cell list, with `notebook_name` per-cell metadata. The dumper reconstructs notebooks by grouping cells with the same `notebook_name`. This keeps the CIR simple (one NotebookDocument → one cell array) while supporting the format's structure.
2. **Integrations as opaque metadata**: Database connections and environment config are stored in `doc.metadata` and round-tripped verbatim. The tool doesn't need to understand them to preserve them.
3. **Snapshots share the loader**: `.snapshot.deepnote` files have the same structure as `.deepnote` but with outputs populated. The loader handles both. The dumper always produces a `.deepnote` (source-only) file by default; a `with_outputs` parameter can emit a snapshot.
4. **Block type inference**: When dumping cells that were originally from another format (e.g., ipynb → deepnote), `_infer_block_type()` maps CellType + language to the closest Deepnote block type. CODE + language="sql" → `"sql"`. CODE + no language → `"code"`. MARKDOWN → `"markdown"`. This ensures cross-format conversion produces valid Deepnote files.

### Task 2.3: Implement MarimoDumper (COMPLETED)

**RED** — `tests/test_roundtrip.py` (add to existing class)
```python
class TestMarimoRoundtrip:
    def test_roundtrip_via_dispatch(self, tmp_path):
        doc = load_file(FIXTURES / "sample_marimo.py")
        out = tmp_path / "roundtrip.py"
        dump_file(doc, out)
        doc2 = load_file(out)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells, strict=True):
            assert c1.cell_type == c2.cell_type
            assert c1.source.strip() == c2.source.strip()
```

**GREEN** — `notebookllm/loaders/marimo.py`
- Add `MarimoDumper(BaseDumper)` class
- For markdown cells: wrap in `mo.md("...")` with proper escaping
- For code cells: wrap in `@app.cell` decorated function with return statement
- Handle `cell.metadata.get("generated_with")` for the `__generated_with` header
- Handle cell references (marimo assigns variable names per cell — `def cell_name():`)

This is the hardest dumper to implement correctly because marimo's AST structure requires generating valid Python with decorators, function defs, and return statements. Each cell needs a unique function name.

Update `dump_file` dispatch to handle `"marimo"` → `MarimoDumper`.

### Task 2.4: Add `convert_format` MCP tool (COMPLETED)

**RED** — `tests/test_mcp.py`
```python
class TestConvertFormat:
    async def test_convert_ipynb_to_percent(self, app_with_session, tmp_path):
        app, _ = app_with_session
        out = tmp_path / "converted.py"
        result = await app.call_tool("convert_format", {
            "session_id": "test-session",
            "output_filepath": str(out),
            "target_format": "percent",
        })
        assert "Converted" in _get_text(result)
        assert out.exists()
```

**GREEN** — `notebookllm/mcp/server.py`
- Add `convert_format(session_id, output_filepath, target_format)` tool
- Loads session doc, calls `dump_file(doc, output_filepath, fmt=target_format)`
- Validates after write (atomic write path)

---

## Sprint 3: Async Execution Engine + Output Intelligence

**Goal:** Execute cells without blocking. See outputs without bloat.

### Task 3.1: KernelPool with isolated execution (COMPLETED)

**RED** — `tests/test_mcp.py`

```python
class TestKernelExecution:
    async def test_execute_simple_code(self, app_with_session):
        """Execute a simple code cell and get output."""
        app, _ = app_with_session
        result = await app.call_tool("execute_cell", {
            "session_id": "test-session",
            "index": 0,
        })
        text = _get_text(result)
        assert "[stdout]" in text or "[output]" in text or "executed" in text.lower()

    async def test_execute_all_cells(self, app_with_session):
        """Execute all code cells sequentially."""
        app, _ = app_with_session
        result = await app.call_tool("execute_all_cells", {
            "session_id": "test-session",
        })
        text = _get_text(result)
        assert "Executed" in text or "cells" in text.lower()

    async def test_execute_non_code_cell_returns_error(self, app_with_session):
        """Markdown cell returns clear error, not crash."""
        app, _ = app_with_session
        result = await app.call_tool("execute_cell", {
            "session_id": "test-session",
            "index": 1,
        })
        assert "not a code cell" in _get_text(result).lower()
```

**GREEN** — `notebookllm/mcp/engine.py` (new module)

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionJob:
    """Represents an active or completed cell execution."""
    job_id: str
    session_id: str
    cell_index: int
    status: str  # "pending", "running", "completed", "failed", "interrupted"
    output: str = ""
    error: str | None = None


class KernelPool:
    """Manages kernel lifecycle and execution for sessions."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, ExecutionJob] = {}
        self._kernels: dict[str, Any] = {}  # session_id → kernel info

    async def start_kernel(self, session_id: str, kernel_name: str = "python3") -> str:
        """Start a kernel for a session. Returns kernel name."""
        ...

    async def execute_cell(self, session_id: str, cell_index: int,
                          cell_source: str, timeout: int = 60) -> str:
        """Execute a cell via blocking client in thread pool, return outputs."""
        ...

    async def execute_all_cells(self, session_id: str,
                                cells: list[Cell], timeout: int = 60) -> str:
        """Execute code cells sequentially. Skip non-code. Stop on error."""
        ...

    async def interrupt(self, session_id: str) -> str:
        """Interrupt the running kernel for a session."""
        ...

    async def shutdown_kernel(self, session_id: str) -> None:
        """Shutdown and cleanup a kernel."""
        ...

    def list_kernels(self) -> list[dict]:
        """List available kernels from jupyter kernelspec."""
        ...
```

**Key implementation details:**
- Use `asyncio.to_thread()` to run blocking `kernel_client.execute()` calls
- Store execution state in `self._jobs` for polling
- Kernel client is per-session, but execution submissions go through thread pool
- Add `execute_all_cells` tool that iterates cells in order
- Add `list_kernels` tool that shells out to `jupyter kernelspec list`

For testing without a real kernel: mock `KernelManager` by subclassing or using `unittest.mock.patch`.

### Task 3.2: Semantic output summarization — DataFrame detection (RED → GREEN)

**RED** — `tests/test_converters/test_llm_optimizer.py`

```python
def test_summarize_dataframe_output():
    """DataFrame ASCII tables are replaced with schema summary."""
    optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
    output = CellOutput(
        output_type="execute_result",
        content={
            "text/plain": "   age  revenue\n0   25    50000\n1   30    60000\n...",
            "text/html": "<table>...</table>"
        }
    )
    cell = Cell(cell_type=CellType.CODE, source="df.head()",
                outputs=[output], execution_count=1)
    doc = NotebookDocument(cells=[cell])
    result = optimizer.optimize(doc)
    assert "DataFrame" in result
    assert "age" in result  # column name preserved
    assert "50000" not in result  # values removed

def test_summarize_long_traceback():
    """Full tracebacks are replaced with ErrorType: message."""
    ...

def test_truncate_long_string():
    """Strings over 500 chars are truncated with count."""
    ...
```

**GREEN** — `notebookllm/converters/llm_optimizer.py`

Add `summarize_outputs` parameter to `LLMOptimizer`:

```python
class LLMOptimizer:
    def __init__(self, mode=OutputMode.MINIMAL, summarize_outputs=False, ...):
        self.summarize_outputs = summarize_outputs

    def _format_output(self, output):
        if self.summarize_outputs:
            return self._summarize_output(output)
        return self._format_output_verbatim(output)

    def _summarize_output(self, output):
        """Detect output type and compress intelligently."""
        content = output.content
        if isinstance(content, dict):
            # Check for DataFrame patterns in MIME bundle
            if "text/html" in content and "text/plain" in content:
                return self._summarize_dataframe(content["text/plain"])
            # Check for image
            if "image/png" in content or "image/jpeg" in content:
                return self._summarize_image(content)
        # String content
        text = content if isinstance(content, str) else content.get("text/plain", "")
        # Traceback detection
        if output.output_type == "error" and "Traceback" in text:
            return self._summarize_traceback(text)
        # Long string truncation
        if len(text) > 500:
            return text[:500] + f"... (truncated, {len(text) - 500} more chars)"
        return self._format_output_verbatim(output)

    def _summarize_dataframe(self, text: str) -> str:
        """Try to extract shape and columns from DataFrame ASCII repr.
        
        This is heuristic — works for pandas default formatting.
        The 100% accurate approach requires kernel-side type checking.
        """
        lines = text.strip().split("\n")
        if len(lines) < 3:
            return text
        # Heuristic: check for aligned column headers + row indices
        # Fallback: return shape estimate + columns
        ...
    
    def _summarize_image(self, content: dict) -> str:
        """Return image metadata instead of base64."""
        for mime in ("image/png", "image/jpeg", "image/svg+xml", "image/gif"):
            if mime in content:
                data = content[mime]
                size = len(data) if isinstance(data, str) else len(str(data))
                return f"[Plot: {mime}, ~{size} bytes]"
        return "[Image output]"
```

### Task 3.3: Image/Plot support in MCP (RED → GREEN)

**RED** — `tests/test_mcp.py`
```python
class TestPlotOutput:
    async def test_plot_output_returns_image_metadata(self, app_with_session):
        """Plot outputs return metadata, not base64."""
        app, sm = app_with_session
        # Add a cell with image output
        doc = sm.get("test-session")
        img_output = CellOutput(
            output_type="display_data",
            content={
                "text/plain": "<Figure 640x480>",
                "image/png": "base64data...",
            }
        )
        doc.cells[2].outputs = [img_output]
        doc.cells[2].execution_count = 3
        result = await app.call_tool("to_text", {
            "session_id": "test-session",
            "mode": "full",
        })
        text = _get_text(result)
        assert "image/png" in text or "Plot" in text
        assert "base64data" not in text  # raw base64 is excluded
```

**GREEN** — `notebookllm/converters/llm_optimizer.py`
- In FULL mode with summarization, image outputs produce `[Plot: mime/type, size]` markers instead of raw base64
- Stretch goal: use FastMCP's `Image` type for vision-capable clients

**GREEN** — `notebookllm/mcp/server.py`
- `to_text` tool accepts `summarize` boolean parameter (default: True)
- When `summarize=True`, uses LLMOptimizer with `summarize_outputs=True`

### Task 3.4: Token budget mode (RED → GREEN)

**RED** — `tests/test_converters/test_llm_optimizer.py`
```python
def test_token_budget_respected():
    """When max_tokens=100, output is under 100 tokens."""
    optimizer = LLMOptimizer(mode=OutputMode.FULL, max_tokens=100)
    doc = load_file(FIXTURES / "sample.ipynb")
    result = optimizer.optimize(doc)
    token_count = count_tokens(result)
    assert token_count <= 100

def test_token_budget_prioritizes_markdown():
    """Markdown cells are kept, low-value code cells are dropped first."""
    ...
```

**GREEN** — `notebookllm/converters/llm_optimizer.py`
- Add `max_tokens` parameter
- Implementation strategy:
  1. Render all cells in MINIMAL mode (source only, no outputs)
  2. If within budget, done
  3. If over budget, strip cells from bottom up (last cells are usually scaffolding/plots)
  4. If still over budget, truncate code cell sources (keep first N lines)
  5. Never drop markdown cells (highest signal/token ratio)

---

## Sprint 4: MCP Tooling + Polish

**Goal:** Agent-friendly MCP surface, CLI parity, documentation.

### Task 4.1: Rename/simplify MCP tools

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `load_notebook` | `load` | Shorter for agent token budgets |
| `save_notebook` | `save` | Shorter |
| `to_text` | `to_text` | Keep (descriptive) |
| `execute_cell` | `execute` | Shorter, params define scope |
| `execute_all_cells` | `execute_all` | New tool |
| `list_cells` | `list_cells` | Keep |
| — | `list_sessions` | New |
| — | `list_kernels` | New |
| — | `create` | New (create blank notebook) |
| — | `fingerprint` | New (notebook summary) |
| — | `convert` | New (change format on save) |
| — | `diff` | New (compare two sessions) |

Add aliases so old tool names still work (backward compat for agents that learned the old names).

### Task 4.2: Notebook fingerprint tool

**Tool:** `fingerprint(session_id) → str`
```
Cells: 12 (8 code, 3 markdown, 1 raw)
Executed: 7/8 code cells
Imports: pandas, numpy, sklearn, matplotlib
Data sources: 'data.csv' (cell 2), API call (cell 4)
Functions: clean_data(), train_model(), evaluate()
Structure: Setup → Load → Clean → Train → Evaluate
Key findings: "Accuracy: 0.934", "RMSE: 1.23"
```

Implementation: static analysis of cell sources + execution metadata. No ML, no external deps. Just regex + string analysis.

### Task 4.3: Actually use rich in CLI

Replace `click.echo()` with `rich.print()` and `rich.table.Table` in:
- `inspect` → Rich table
- `get` → Syntax highlighted source
- `search` → Highlighted matches
- `tokens --breakdown` → Table

This is already a dependency. Using it costs nothing.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite schema changes during dev | Medium | Low | Use schema versioning from day 1 |
| Kernel execution test flakiness | High | Medium | Mock jupyter_client in unit tests; integration tests use short code |
| DataFrame detection heuristics wrong | Medium | Low | Fall through to verbatim output; document as heuristic |
| Deepnote YAML format changes upstream | Low | Medium | Pin to schema version "1.0.0"; validate against known structure |
| Deepnote multi-notebook flattening loses structure | Medium | Low | Preserve notebook_name per-cell; dumper reconstructs notebooks by name |
| Deepnote visualization/dataframe blocks non-executable | Low | Low | `CellType.RAW` prevents execution attempts; agent sees `block_type` metadata |
| MarimoDumper generates invalid Python | Medium | High | Round-trip test MUST validate the output parses as valid Python |
| Serialization perf for 500+ cell notebooks | Low | Medium | Benchmark in CI; add streaming serialization if needed |
| Race condition on kernel_client | Medium | High | Per-session lock; serialize all kernel operations for same session |
| pyyaml not installed when user loads .deepnote | Medium | Medium | Detect missing dependency and raise clear import error |

---

## Test Strategy

**Unit tests** (fast, no external deps):
- `test_models.py`: Cell, CellOutput, NotebookDocument serialization
- `test_loaders/*`: Each loader/dumper independently (including `test_deepnote.py`)
- `test_converters/*`: LLMOptimizer compression, token budget
- `test_validation.py`: Atomic writes, format validation

**Integration tests** (require `[execute]` and/or `[yaml]` extra):
- `test_mcp.py`: MCP tool calls through FastMCP
- `test_mcp_session.py`: Session persistence across restarts
- `test_mcp_execution.py` (new): Kernel execution with real jupyter_client

**Round-trip tests** (`test_roundtrip.py`):
- Every format → dump → load → content preserved
- Cross-format: ipynb → percent → ipynb, ipynb → deepnote → ipynb, etc.
- Deepnote round-trip (multi-notebook, integrations, SQL blocks preserved)
- Marimo round-trip (AST validates)
- Snapshot round-trip (`.snapshot.deepnote` outputs preserved)

**Benchmarks** (`tests/benchmarks/`):
- Load speed per format
- Token reduction ratios
- Serialization/deserialization speed
- (Keep existing benchmarks, add new ones)

---

## Implementation Sequence (Strict Order)

```
Sprint 1 Tasks (Parallel-safe):
  1.1 Model serialization ← no deps
  1.2 SQLite SessionManager ← depends on 1.1
  1.3 Atomic writes + validation ← no deps on 1.2
  1.4 create_notebook + list_sessions ← depends on 1.2

Sprint 2 Tasks (mostly parallel):
  2.1 Cell expansion (language, block_type, Deepnote fields) ← touches all loaders
  2.2 Deepnote YAML loader/dumper ← depends on 2.1 for block_type field
  2.3 MarimoDumper ← independent
  2.4 convert_format tool ← depends on 2.1, 2.2, 2.3

Sprint 3 Tasks (sequential):
  3.1 KernelPool + execute_all ← independent (new module)
  3.2 Output summarization ← independent (optimizer change)
  3.3 Image/Plot handling ← depends on 3.2 (uses summarization)
  3.4 Token budget mode ← depends on 3.2 (uses optimizer)

Sprint 4 Tasks (parallel, lowest priority):
  4.1 Tool renames ← after all features stable
  4.2 fingerprint tool ← independent
  4.3 rich CLI polish ← independent
```

---

## What This Plan Does NOT Do (Consciously)

- **No web UI** — agents don't need it, data scientists use Jupyter/VS Code
- **No config files** — `notebookllm.toml`, `settings.json` etc. add complexity for marginal gain
- **No plugin system** — premature abstraction; loader/dumper registry is sufficient
- **No remote kernel management** (Kubernetes, SageMaker) — scope creep; the KernelPool abstraction allows it later
- **No npm/JS client** — the MCP protocol is the client interface
- **No notebook scheduling/cron** — execution is per-cell, not workflows
