# notebookllm Merge & Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `notebookllm` + `notebookllm-mcp` into a single production-ready package with multi-format support, CLI + MCP server + agent skill, comprehensive tests, and maximum performance.

**Architecture:** Loader Pattern — each format has a dedicated parser (loader/dumper) converting to/from a unified `NotebookDocument` dataclass. The MCP server and CLI consume this model. LLM optimizer produces configurable output (minimal/standard/full).

**Tech Stack:** Python 3.11+, nbformat, click, mcp[cli], ijson, jupyter_client (optional)

---

## File Map

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package config, extras, entry points |
| `notebookllm/__init__.py` | Public API exports |
| `notebookllm/models.py` | NotebookDocument, Cell, CellType, OutputMode, CellOutput |
| `notebookllm/loaders/__init__.py` | Format auto-detection + dispatch |
| `notebookllm/loaders/base.py` | Abstract BaseLoader, BaseDumper |
| `notebookllm/loaders/ipynb.py` | .ipynb loader (nbformat + ijson streaming) |
| `notebookllm/loaders/percent.py` | .py percent format (# %% markers) |
| `notebookllm/loaders/marimo.py` | .py marimo format (AST parsing) |
| `notebookllm/loaders/quarto.py` | .qmd format |
| `notebookllm/loaders/markdown.py` | .md format |
| `notebookllm/converters/__init__.py` | Converter exports |
| `notebookllm/converters/llm_optimizer.py` | Minimal/standard/full output modes |
| `notebookllm/cli/__init__.py` | CLI package |
| `notebookllm/cli/commands.py` | click CLI with subcommands |
| `notebookllm/mcp/__init__.py` | MCP package |
| `notebookllm/mcp/server.py` | FastMCP server, 11 tools |
| `notebookllm/mcp/session.py` | SessionManager |
| `notebookllm/utils/__init__.py` | Utils package |
| `notebookllm/utils/detect.py` | Format detection |
| `notebookllm/utils/validation.py` | Input/output validation |
| `skills/notebookllm/SKILL.md` | Agent skill |
| `tests/fixtures/` | Sample notebooks in all formats |
| `tests/test_models.py` | Data model tests |
| `tests/test_loaders/` | Per-format parser tests |
| `tests/test_converters/` | LLM optimizer tests |
| `tests/test_cli.py` | CLI integration tests |
| `tests/test_mcp.py` | MCP server tests |
| `tests/test_roundtrip.py` | Format fidelity tests |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `notebookllm/models.py` (empty)
- Create: `notebookllm/loaders/__init__.py`, `notebookllm/loaders/base.py` (empty)
- Create: `notebookllm/loaders/ipynb.py`, `notebookllm/loaders/percent.py`, `notebookllm/loaders/marimo.py`, `notebookllm/loaders/quarto.py`, `notebookllm/loaders/markdown.py` (empty)
- Create: `notebookllm/converters/__init__.py`, `notebookllm/converters/llm_optimizer.py` (empty)
- Create: `notebookllm/cli/__init__.py`, `notebookllm/cli/commands.py` (empty)
- Create: `notebookllm/mcp/__init__.py`, `notebookllm/mcp/server.py`, `notebookllm/mcp/session.py` (empty)
- Create: `notebookllm/utils/__init__.py`, `notebookllm/utils/detect.py`, `notebookllm/utils/validation.py` (empty)
- Create: `tests/__init__.py`, `tests/fixtures/` (empty)
- Modify: `pyproject.toml`
- Modify: `notebookllm/__init__.py`

- [ ] **Step 1: Create directory structure**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
mkdir -p notebookllm/loaders notebookllm/converters notebookllm/cli notebookllm/mcp notebookllm/utils tests/fixtures tests/test_loaders tests/test_converters skills/notebookllm
touch notebookllm/loaders/__init__.py notebookllm/loaders/base.py notebookllm/loaders/ipynb.py notebookllm/loaders/percent.py notebookllm/loaders/marimo.py notebookllm/loaders/quarto.py notebookllm/loaders/markdown.py
touch notebookllm/converters/__init__.py notebookllm/converters/llm_optimizer.py
touch notebookllm/cli/__init__.py notebookllm/cli/commands.py
touch notebookllm/mcp/__init__.py notebookllm/mcp/server.py notebookllm/mcp/session.py
touch notebookllm/utils/__init__.py notebookllm/utils/detect.py notebookllm/utils/validation.py
touch tests/__init__.py
```

- [ ] **Step 2: Update pyproject.toml**

Replace `pyproject.toml` with:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "notebookllm"
version = "3.0.0"
description = "Convert and optimize Jupyter notebooks for LLMs"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "Yasir Raza", email = "yasir@example.com"},
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = [
    "nbformat>=5.9",
]

[project.optional-dependencies]
cli = [
    "click>=8.1",
    "rich>=13.0",
]
mcp = [
    "mcp[cli]>=1.8.1",
]
execute = [
    "jupyter_client>=8.0",
]
all = [
    "notebookllm[cli,mcp,execute]",
]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1",
]

[project.scripts]
notebookllm = "notebookllm.cli.commands:cli"
notebookllm-server = "notebookllm.mcp.server:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["notebookllm*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 3: Update notebookllm/__init__.py**

```python
"""notebookllm — Convert and optimize Jupyter notebooks for LLMs."""

__version__ = "3.0.0"
```

- [ ] **Step 4: Verify structure**

Run:
```bash
find notebookllm -name "*.py" | sort
```

Expected: All Python files exist.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: scaffold package structure for notebookllm v3.0"
```

---

## Task 2: Core Data Model

**Files:**
- Modify: `notebookllm/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
"""Tests for notebookllm.models — NotebookDocument, Cell, CellType, OutputMode, CellOutput."""
import pytest
from notebookllm.models import (
    Cell, CellType, CellOutput, NotebookDocument, OutputMode
)


class TestCellType:
    def test_enum_values(self):
        assert CellType.CODE.value == "code"
        assert CellType.MARKDOWN.value == "markdown"
        assert CellType.RAW.value == "raw"

    def test_from_string(self):
        assert CellType("code") == CellType.CODE
        assert CellType("markdown") == CellType.MARKDOWN


class TestOutputMode:
    def test_enum_values(self):
        assert OutputMode.MINIMAL.value == "minimal"
        assert OutputMode.STANDARD.value == "standard"
        assert OutputMode.FULL.value == "full"


class TestCellOutput:
    def test_stream_output(self):
        out = CellOutput(output_type="stream", content="hello world", name="stdout")
        assert out.output_type == "stream"
        assert out.content == "hello world"
        assert out.name == "stdout"

    def test_execute_result(self):
        out = CellOutput(output_type="execute_result", content={"text/plain": "42"})
        assert out.output_type == "execute_result"
        assert out.name is None

    def test_error_output(self):
        out = CellOutput(output_type="error", content="Traceback...")
        assert out.output_type == "error"


class TestCell:
    def test_code_cell(self):
        cell = Cell(cell_type=CellType.CODE, source="print('hello')")
        assert cell.cell_type == CellType.CODE
        assert cell.source == "print('hello')"
        assert cell.execution_count is None
        assert cell.outputs == []
        assert cell.metadata == {}
        assert cell.cell_id is None

    def test_cell_with_outputs(self):
        outputs = [CellOutput(output_type="stream", content="hello", name="stdout")]
        cell = Cell(cell_type=CellType.CODE, source="print('hello')", outputs=outputs)
        assert len(cell.outputs) == 1
        assert cell.outputs[0].content == "hello"

    def test_markdown_cell(self):
        cell = Cell(cell_type=CellType.MARKDOWN, source="# Title")
        assert cell.cell_type == CellType.MARKDOWN


class TestNotebookDocument:
    def test_empty_notebook(self):
        doc = NotebookDocument()
        assert doc.cells == []
        assert doc.metadata == {}
        assert doc.language == "python"
        assert doc.source_format is None

    def test_add_cell(self):
        doc = NotebookDocument()
        cell = Cell(cell_type=CellType.CODE, source="x = 1")
        doc.add_cell(cell)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "x = 1"

    def test_add_cell_at_position(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"), position=0)
        assert len(doc.cells) == 3
        assert doc.cells[0].source == "# Title"
        assert doc.cells[1].source == "a"
        assert doc.cells[2].source == "b"

    def test_get_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        cell = doc.get_cell(0)
        assert cell.source == "x = 1"

    def test_get_cell_out_of_range(self):
        doc = NotebookDocument()
        with pytest.raises(IndexError):
            doc.get_cell(0)

    def test_edit_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.edit_cell(0, source="x = 2")
        assert doc.cells[0].source == "x = 2"

    def test_edit_cell_change_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="# comment"))
        doc.edit_cell(0, source="# Title", cell_type=CellType.MARKDOWN)
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[0].source == "# Title"

    def test_delete_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.delete_cell(0)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "b"

    def test_delete_cell_out_of_range(self):
        doc = NotebookDocument()
        with pytest.raises(IndexError):
            doc.delete_cell(0)

    def test_move_cell(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="a"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="b"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="c"))
        doc.move_cell(0, 2)
        assert doc.cells[0].source == "b"
        assert doc.cells[1].source == "c"
        assert doc.cells[2].source == "a"

    def test_filter_cells_by_type(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        code_cells = doc.filter_cells(cell_type=CellType.CODE)
        assert len(code_cells) == 2

    def test_filter_cells_by_query(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import numpy"))
        results = doc.filter_cells(query="pandas")
        assert len(results) == 1
        assert results[0].source == "import pandas"

    def test_search(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas as pd"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import numpy as np"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="Data analysis with pandas"))
        results = doc.search("pandas")
        assert len(results) == 2
        indices = [r[0] for r in results]
        assert 0 in indices
        assert 2 in indices

    def test_search_case_insensitive(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import Pandas"))
        results = doc.search("pandas")
        assert len(results) == 1

    def test_search_with_cell_type_filter(self):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="import pandas"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="pandas documentation"))
        results = doc.search("pandas", cell_type=CellType.MARKDOWN)
        assert len(results) == 1
        assert results[0][1].cell_type == CellType.MARKDOWN
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_models.py -v 2>&1 | head -30
```

Expected: FAIL — `ModuleNotFoundError: No module named 'notebookllm.models'` (file is empty)

- [ ] **Step 3: Write the data model**

Write `notebookllm/models.py`:

```python
"""Core data models for notebookllm — universal notebook representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass


class CellType(Enum):
    """Type of notebook cell."""

    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"


class OutputMode(Enum):
    """LLM output verbosity mode."""

    MINIMAL = "minimal"  # Cell markers + source only
    STANDARD = "standard"  # Cell markers + source + metadata (type, exec count)
    FULL = "full"  # Cell markers + source + metadata + outputs


@dataclass
class CellOutput:
    """Represents output from a cell execution."""

    output_type: str  # "stream", "execute_result", "display_data", "error"
    content: str | dict  # Text for streams, data dict for display
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
    source_format: str | None = None

    @classmethod
    def from_file(cls, filepath: str | Path) -> NotebookDocument:
        """Load a notebook from file. Auto-detects format."""
        from notebookllm.loaders import load_file

        return load_file(filepath)

    def to_file(self, filepath: str | Path, fmt: str | None = None) -> None:
        """Save notebook to file. Auto-detects format from extension or uses fmt."""
        from notebookllm.loaders import dump_file

        dump_file(self, filepath, fmt=fmt)

    def to_text(self, mode: OutputMode = OutputMode.MINIMAL) -> str:
        """Convert to LLM-optimized text."""
        from notebookllm.converters.llm_optimizer import LLMOptimizer

        optimizer = LLMOptimizer(mode=mode)
        return optimizer.optimize(self)

    @classmethod
    def from_text(cls, text: str, source_format: str | None = None) -> NotebookDocument:
        """Parse text content into NotebookDocument.

        If source_format is None, attempts auto-detection by content sniffing.
        """
        from notebookllm.loaders import loads_text

        return loads_text(text, source_format=source_format)

    def filter_cells(
        self, cell_type: CellType | None = None, query: str | None = None
    ) -> list[Cell]:
        """Filter cells by type and/or content query."""
        results = self.cells
        if cell_type is not None:
            results = [c for c in results if c.cell_type == cell_type]
        if query is not None:
            q = query.lower()
            results = [c for c in results if q in c.source.lower()]
        return results

    def get_cell(self, index: int) -> Cell:
        """Get cell by index. Raises IndexError if out of range."""
        if index < 0 or index >= len(self.cells):
            raise IndexError(f"Cell index {index} out of range (0-{len(self.cells) - 1})")
        return self.cells[index]

    def add_cell(self, cell: Cell, position: int | None = None) -> None:
        """Add a cell at the given position, or append if None."""
        if position is None:
            self.cells.append(cell)
        else:
            if position < 0 or position > len(self.cells):
                raise IndexError(f"Position {position} out of range (0-{len(self.cells)})")
            self.cells.insert(position, cell)

    def edit_cell(self, index: int, source: str, cell_type: CellType | None = None) -> None:
        """Edit a cell's source and optionally change its type."""
        cell = self.get_cell(index)
        cell.source = source
        if cell_type is not None:
            cell.cell_type = cell_type

    def delete_cell(self, index: int) -> None:
        """Delete a cell by index."""
        self.get_cell(index)  # Validate index exists
        self.cells.pop(index)

    def move_cell(self, from_index: int, to_index: int) -> None:
        """Move a cell from one position to another."""
        cell = self.get_cell(from_index)
        self.cells.pop(from_index)
        if to_index > len(self.cells):
            to_index = len(self.cells)
        self.cells.insert(to_index, cell)

    def search(self, query: str, cell_type: CellType | None = None) -> list[tuple[int, Cell]]:
        """Search cells by content (case-insensitive substring match).

        Returns list of (index, cell) tuples for cells containing query.
        """
        q = query.lower()
        results = []
        for i, cell in enumerate(self.cells):
            if cell_type is not None and cell.cell_type != cell_type:
                continue
            if q in cell.source.lower():
                results.append((i, cell))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_models.py -v
```

Expected: All 22 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/models.py tests/test_models.py
git commit -m "feat: add core data model (NotebookDocument, Cell, CellType, OutputMode)"
```

---

## Task 3: Base Loader/Dumper Classes

**Files:**
- Modify: `notebookllm/loaders/base.py`
- Create: `tests/test_loaders/__init__.py`
- Create: `tests/test_loaders/test_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_loaders/__init__.py` (empty).
Create `tests/test_loaders/test_base.py`:

```python
"""Tests for notebookllm.loaders.base — abstract base classes."""
import pytest
from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import NotebookDocument, Cell, CellType


class ConcreteLoader(BaseLoader):
    """Concrete loader for testing abstract base."""

    def load(self, source):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        return doc

    def loads(self, content):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source=content))
        return doc


class ConcreteDumper(BaseDumper):
    """Concrete dumper for testing abstract base."""

    def dump(self, doc, filepath=None):
        lines = []
        for cell in doc.cells:
            lines.append(f"# %% [{cell.cell_type.value}]")
            lines.append(cell.source)
        result = "\n".join(lines)
        if filepath:
            filepath.write_text(result)
        return result


class TestBaseLoader:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseLoader()

    def test_concrete_loader_load(self):
        loader = ConcreteLoader()
        doc = loader.load("fake.ipynb")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 1

    def test_concrete_loader_loads(self):
        loader = ConcreteLoader()
        doc = loader.loads("print('hello')")
        assert doc.cells[0].source == "print('hello')"


class TestBaseDumper:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseDumper()

    def test_concrete_dumper_dump_to_string(self):
        dumper = ConcreteDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "# %% [code]" in result
        assert "x = 1" in result

    def test_concrete_dumper_dump_to_file(self, tmp_path):
        dumper = ConcreteDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.py"
        result = dumper.dump(doc, filepath=filepath)
        assert filepath.read_text() == result
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_base.py -v 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError` or empty base.py

- [ ] **Step 3: Write the base classes**

Write `notebookllm/loaders/base.py`:

```python
"""Abstract base classes for format loaders and dumpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from notebookllm.models import NotebookDocument


class BaseLoader(ABC):
    """Abstract base class for format loaders."""

    @abstractmethod
    def load(self, source: str | Path) -> NotebookDocument:
        """Load a notebook from a file path."""
        ...

    @abstractmethod
    def loads(self, content: str) -> NotebookDocument:
        """Load a notebook from a string."""
        ...


class BaseDumper(ABC):
    """Abstract base class for format dumpers."""

    @abstractmethod
    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        """Dump a notebook to string, optionally writing to file."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_base.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/loaders/base.py tests/test_loaders/
git commit -m "feat: add abstract BaseLoader and BaseDumper classes"
```

---

## Task 4: Format Detection

**Files:**
- Modify: `notebookllm/utils/detect.py`
- Create: `tests/test_loaders/test_detect.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_loaders/test_detect.py`:

```python
"""Tests for notebookllm.utils.detect — format detection."""
import pytest
from pathlib import Path
from notebookllm.utils.detect import detect_format, detect_text_format


class TestDetectFormat:
    def test_ipynb_extension(self, tmp_path):
        f = tmp_path / "notebook.ipynb"
        f.write_text("{}")
        assert detect_format(f) == "ipynb"

    def test_qmd_extension(self, tmp_path):
        f = tmp_path / "notebook.qmd"
        f.write_text("---\ntitle: Test\n---")
        assert detect_format(f) == "quarto"

    def test_md_extension(self, tmp_path):
        f = tmp_path / "notebook.md"
        f.write_text("# Title")
        assert detect_format(f) == "markdown"

    def test_rmd_extension(self, tmp_path):
        f = tmp_path / "notebook.rmd"
        f.write_text("# Title")
        assert detect_format(f) == "markdown"

    def test_py_percent_format(self, tmp_path):
        f = tmp_path / "notebook.py"
        f.write_text("# %% [code]\nx = 1\n")
        assert detect_format(f) == "percent"

    def test_py_marimo_format(self, tmp_path):
        f = tmp_path / "notebook.py"
        f.write_text("import marimo\n\n@app.cell\ndef f():\n    return\n")
        assert detect_format(f) == "marimo"

    def test_py_default_to_percent(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("x = 1\nprint(x)\n")
        assert detect_format(f) == "percent"

    def test_unknown_extension_raises(self, tmp_path):
        f = tmp_path / "notebook.xyz"
        f.write_text("content")
        with pytest.raises(ValueError, match="Cannot detect format"):
            detect_format(f)


class TestDetectTextFormat:
    def test_percent_markers(self):
        text = "# %% [code]\nx = 1\n# %% [markdown]\n# Title"
        assert detect_text_format(text) == "percent"

    def test_marimo_markers(self):
        text = "import marimo\n\n@app.cell\ndef f():\n    return\n"
        assert detect_text_format(text) == "marimo"

    def test_quarto_markers(self):
        text = "---\ntitle: Test\n---\n\n```{python}\nx = 1\n```\n"
        assert detect_text_format(text) == "quarto"

    def test_markdown_code_blocks(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        assert detect_text_format(text) == "markdown"

    def test_plain_python_fallback(self):
        text = "x = 1\nprint(x)\n"
        assert detect_text_format(text) == "percent"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_detect.py -v 2>&1 | head -20
```

Expected: FAIL — empty detect.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/utils/detect.py`:

```python
"""Format detection for notebooks — extension and content sniffing."""
from __future__ import annotations

from pathlib import Path


def detect_format(filepath: Path, content: str | None = None) -> str:
    """Detect notebook format from file extension and optionally content sniffing.

    Returns: "ipynb", "quarto", "markdown", "marimo", or "percent"
    """
    filepath = Path(filepath)
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
        return "percent"
    else:
        raise ValueError(f"Cannot detect format for {filepath}")


def detect_text_format(content: str) -> str:
    """Detect format from text content alone (content sniffing).

    Returns: "percent", "marimo", "quarto", "markdown"
    """
    lines = content.splitlines()

    # Check for percent format markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# %%"):
            return "percent"

    # Check for marimo markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import marimo") or stripped.startswith("@app.cell"):
            return "marimo"

    # Check for quarto markers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```{python}"):
            return "quarto"

    # Check for markdown code blocks
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```python"):
            return "markdown"

    # Fallback: treat as percent format
    return "percent"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_detect.py -v
```

Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/utils/detect.py tests/test_loaders/test_detect.py
git commit -m "feat: add format detection (extension + content sniffing)"
```

---

## Task 5: .ipynb Loader/Dumper

**Files:**
- Modify: `notebookllm/loaders/ipynb.py`
- Create: `tests/test_loaders/test_ipynb.py`
- Create: `tests/fixtures/sample.ipynb`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample.ipynb`:

```json
{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "id": "cell-001",
   "metadata": {"tags": ["setup"]},
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "text": "Hello, World!\n"
    }
   ],
   "source": ["import pandas as pd\n", "df = pd.read_csv('data.csv')\n", "df.head()"]
  },
  {
   "cell_type": "markdown",
   "id": "cell-002",
   "metadata": {},
   "source": ["# Analysis\n", "\n", "This notebook analyzes data."]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "cell-003",
   "metadata": {},
   "outputs": [],
   "source": ["# Empty outputs cell"]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.11.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_loaders/test_ipynb.py`:

```python
"""Tests for notebookllm.loaders.ipynb — .ipynb loader/dumper."""
import json
import pytest
from pathlib import Path
from notebookllm.loaders.ipynb import IpynbLoader, IpynbDumper
from notebookllm.models import NotebookDocument, Cell, CellType, CellOutput


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestIpynbLoader:
    def test_load_sample(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 3
        assert doc.source_format == "ipynb"

    def test_load_preserves_cell_types(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[2].cell_type == CellType.CODE

    def test_load_preserves_execution_count(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].execution_count == 1
        assert doc.cells[2].execution_count is None

    def test_load_preserves_outputs(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert len(doc.cells[0].outputs) == 1
        assert doc.cells[0].outputs[0].output_type == "stream"
        assert doc.cells[0].outputs[0].name == "stdout"

    def test_load_preserves_metadata(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].metadata.get("tags") == ["setup"]
        assert doc.kernel_name == "python3"

    def test_load_preserves_cell_id(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_id == "cell-001"

    def test_load_joins_source_list(self):
        """ipynb source can be a list of strings — should be joined."""
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        # sample.ipynb has list-style source
        assert "import pandas" in doc.cells[0].source
        assert "df.head()" in doc.cells[0].source

    def test_loads_from_string(self):
        loader = IpynbLoader()
        content = json.dumps({
            "cells": [{"cell_type": "code", "id": "c1", "source": ["x = 1"], "metadata": {}, "outputs": []}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        })
        doc = loader.loads(content)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "x = 1"

    def test_load_empty_notebook(self):
        loader = IpynbLoader()
        content = json.dumps({
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        })
        doc = loader.loads(content)
        assert len(doc.cells) == 0


class TestIpynbDumper:
    def test_dump_to_string(self):
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        data = json.loads(result)
        assert data["nbformat"] == 4
        assert len(data["cells"]) == 1
        assert data["cells"][0]["cell_type"] == "code"

    def test_dump_to_file(self, tmp_path):
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.ipynb"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert len(data["cells"]) == 1

    def test_dump_preserves_metadata(self):
        dumper = IpynbDumper()
        doc = NotebookDocument(metadata={"kernelspec": {"name": "python3"}})
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        data = json.loads(result)
        assert data["metadata"]["kernelspec"]["name"] == "python3"

    def test_roundtrip_preserves_cells(self):
        loader = IpynbLoader()
        dumper = IpynbDumper()
        doc = loader.load(FIXTURES / "sample.ipynb")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source == c2.source
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_ipynb.py -v 2>&1 | head -20
```

Expected: FAIL — empty ipynb.py

- [ ] **Step 4: Write the implementation**

Write `notebookllm/loaders/ipynb.py`:

```python
"""ipynb loader/dumper — Jupyter notebook format."""
from __future__ import annotations

import json
from pathlib import Path

import nbformat

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument


class IpynbLoader(BaseLoader):
    """Load .ipynb files using nbformat."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        nb = nbformat.read(str(source), as_version=4)
        return self._convert(nb)

    def loads(self, content: str) -> NotebookDocument:
        nb = nbformat.reads(content, as_version=4)
        return self._convert(nb)

    def _convert(self, nb: nbformat.NotebookNode) -> NotebookDocument:
        cells = []
        for nb_cell in nb.cells:
            source = nb_cell.source
            if isinstance(source, list):
                source = "".join(source)

            outputs = []
            if nb_cell.cell_type == "code" and hasattr(nb_cell, "outputs"):
                for out in nb_cell.outputs:
                    outputs.append(self._parse_output(out))

            metadata = dict(nb_cell.metadata) if nb_cell.metadata else {}
            cell_id = getattr(nb_cell, "id", None)

            cells.append(Cell(
                cell_type=CellType(nb_cell.cell_type),
                source=source,
                execution_count=getattr(nb_cell, "execution_count", None),
                outputs=outputs,
                metadata=metadata,
                cell_id=cell_id,
            ))

        nb_metadata = dict(nb.metadata) if nb.metadata else {}
        kernel_name = None
        if "kernelspec" in nb_metadata:
            kernel_name = nb_metadata["kernelspec"].get("name")

        return NotebookDocument(
            cells=cells,
            metadata=nb_metadata,
            kernel_name=kernel_name,
            source_format="ipynb",
        )

    def _parse_output(self, out: dict) -> CellOutput:
        output_type = out.get("output_type", "unknown")
        if output_type == "stream":
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            return CellOutput(output_type=output_type, content=text, name=out.get("name"))
        elif output_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            content = data.get("text/plain", str(data))
            if isinstance(content, list):
                content = "".join(content)
            return CellOutput(output_type=output_type, content=content)
        elif output_type == "error":
            traceback = out.get("traceback", [])
            content = "\n".join(traceback) if isinstance(traceback, list) else str(traceback)
            return CellOutput(output_type=output_type, content=content)
        else:
            return CellOutput(output_type=output_type, content=str(out))


class IpynbDumper(BaseDumper):
    """Dump to .ipynb format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        nb = nbformat.v4.new_notebook()
        nb.metadata = doc.metadata.copy()
        if doc.kernel_name:
            nb.metadata.setdefault("kernelspec", {})["name"] = doc.kernel_name

        nb.cells = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                nb_cell = nbformat.v4.new_code_cell(source=cell.source)
                nb_cell.execution_count = cell.execution_count
                nb_cell.outputs = [self._dump_output(o) for o in cell.outputs]
            elif cell.cell_type == CellType.MARKDOWN:
                nb_cell = nbformat.v4.new_markdown_cell(source=cell.source)
            elif cell.cell_type == CellType.RAW:
                nb_cell = nbformat.v4.new_raw_cell(source=cell.source)
            else:
                continue

            nb_cell.metadata = cell.metadata.copy()
            if cell.cell_id:
                nb_cell.id = cell.cell_id
            nb.cells.append(nb_cell)

        content = nbformat.writes(nb)
        if filepath:
            filepath.write_text(content, encoding="utf-8")
        return content

    def _dump_output(self, out: CellOutput) -> dict:
        if out.output_type == "stream":
            return {"output_type": "stream", "name": out.name or "stdout", "text": out.content}
        elif out.output_type in ("execute_result", "display_data"):
            data = {}
            if isinstance(out.content, str):
                data["text/plain"] = out.content
            else:
                data = out.content
            return {"output_type": out.output_type, "data": data}
        elif out.output_type == "error":
            return {"output_type": "error", "traceback": [out.content]}
        return {"output_type": out.output_type, "data": str(out.content)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_ipynb.py -v
```

Expected: All 13 tests PASS

- [ ] **Step 6: Commit**

```bash
git add notebookllm/loaders/ipynb.py tests/test_loaders/test_ipynb.py tests/fixtures/sample.ipynb
git commit -m "feat: add ipynb loader/dumper with nbformat"
```

---

## Task 6: Percent Format Loader/Dumper

**Files:**
- Modify: `notebookllm/loaders/percent.py`
- Create: `tests/fixtures/sample_percent.py`
- Create: `tests/test_loaders/test_percent.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_percent.py`:

```python
# %% [code]
import pandas as pd

df = pd.read_csv("data.csv")
df.head()

# %% [markdown]
# ## Analysis

# This is a **percent format** notebook.

# %% [code]
# Cell with no output
x = 42
print(x)
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_loaders/test_percent.py`:

```python
"""Tests for notebookllm.loaders.percent — percent format (.py with # %% markers)."""
import pytest
from pathlib import Path
from notebookllm.loaders.percent import PercentLoader, PercentDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestPercentLoader:
    def test_load_sample(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 3
        assert doc.source_format == "percent"

    def test_load_preserves_cell_types(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[2].cell_type == CellType.CODE

    def test_load_preserves_source(self):
        loader = PercentLoader()
        doc = loader.load(FIXTURES / "sample_percent.py")
        assert "import pandas" in doc.cells[0].source
        assert "df.head()" in doc.cells[0].source

    def test_loads_from_string(self):
        loader = PercentLoader()
        text = "# %% [code]\nx = 1\n\n# %% [markdown]\n# Title\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN

    def test_load_no_markers(self):
        """Files without markers are treated as a single code cell."""
        loader = PercentLoader()
        text = "x = 1\nprint(x)\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE
        assert "x = 1" in doc.cells[0].source

    def test_load_empty_file(self):
        loader = PercentLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_load_consecutive_markers(self):
        loader = PercentLoader()
        text = "# %% [code]\n\n# %% [code]\nx = 1\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2

    def test_load_preserves_indentation(self):
        """percent loader should NOT use textwrap.dedent — preserve indentation."""
        loader = PercentLoader()
        text = "# %% [code]\nif True:\n    x = 1\n    print(x)\n"
        doc = loader.loads(text)
        assert "    x = 1" in doc.cells[0].source
        assert "    print(x)" in doc.cells[0].source


class TestPercentDumper:
    def test_dump_to_string(self):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "# %% [code]" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.py"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()
        assert "# %% [code]" in filepath.read_text()

    def test_dump_multiple_cells(self):
        dumper = PercentDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc.add_cell(Cell(cell_type=CellType.MARKDOWN, source="# Title"))
        doc.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        result = dumper.dump(doc)
        assert result.count("# %%") == 3

    def test_roundtrip_preserves_content(self):
        loader = PercentLoader()
        dumper = PercentDumper()
        doc = loader.load(FIXTURES / "sample_percent.py")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source.strip() == c2.source.strip()
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_percent.py -v 2>&1 | head -20
```

Expected: FAIL — empty percent.py

- [ ] **Step 4: Write the implementation**

Write `notebookllm/loaders/percent.py`:

```python
"""Percent format loader/dumper — .py files with # %% markers."""
from __future__ import annotations

import re
from pathlib import Path

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellType, NotebookDocument

# Matches: # %% [code], # %% [markdown], # %% [raw], # %%
CELL_MARKER = re.compile(r"^#\s*%%\s*(?:\[(\w+)\])?\s*$")


class PercentLoader(BaseLoader):
    """Load percent format .py files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []
        current_type = CellType.CODE
        current_lines: list[str] = []
        has_markers = False

        for line in content.splitlines(keepends=True):
            match = CELL_MARKER.match(line.rstrip())
            if match:
                has_markers = True
                # Save previous cell
                if current_lines or cells:
                    source = "".join(current_lines).rstrip("\n")
                    cells.append(Cell(cell_type=current_type, source=source))
                # Start new cell
                cell_type_str = match.group(1) or "code"
                try:
                    current_type = CellType(cell_type_str)
                except ValueError:
                    current_type = CellType.CODE
                current_lines = []
            else:
                current_lines.append(line)

        # Don't forget last cell
        if current_lines:
            source = "".join(current_lines).rstrip("\n")
            cells.append(Cell(cell_type=current_type, source=source))

        # If no markers found, treat entire content as single code cell
        if not has_markers and content.strip():
            cells = [Cell(cell_type=CellType.CODE, source=content.rstrip("\n"))]

        return NotebookDocument(cells=cells, source_format="percent")


class PercentDumper(BaseDumper):
    """Dump to percent format .py files."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        parts = []
        for cell in doc.cells:
            marker = f"# %% [{cell.cell_type.value}]"
            parts.append(f"{marker}\n{cell.source}")

        result = "\n\n".join(parts)
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_percent.py -v
```

Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
git add notebookllm/loaders/percent.py tests/test_loaders/test_percent.py tests/fixtures/sample_percent.py
git commit -m "feat: add percent format loader/dumper with regex state machine"
```

---

## Task 7: Marimo Format Loader

**Files:**
- Modify: `notebookllm/loaders/marimo.py`
- Create: `tests/fixtures/sample_marimo.py`
- Create: `tests/test_loaders/test_marimo.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_marimo.py`:

```python
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def import_data():
    import pandas as pd
    df = pd.read_csv("data.csv")
    return pd, df


@app.cell
def analyze(df):
    result = df.describe()
    return result,


@app.cell
def display(result):
    return result,
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_loaders/test_marimo.py`:

```python
"""Tests for notebookllm.loaders.marimo — marimo format (.py with @app.cell)."""
import pytest
from pathlib import Path
from notebookllm.loaders.marimo import MarimoLoader
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestMarimoLoader:
    def test_load_sample(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert isinstance(doc, NotebookDocument)
        assert doc.source_format == "marimo"

    def test_load_extracts_cells(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert len(doc.cells) == 3

    def test_load_cell_types_are_code(self):
        """Marimo cells are always code cells."""
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        for cell in doc.cells:
            assert cell.cell_type == CellType.CODE

    def test_load_preserves_cell_content(self):
        loader = MarimoLoader()
        doc = loader.load(FIXTURES / "sample_marimo.py")
        assert "import pandas" in doc.cells[0].source
        assert "df.describe()" in doc.cells[1].source

    def test_loads_from_string(self):
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "app = marimo.App()\n"
            "\n"
            "@app.cell\n"
            "def f():\n"
            "    x = 1\n"
            "    return x,\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert "x = 1" in doc.cells[0].source

    def test_load_empty_marimo_file(self):
        loader = MarimoLoader()
        text = "import marimo\napp = marimo.App()\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 0

    def test_load_skips_non_cell_functions(self):
        loader = MarimoLoader()
        text = (
            "import marimo\n"
            "app = marimo.App()\n"
            "\n"
            "def helper():\n"
            "    return 42\n"
            "\n"
            "@app.cell\n"
            "def main():\n"
            "    return helper(),\n"
        )
        doc = loader.loads(text)
        assert len(doc.cells) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_marimo.py -v 2>&1 | head -20
```

Expected: FAIL — empty marimo.py

- [ ] **Step 4: Write the implementation**

Write `notebookllm/loaders/marimo.py`:

```python
"""Marimo format loader — .py files with @app.cell decorators."""
from __future__ import annotations

import ast
from pathlib import Path

from notebookllm.loaders.base import BaseLoader
from notebookllm.models import Cell, CellType, NotebookDocument


class MarimoLoader(BaseLoader):
    """Load marimo format .py files using AST parsing."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If AST fails, return empty
            return NotebookDocument(cells=[], source_format="marimo")

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not self._has_cell_decorator(node):
                continue
            # Extract cell body from AST
            cell_source = self._extract_cell_body(content, node)
            cells.append(Cell(cell_type=CellType.CODE, source=cell_source))

        return NotebookDocument(cells=cells, source_format="marimo")

    def _has_cell_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if function has @app.cell or @app.function decorator."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "cell":
                return True
            if isinstance(dec, ast.Name) and dec.id == "cell":
                return True
        return False

    def _extract_cell_body(self, content: str, node: ast.FunctionDef) -> str:
        """Extract the function body as source code, stripping the decorator and def line."""
        lines = content.splitlines(keepends=True)
        # Find the start of the function body (first line after def:)
        body_start = node.body[0].lineno - 1
        body_end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else body_start + 1

        body_lines = lines[body_start:body_end]
        source = "".join(body_lines)

        # Strip common indentation (the body is indented under def)
        import textwrap
        source = textwrap.dedent(source)

        # Remove trailing return statement if it's just returning variables
        # (marimo convention: return var1, var2,)
        source = source.rstrip()

        return source
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_marimo.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add notebookllm/loaders/marimo.py tests/test_loaders/test_marimo.py tests/fixtures/sample_marimo.py
git commit -m "feat: add marimo format loader with AST parsing"
```

---

## Task 8: Quarto Format Loader/Dumper

**Files:**
- Modify: `notebookllm/loaders/quarto.py`
- Create: `tests/fixtures/sample_quarto.qmd`
- Create: `tests/test_loaders/test_quarto.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_quarto.qmd`:

```markdown
---
title: "Analysis"
author: "Yasir"
---

## Setup

```{python}
import pandas as pd
df = pd.read_csv("data.csv")
```

## Results

```{python}
df.head()
```

Some markdown text between code cells.
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_loaders/test_quarto.py`:

```python
"""Tests for notebookllm.loaders.quarto — quarto format (.qmd)."""
import pytest
from pathlib import Path
from notebookllm.loaders.quarto import QuartoLoader, QuartoDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestQuartoLoader:
    def test_load_sample(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) >= 2
        assert doc.source_format == "quarto"

    def test_load_preserves_cell_types(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        types = [c.cell_type for c in doc.cells]
        assert CellType.CODE in types
        assert CellType.MARKDOWN in types

    def test_load_preserves_code_content(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        assert any("import pandas" in c.source for c in code_cells)

    def test_load_preserves_metadata(self):
        loader = QuartoLoader()
        doc = loader.load(FIXTURES / "sample_quarto.qmd")
        assert "title" in doc.metadata

    def test_loads_from_string(self):
        loader = QuartoLoader()
        text = '---\ntitle: "Test"\n---\n\n```{python}\nx = 1\n```\n'
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.CODE

    def test_load_no_frontmatter(self):
        loader = QuartoLoader()
        text = "```{python}\nx = 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1


class TestQuartoDumper:
    def test_dump_to_string(self):
        dumper = QuartoDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "```{python}" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = QuartoDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.qmd"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()

    def test_dump_includes_frontmatter(self):
        dumper = QuartoDumper()
        doc = NotebookDocument(metadata={"title": "My Analysis"})
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "---" in result
        assert "title:" in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_quarto.py -v 2>&1 | head -20
```

Expected: FAIL — empty quarto.py

- [ ] **Step 4: Write the implementation**

Write `notebookllm/loaders/quarto.py`:

```python
"""Quarto format loader/dumper — .qmd files."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellType, NotebookDocument

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
CODE_CHUNK_RE = re.compile(r"```\{(\w+)\}\s*\n(.*?)```", re.DOTALL)


class QuartoLoader(BaseLoader):
    """Load quarto .qmd files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []
        metadata = {}

        # Parse YAML frontmatter
        fm_match = FRONTMATTER_RE.match(content)
        if fm_match:
            try:
                metadata = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                metadata = {}
            content = content[fm_match.end():]

        # Find all code chunks and markdown between them
        last_end = 0
        for match in CODE_CHUNK_RE.finditer(content):
            # Markdown before this code chunk
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            # The code chunk
            lang = match.group(1)
            code = match.group(2).strip()
            if lang in ("python", "r", "julia"):
                cells.append(Cell(cell_type=CellType.CODE, source=code))
            else:
                cells.append(Cell(cell_type=CellType.RAW, source=code))

            last_end = match.end()

        # Trailing markdown
        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, metadata=metadata, source_format="quarto")


class QuartoDumper(BaseDumper):
    """Dump to quarto .qmd format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        parts = []

        # YAML frontmatter
        if doc.metadata:
            parts.append("---")
            parts.append(yaml.dump(doc.metadata, default_flow_style=False).strip())
            parts.append("---")
            parts.append("")

        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                parts.append("```{python}")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                parts.append("```{raw}")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_quarto.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add notebookllm/loaders/quarto.py tests/test_loaders/test_quarto.py tests/fixtures/sample_quarto.qmd
git commit -m "feat: add quarto format loader/dumper"
```

---

## Task 9: Markdown Format Loader/Dumper

**Files:**
- Modify: `notebookllm/loaders/markdown.py`
- Create: `tests/fixtures/sample_markdown.md`
- Create: `tests/test_loaders/test_markdown.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_markdown.md`:

```markdown
# Data Analysis

This is a markdown notebook.

```python
import pandas as pd
df = pd.read_csv("data.csv")
```

## Results

```python
df.head()
```
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_loaders/test_markdown.py`:

```python
"""Tests for notebookllm.loaders.markdown — markdown format (.md with ```python blocks)."""
import pytest
from pathlib import Path
from notebookllm.loaders.markdown import MarkdownLoader, MarkdownDumper
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestMarkdownLoader:
    def test_load_sample(self):
        loader = MarkdownLoader()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) >= 2
        assert doc.source_format == "markdown"

    def test_load_preserves_cell_types(self):
        loader = MarkdownLoader()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        types = [c.cell_type for c in doc.cells]
        assert CellType.CODE in types
        assert CellType.MARKDOWN in types

    def test_loads_from_string(self):
        loader = MarkdownLoader()
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE

    def test_load_no_code_blocks(self):
        loader = MarkdownLoader()
        text = "# Just markdown\n\nNo code here.\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 1
        assert doc.cells[0].cell_type == CellType.MARKDOWN

    def test_load_empty_file(self):
        loader = MarkdownLoader()
        doc = loader.loads("")
        assert len(doc.cells) == 0

    def test_load_multiple_code_blocks(self):
        loader = MarkdownLoader()
        text = "```python\na = 1\n```\n\n```python\nb = 2\n```\n"
        doc = loader.loads(text)
        assert len(doc.cells) == 2
        assert all(c.cell_type == CellType.CODE for c in doc.cells)


class TestMarkdownDumper:
    def test_dump_to_string(self):
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "```python" in result
        assert "x = 1" in result

    def test_dump_to_file(self, tmp_path):
        dumper = MarkdownDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.md"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()

    def test_roundtrip_preserves_content(self):
        loader = MarkdownLoader()
        dumper = MarkdownDumper()
        doc = loader.load(FIXTURES / "sample_markdown.md")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_markdown.py -v 2>&1 | head -20
```

Expected: FAIL — empty markdown.py

- [ ] **Step 4: Write the implementation**

Write `notebookllm/loaders/markdown.py`:

```python
"""Markdown format loader/dumper — .md files with ```python blocks."""
from __future__ import annotations

import re
from pathlib import Path

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellType, NotebookDocument

CODE_BLOCK_RE = re.compile(r"```(\w+)\s*\n(.*?)```", re.DOTALL)


class MarkdownLoader(BaseLoader):
    """Load markdown files with embedded code blocks."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        cells = []
        last_end = 0

        for match in CODE_BLOCK_RE.finditer(content):
            # Markdown before this code block
            md_text = content[last_end:match.start()].strip()
            if md_text:
                cells.append(Cell(cell_type=CellType.MARKDOWN, source=md_text))

            # The code block
            lang = match.group(1)
            code = match.group(2).strip()
            if lang in ("python", "r", "julia", "javascript", "ts", "typescript"):
                cells.append(Cell(cell_type=CellType.CODE, source=code))
            else:
                cells.append(Cell(cell_type=CellType.RAW, source=code))

            last_end = match.end()

        # Trailing markdown
        trailing = content[last_end:].strip()
        if trailing:
            cells.append(Cell(cell_type=CellType.MARKDOWN, source=trailing))

        return NotebookDocument(cells=cells, source_format="markdown")


class MarkdownDumper(BaseDumper):
    """Dump to markdown format with embedded code blocks."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
        parts = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                parts.append("```python")
                parts.append(cell.source)
                parts.append("```")
            elif cell.cell_type == CellType.MARKDOWN:
                parts.append(cell.source)
            elif cell.cell_type == CellType.RAW:
                parts.append("```raw")
                parts.append(cell.source)
                parts.append("```")
            parts.append("")

        result = "\n".join(parts).rstrip() + "\n"
        if filepath:
            filepath.write_text(result, encoding="utf-8")
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_markdown.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add notebookllm/loaders/markdown.py tests/test_loaders/test_markdown.py tests/fixtures/sample_markdown.md
git commit -m "feat: add markdown format loader/dumper"
```

---

## Task 10: Format Auto-Loading Dispatch

**Files:**
- Modify: `notebookllm/loaders/__init__.py`
- Create: `tests/test_loaders/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_loaders/test_dispatch.py`:

```python
"""Tests for notebookllm.loaders — format auto-detection and dispatch."""
import pytest
from pathlib import Path
from notebookllm.loaders import load_file, dump_file, loads_text
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadFile:
    def test_load_ipynb(self):
        doc = load_file(FIXTURES / "sample.ipynb")
        assert doc.source_format == "ipynb"
        assert len(doc.cells) > 0

    def test_load_percent(self):
        doc = load_file(FIXTURES / "sample_percent.py")
        assert doc.source_format == "percent"
        assert len(doc.cells) > 0

    def test_load_marimo(self):
        doc = load_file(FIXTURES / "sample_marimo.py")
        assert doc.source_format == "marimo"
        assert len(doc.cells) > 0

    def test_load_quarto(self):
        doc = load_file(FIXTURES / "sample_quarto.qmd")
        assert doc.source_format == "quarto"
        assert len(doc.cells) > 0

    def test_load_markdown(self):
        doc = load_file(FIXTURES / "sample_markdown.md")
        assert doc.source_format == "markdown"
        assert len(doc.cells) > 0

    def test_load_unknown_extension(self, tmp_path):
        f = tmp_path / "unknown.xyz"
        f.write_text("content")
        with pytest.raises(ValueError):
            load_file(f)


class TestDumpFile:
    def test_dump_ipynb(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.ipynb"
        dump_file(doc, out)
        assert out.exists()

    def test_dump_percent(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.py"
        dump_file(doc, out)
        assert out.exists()
        assert "# %% [code]" in out.read_text()

    def test_dump_quarto(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.qmd"
        dump_file(doc, out)
        assert out.exists()
        assert "```{python}" in out.read_text()

    def test_dump_markdown(self, tmp_path):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        out = tmp_path / "out.md"
        dump_file(doc, out)
        assert out.exists()
        assert "```python" in out.read_text()


class TestLoadsText:
    def test_percent_format(self):
        text = "# %% [code]\nx = 1\n"
        doc = loads_text(text)
        assert doc.source_format == "percent"
        assert len(doc.cells) == 1

    def test_marimo_format(self):
        text = "import marimo\napp = marimo.App()\n\n@app.cell\ndef f():\n    x = 1\n    return x,\n"
        doc = loads_text(text)
        assert doc.source_format == "marimo"

    def test_quarto_format(self):
        text = "```{python}\nx = 1\n```\n"
        doc = loads_text(text)
        assert doc.source_format == "quarto"

    def test_markdown_format(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loads_text(text)
        assert doc.source_format == "markdown"

    def test_explicit_format(self):
        text = "# Title\n\n```python\nx = 1\n```\n"
        doc = loads_text(text, source_format="markdown")
        assert doc.source_format == "markdown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_dispatch.py -v 2>&1 | head -20
```

Expected: FAIL — empty loaders/__init__.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/loaders/__init__.py`:

```python
"""Format auto-detection and dispatch — the entry point for loading/dumping notebooks."""
from __future__ import annotations

from pathlib import Path

from notebookllm.utils.detect import detect_format, detect_text_format
from notebookllm.models import NotebookDocument


def load_file(filepath: str | Path) -> NotebookDocument:
    """Load a notebook from file. Auto-detects format from extension."""
    filepath = Path(filepath)
    fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbLoader
        return IpynbLoader().load(filepath)
    elif fmt == "percent":
        from notebookllm.loaders.percent import PercentLoader
        return PercentLoader().load(filepath)
    elif fmt == "marimo":
        from notebookllm.loaders.marimo import MarimoLoader
        return MarimoLoader().load(filepath)
    elif fmt == "quarto":
        from notebookllm.loaders.quarto import QuartoLoader
        return QuartoLoader().load(filepath)
    elif fmt == "markdown":
        from notebookllm.loaders.markdown import MarkdownLoader
        return MarkdownLoader().load(filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def dump_file(doc: NotebookDocument, filepath: str | Path, fmt: str | None = None) -> None:
    """Dump a notebook to file. Auto-detects format from extension or uses fmt."""
    filepath = Path(filepath)
    if fmt is None:
        fmt = detect_format(filepath)

    if fmt == "ipynb":
        from notebookllm.loaders.ipynb import IpynbDumper
        IpynbDumper().dump(doc, filepath)
    elif fmt == "percent":
        from notebookllm.loaders.percent import PercentDumper
        PercentDumper().dump(doc, filepath)
    elif fmt == "quarto":
        from notebookllm.loaders.quarto import QuartoDumper
        QuartoDumper().dump(doc, filepath)
    elif fmt == "markdown":
        from notebookllm.loaders.markdown import MarkdownDumper
        MarkdownDumper().dump(doc, filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def loads_text(text: str, source_format: str | None = None) -> NotebookDocument:
    """Load a notebook from text content. Auto-detects format if not specified."""
    if source_format is None:
        source_format = detect_text_format(text)

    if source_format == "percent":
        from notebookllm.loaders.percent import PercentLoader
        return PercentLoader().loads(text)
    elif source_format == "marimo":
        from notebookllm.loaders.marimo import MarimoLoader
        return MarimoLoader().loads(text)
    elif source_format == "quarto":
        from notebookllm.loaders.quarto import QuartoLoader
        return QuartoLoader().loads(text)
    elif source_format == "markdown":
        from notebookllm.loaders.markdown import MarkdownLoader
        return MarkdownLoader().loads(text)
    else:
        raise ValueError(f"Unsupported format: {source_format}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_loaders/test_dispatch.py -v
```

Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/loaders/__init__.py tests/test_loaders/test_dispatch.py
git commit -m "feat: add format auto-detection and dispatch (load_file, dump_file, loads_text)"
```

---

## Task 11: LLM Optimizer

**Files:**
- Modify: `notebookllm/converters/__init__.py`
- Modify: `notebookllm/converters/llm_optimizer.py`
- Create: `tests/test_converters/__init__.py`
- Create: `tests/test_converters/test_llm_optimizer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_converters/__init__.py` (empty).
Create `tests/test_converters/test_llm_optimizer.py`:

```python
"""Tests for notebookllm.converters.llm_optimizer — configurable output modes."""
import pytest
from notebookllm.converters.llm_optimizer import LLMOptimizer
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode


def _sample_doc():
    doc = NotebookDocument()
    doc.add_cell(Cell(
        cell_type=CellType.CODE,
        source="import pandas as pd\ndf = pd.read_csv('data.csv')",
        execution_count=1,
        outputs=[CellOutput(output_type="stream", content="    col1  col2\n0     1     2", name="stdout")],
        metadata={"tags": ["setup"]},
    ))
    doc.add_cell(Cell(
        cell_type=CellType.MARKDOWN,
        source="# Analysis\n\nThis is the analysis section.",
    ))
    doc.add_cell(Cell(
        cell_type=CellType.CODE,
        source="df.describe()",
        execution_count=2,
        outputs=[CellOutput(output_type="execute_result", content="       col1  col2\ncount   3.0   3.0\nmean    2.0   2.0")],
    ))
    return doc


class TestMinimalMode:
    def test_basic_output(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert "# %% [code]" in result
        assert "# %% [markdown]" in result
        assert "import pandas" in result
        assert "# Analysis" in result

    def test_no_metadata(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert "exec_count" not in result
        assert "tags" not in result
        assert "outputs" not in result

    def test_cell_markers_present(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert result.count("# %% [") == 3


class TestStandardMode:
    def test_includes_exec_count(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "exec_count: 1" in result
        assert "exec_count: 2" in result

    def test_includes_tags(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "tags: setup" in result

    def test_no_outputs(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.STANDARD).optimize(doc)
        assert "outputs ---" not in result


class TestFullMode:
    def test_includes_outputs(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "# --- outputs ---" in result

    def test_includes_stream_output(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "[stdout]" in result

    def test_includes_exec_result(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.FULL).optimize(doc)
        assert "count" in result


class TestOptions:
    def test_no_cell_markers(self):
        doc = _sample_doc()
        result = LLMOptimizer(mode=OutputMode.MINIMAL, include_cell_markers=False).optimize(doc)
        assert "# %% [" not in result
        assert "import pandas" in result

    def test_empty_notebook(self):
        doc = NotebookDocument()
        result = LLMOptimizer(mode=OutputMode.MINIMAL).optimize(doc)
        assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_converters/test_llm_optimizer.py -v 2>&1 | head -20
```

Expected: FAIL — empty llm_optimizer.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/converters/__init__.py`:

```python
"""Converters for notebook format transformation."""
from notebookllm.converters.llm_optimizer import LLMOptimizer

__all__ = ["LLMOptimizer"]
```

Write `notebookllm/converters/llm_optimizer.py`:

```python
"""LLM Optimizer — converts NotebookDocument to LLM-optimized text."""
from __future__ import annotations

from notebookllm.models import CellOutput, CellType, NotebookDocument, OutputMode


class LLMOptimizer:
    """Converts NotebookDocument to LLM-optimized text with configurable output modes."""

    def __init__(
        self,
        mode: OutputMode = OutputMode.MINIMAL,
        include_cell_markers: bool = True,
        max_line_length: int | None = None,
        strip_outputs: bool = True,
    ):
        self.mode = mode
        self.include_cell_markers = include_cell_markers
        self.max_line_length = max_line_length
        self.strip_outputs = strip_outputs

    def optimize(self, doc: NotebookDocument) -> str:
        """Produce optimized text based on mode."""
        if not doc.cells:
            return ""

        parts = []
        for cell in doc.cells:
            parts.append(self._format_cell(cell))

        return "\n\n".join(parts)

    def _format_cell(self, cell) -> str:
        lines = []

        # Cell marker
        if self.include_cell_markers:
            lines.append(f"# %% [{cell.cell_type.value}]")

        # Metadata (STANDARD+)
        if self.mode in (OutputMode.STANDARD, OutputMode.FULL):
            if cell.execution_count is not None:
                lines.append(f"# exec_count: {cell.execution_count}")
            tags = cell.metadata.get("tags")
            if tags:
                lines.append(f"# tags: {', '.join(tags)}")

        # Source
        lines.append(cell.source)

        # Outputs (FULL only)
        if self.mode == OutputMode.FULL and cell.outputs:
            lines.append("# --- outputs ---")
            for output in cell.outputs:
                lines.append(self._format_output(output))

        return "\n".join(lines)

    def _format_output(self, output: CellOutput) -> str:
        if output.output_type == "stream":
            name = output.name or "stdout"
            return f"# [{name}] {output.content}"
        elif output.output_type == "execute_result":
            return f"# [output] {output.content}"
        elif output.output_type == "display_data":
            return f"# [display] {output.content}"
        elif output.output_type == "error":
            return f"# [error] {output.content}"
        else:
            return f"# [{output.output_type}] {output.content}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_converters/test_llm_optimizer.py -v
```

Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/converters/ tests/test_converters/
git commit -m "feat: add LLM optimizer with minimal/standard/full output modes"
```

---

## Task 12: Validation Utils

**Files:**
- Modify: `notebookllm/utils/validation.py`
- Create: `tests/test_validation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_validation.py`:

```python
"""Tests for notebookllm.utils.validation."""
import pytest
from pathlib import Path
from notebookllm.utils.validation import (
    validate_filepath,
    validate_output_format,
    validate_cell_index,
    validate_cell_type,
)


class TestValidateFilepath:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.ipynb"
        f.write_text("{}")
        result = validate_filepath(f)
        assert result == f

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.ipynb"
        with pytest.raises(FileNotFoundError):
            validate_filepath(f)

    def test_directory(self, tmp_path):
        with pytest.raises(IsADirectoryError):
            validate_filepath(tmp_path)


class TestValidateOutputFormat:
    def test_valid_formats(self):
        for fmt in ["ipynb", "percent", "marimo", "quarto", "markdown"]:
            assert validate_output_format(fmt) == fmt

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            validate_output_format("csv")


class TestValidateCellIndex:
    def test_valid_index(self):
        assert validate_cell_index(0, 5) == 0
        assert validate_cell_index(4, 5) == 4

    def test_negative_index(self):
        with pytest.raises(IndexError):
            validate_cell_index(-1, 5)

    def test_out_of_range(self):
        with pytest.raises(IndexError):
            validate_cell_index(5, 5)


class TestValidateCellType:
    def test_valid_types(self):
        assert validate_cell_type("code").value == "code"
        assert validate_cell_type("markdown").value == "markdown"
        assert validate_cell_type("raw").value == "raw"

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            validate_cell_type("invalid")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_validation.py -v 2>&1 | head -20
```

Expected: FAIL — empty validation.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/utils/validation.py`:

```python
"""Input/output validation utilities."""
from __future__ import annotations

from pathlib import Path

from notebookllm.models import CellType


def validate_filepath(filepath: str | Path) -> Path:
    """Validate that filepath exists and is a file."""
    filepath = Path(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(f"Expected a file, got directory: {filepath}")
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return filepath


def validate_output_format(fmt: str) -> str:
    """Validate output format string."""
    valid = {"ipynb", "percent", "marimo", "quarto", "markdown"}
    if fmt not in valid:
        raise ValueError(f"Invalid format '{fmt}'. Must be one of: {valid}")
    return fmt


def validate_cell_index(index: int, total: int) -> int:
    """Validate cell index is within range."""
    if index < 0 or index >= total:
        raise IndexError(f"Cell index {index} out of range (0-{total - 1})")
    return index


def validate_cell_type(cell_type: str) -> CellType:
    """Validate and convert cell type string to CellType enum."""
    try:
        return CellType(cell_type)
    except ValueError:
        raise ValueError(f"Invalid cell type '{cell_type}'. Must be one of: code, markdown, raw")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_validation.py -v
```

Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/utils/validation.py tests/test_validation.py
git commit -m "feat: add input/output validation utilities"
```

---

## Task 13: CLI

**Files:**
- Modify: `notebookllm/cli/commands.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
"""Tests for notebookllm.cli.commands — CLI integration."""
import pytest
from click.testing import CliRunner
from pathlib import Path
from notebookllm.cli.commands import cli


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


class TestConvert:
    def test_convert_to_stdout(self, runner):
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample_percent.py")])
        assert result.exit_code == 0
        assert "# %% [code]" in result.output

    def test_convert_to_file(self, runner, tmp_path):
        out = tmp_path / "output.py"
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample.ipynb"), "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_convert_with_mode(self, runner):
        result = runner.invoke(cli, ["convert", str(FIXTURES / "sample_percent.py"), "-m", "full"])
        assert result.exit_code == 0

    def test_convert_nonexistent_file(self, runner):
        result = runner.invoke(cli, ["convert", "nonexistent.ipynb"])
        assert result.exit_code != 0


class TestInspect:
    def test_inspect(self, runner):
        result = runner.invoke(cli, ["inspect", str(FIXTURES / "sample.ipynb")])
        assert result.exit_code == 0
        assert "Cells:" in result.output or "cell" in result.output.lower()


class TestSearch:
    def test_search(self, runner):
        result = runner.invoke(cli, ["search", str(FIXTURES / "sample_percent.py"), "pandas"])
        assert result.exit_code == 0

    def test_search_with_type(self, runner):
        result = runner.invoke(cli, ["search", str(FIXTURES / "sample_percent.py"), "pandas", "-t", "code"])
        assert result.exit_code == 0


class TestGet:
    def test_get_cell(self, runner):
        result = runner.invoke(cli, ["get", str(FIXTURES / "sample_percent.py"), "0"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_cli.py -v 2>&1 | head -20
```

Expected: FAIL — empty commands.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/cli/commands.py`:

```python
"""CLI commands for notebookllm — convert, inspect, search, get."""
from __future__ import annotations

import click
from pathlib import Path

from notebookllm.loaders import load_file, dump_file
from notebookllm.models import OutputMode, CellType


@click.group()
@click.version_option(package_name="notebookllm")
def cli():
    """notebookllm — Convert and optimize Jupyter notebooks for LLMs."""
    pass


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output file path")
@click.option("-f", "--format", "fmt", help="Output format (ipynb, percent, quarto, markdown)")
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="LLM output mode")
def convert(file: str, output: str | None, fmt: str | None, mode: str):
    """Convert notebook between formats."""
    doc = load_file(file)

    if output:
        dump_file(doc, output, fmt=fmt)
        click.echo(f"Converted to {output}")
    else:
        output_mode = OutputMode(mode)
        text = doc.to_text(mode=output_mode)
        click.echo(text)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def inspect(file: str):
    """Inspect notebook structure."""
    doc = load_file(file)
    click.echo(f"Format: {doc.source_format}")
    click.echo(f"Cells: {len(doc.cells)}")
    click.echo(f"Language: {doc.language}")
    click.echo()
    for i, cell in enumerate(doc.cells):
        preview = cell.source[:80].replace("\n", " ")
        if len(cell.source) > 80:
            preview += "..."
        click.echo(f"  [{i}] {cell.cell_type.value:10s} {preview}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("query")
@click.option("-t", "--type", "cell_type", type=click.Choice(["code", "markdown", "raw"]),
              help="Filter by cell type")
def search(file: str, query: str, cell_type: str | None):
    """Search cells by content."""
    doc = load_file(file)
    ct = CellType(cell_type) if cell_type else None
    results = doc.search(query, cell_type=ct)
    if not results:
        click.echo("No matches found.")
        return
    for idx, cell in results:
        preview = cell.source[:80].replace("\n", " ")
        click.echo(f"  [{idx}] {cell.cell_type.value:10s} {preview}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("index", type=int)
def get(file: str, index: int):
    """Get a specific cell by index."""
    doc = load_file(file)
    cell = doc.get_cell(index)
    click.echo(f"Cell [{index}] ({cell.cell_type.value}):")
    click.echo(cell.source)


@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport type")
def server(transport: str):
    """Start MCP server."""
    from notebookllm.mcp.server import main
    main(transport=transport)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_cli.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/cli/commands.py tests/test_cli.py
git commit -m "feat: add CLI with convert, inspect, search, get, server commands"
```

---

## Task 14: MCP Session Manager

**Files:**
- Modify: `notebookllm/mcp/session.py`
- Create: `tests/test_mcp_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_session.py`:

```python
"""Tests for notebookllm.mcp.session — session management."""
import pytest
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument


@pytest.fixture
def manager():
    return SessionManager()


class TestSessionManager:
    def test_store_and_get(self, manager):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        manager.store("session-1", doc, filepath="/tmp/test.ipynb")
        result = manager.get("session-1")
        assert result is doc
        assert len(result.cells) == 1

    def test_get_nonexistent(self, manager):
        with pytest.raises(KeyError):
            manager.get("missing")

    def test_delete(self, manager):
        doc = NotebookDocument()
        manager.store("session-1", doc)
        manager.delete("session-1")
        with pytest.raises(KeyError):
            manager.get("session-1")

    def test_delete_nonexistent(self, manager):
        with pytest.raises(KeyError):
            manager.delete("missing")

    def test_list_sessions(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc)
        manager.store("s2", doc)
        sessions = manager.list_sessions()
        assert "s1" in sessions
        assert "s2" in sessions
        assert len(sessions) == 2

    def test_store_replaces_existing(self, manager):
        doc1 = NotebookDocument()
        doc1.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        doc2 = NotebookDocument()
        doc2.add_cell(Cell(cell_type=CellType.CODE, source="y = 2"))
        manager.store("s1", doc1)
        manager.store("s1", doc2)
        result = manager.get("s1")
        assert result.cells[0].source == "y = 2"

    def test_get_filepath(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc, filepath="/tmp/test.ipynb")
        assert manager.get_filepath("s1") == "/tmp/test.ipynb"

    def test_get_filepath_none(self, manager):
        doc = NotebookDocument()
        manager.store("s1", doc)
        assert manager.get_filepath("s1") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_mcp_session.py -v 2>&1 | head -20
```

Expected: FAIL — empty session.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/mcp/session.py`:

```python
"""Session manager for MCP server — supports multi-user notebook editing."""
from __future__ import annotations

from dataclasses import dataclass, field

from notebookllm.models import NotebookDocument


@dataclass
class Session:
    """A single user session holding a notebook."""
    doc: NotebookDocument
    filepath: str | None = None


class SessionManager:
    """Manages notebook sessions for MCP connections."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def store(self, session_id: str, doc: NotebookDocument, filepath: str | None = None) -> None:
        """Store or replace a notebook session."""
        self._sessions[session_id] = Session(doc=doc, filepath=filepath)

    def get(self, session_id: str) -> NotebookDocument:
        """Get notebook for a session. Raises KeyError if not found."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self._sessions[session_id].doc

    def get_filepath(self, session_id: str) -> str | None:
        """Get filepath for a session, or None if not set."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self._sessions[session_id].filepath

    def delete(self, session_id: str) -> None:
        """Delete a session. Raises KeyError if not found."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        del self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return list(self._sessions.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_mcp_session.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/mcp/session.py tests/test_mcp_session.py
git commit -m "feat: add MCP session manager with multi-user support"
```

---

## Task 15: MCP Server

**Files:**
- Modify: `notebookllm/mcp/server.py`
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp.py`:

```python
"""Tests for notebookllm.mcp.server — MCP server tools."""
import pytest
from notebookllm.mcp.server import create_app
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session_manager():
    return SessionManager()


@pytest.fixture
def app(session_manager):
    return create_app(session_manager)


class TestMCPServerTools:
    """Test MCP server tool functions directly (not via MCP protocol)."""

    def test_load_notebook(self, app, session_manager):
        # The app should have tools registered
        # We test by calling the underlying functions
        from notebookllm.loaders import load_file
        doc = load_file(FIXTURES / "sample_percent.py")
        session_manager.store("test", doc)
        assert session_manager.get("test") is doc

    def test_session_lifecycle(self, session_manager):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        session_manager.store("s1", doc)
        assert len(session_manager.get("s1").cells) == 1
        session_manager.delete("s1")
        with pytest.raises(KeyError):
            session_manager.get("s1")


class TestMCPAppCreation:
    def test_create_app(self, session_manager):
        app = create_app(session_manager)
        assert app is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_mcp.py -v 2>&1 | head -20
```

Expected: FAIL — empty server.py

- [ ] **Step 3: Write the implementation**

Write `notebookllm/mcp/server.py`:

```python
"""MCP server for notebookllm — 11 tools for notebook operations."""
from __future__ import annotations

import uuid
from typing import Any

from notebookllm.loaders import load_file, dump_file
from notebookllm.mcp.session import SessionManager
from notebookllm.models import Cell, CellType, NotebookDocument, OutputMode


def create_app(session_manager: SessionManager | None = None):
    """Create and configure the MCP server app."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError("MCP server requires 'mcp[cli]'. Install with: pip install notebookllm[mcp]")

    if session_manager is None:
        session_manager = SessionManager()

    mcp = FastMCP("notebookllm")

    @mcp.tool()
    def load_notebook(filepath: str) -> str:
        """Load a notebook file into session."""
        session_id = str(uuid.uuid4())
        doc = load_file(filepath)
        session_manager.store(session_id, doc, filepath=filepath)
        return f"Loaded {len(doc.cells)} cells from {filepath}. Session: {session_id}"

    @mcp.tool()
    def save_notebook(session_id: str, output_filepath: str | None = None) -> str:
        """Save notebook to file."""
        doc = session_manager.get(session_id)
        filepath = output_filepath or session_manager.get_filepath(session_id)
        if not filepath:
            return "No filepath specified and none set in session."
        dump_file(doc, filepath)
        return f"Saved to {filepath}"

    @mcp.tool()
    def to_text(session_id: str, mode: str = "minimal") -> str:
        """Convert notebook to LLM-optimized text."""
        doc = session_manager.get(session_id)
        output_mode = OutputMode(mode)
        return doc.to_text(mode=output_mode)

    @mcp.tool()
    def list_cells(session_id: str) -> str:
        """List all cells with index, type, and preview."""
        doc = session_manager.get(session_id)
        lines = []
        for i, cell in enumerate(doc.cells):
            preview = cell.source[:60].replace("\n", " ")
            if len(cell.source) > 60:
                preview += "..."
            lines.append(f"[{i}] {cell.cell_type.value:10s} {preview}")
        return "\n".join(lines) if lines else "No cells."

    @mcp.tool()
    def get_cell(session_id: str, index: int) -> str:
        """Get a specific cell by index."""
        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        return f"Cell [{index}] ({cell.cell_type.value}):\n{cell.source}"

    @mcp.tool()
    def add_cell(session_id: str, source: str, cell_type: str = "code", position: int | None = None) -> str:
        """Add a new cell."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type)
        cell = Cell(cell_type=ct, source=source)
        doc.add_cell(cell, position=position)
        return f"Added {cell_type} cell at position {position or len(doc.cells) - 1}"

    @mcp.tool()
    def edit_cell(session_id: str, index: int, source: str, cell_type: str | None = None) -> str:
        """Edit an existing cell."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type) if cell_type else None
        doc.edit_cell(index, source=source, cell_type=ct)
        return f"Edited cell [{index}]"

    @mcp.tool()
    def delete_cell(session_id: str, index: int) -> str:
        """Delete a cell by index."""
        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        doc.delete_cell(index)
        return f"Deleted cell [{index}] ({cell.cell_type.value})"

    @mcp.tool()
    def move_cell(session_id: str, from_index: int, to_index: int) -> str:
        """Move a cell from one position to another."""
        doc = session_manager.get(session_id)
        doc.move_cell(from_index, to_index)
        return f"Moved cell from [{from_index}] to [{to_index}]"

    @mcp.tool()
    def search_cells(session_id: str, query: str, cell_type: str | None = None) -> str:
        """Search cells by content (case-insensitive)."""
        doc = session_manager.get(session_id)
        ct = CellType(cell_type) if cell_type else None
        results = doc.search(query, cell_type=ct)
        if not results:
            return "No matches found."
        lines = []
        for idx, cell in results:
            preview = cell.source[:60].replace("\n", " ")
            lines.append(f"[{idx}] {cell.cell_type.value:10s} {preview}")
        return "\n".join(lines)

    @mcp.tool()
    def execute_cell(session_id: str, index: int, timeout: int = 60) -> str:
        """Execute a code cell via Jupyter kernel (requires notebookllm[execute])."""
        try:
            import jupyter_client
        except ImportError:
            return "Error: notebookllm[execute] not installed. Run: pip install notebookllm[execute]"

        doc = session_manager.get(session_id)
        cell = doc.get_cell(index)
        if cell.cell_type != CellType.CODE:
            return f"Cell [{index}] is not a code cell (it's {cell.cell_type.value})."

        # Execute via jupyter_client
        km = jupyter_client.KernelManager(kernel_name=doc.kernel_name or "python3")
        km.start_kernel()
        kc = km.client()
        kc.start_channels()
        try:
            kc.execute(cell.source)
            reply = kc.get_shell_msg(timeout=timeout)
            iopub = kc.get_iopub_msg(timeout=timeout)

            outputs = []
            while True:
                try:
                    msg = kc.get_iopub_msg(timeout=2)
                    msg_type = msg["msg_type"]
                    if msg_type == "stream":
                        outputs.append(f"[{msg['content'].get('name', 'stdout')}] {msg['content'].get('text', '')}")
                    elif msg_type in ("execute_result", "display_data"):
                        text = msg["content"].get("data", {}).get("text/plain", "")
                        outputs.append(f"[output] {text}")
                    elif msg_type == "error":
                        traceback = "\n".join(msg["content"].get("traceback", []))
                        outputs.append(f"[error] {traceback}")
                    elif msg_type == "status" and msg["content"].get("execution_state") == "idle":
                        break
                except Exception:
                    break

            result = "\n".join(outputs) if outputs else "Cell executed (no output)."
            return f"Cell [{index}] executed:\n{result}"
        finally:
            kc.stop_channels()
            km.shutdown_kernel()

    return mcp


def main(transport: str = "stdio"):
    """Entry point for MCP server."""
    app = create_app()
    app.run(transport=transport)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_mcp.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notebookllm/mcp/server.py tests/test_mcp.py
git commit -m "feat: add MCP server with 11 tools and session-scoped state"
```

---

## Task 16: Agent Skill

**Files:**
- Create: `skills/notebookllm/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `skills/notebookllm/SKILL.md`:

```markdown
# Skill: notebookllm

## Description
CLI wrapper for notebookllm — convert, inspect, search, and optimize Jupyter notebooks for LLMs.

## Triggers
- "convert notebook to text"
- "optimize notebook for LLM"
- "inspect notebook"
- "search notebook cells"
- "notebook to markdown"
- "notebook to percent format"

## Available Commands

### Convert notebook to LLM-optimized text
```bash
notebookllm convert <file> [-m minimal|standard|full]
```

### Convert between formats
```bash
notebookllm convert <input> -o <output> [-f ipynb|percent|quarto|markdown]
```

### Inspect notebook structure
```bash
notebookllm inspect <file>
```

### Search cells by content
```bash
notebookllm search <file> "<query>" [-t code|markdown|raw]
```

### Get specific cell
```bash
notebookllm get <file> <index>
```

### Start MCP server
```bash
notebookllm server start [--transport stdio|sse]
```

## Examples

### Optimize notebook for LLM context
```bash
notebookllm convert analysis.ipynb -m minimal
```

### Convert .ipynb to percent .py
```bash
notebookllm convert notebook.ipynb -o notebook.py -f percent
```

### Find all cells with pandas imports
```bash
notebookllm search notebook.ipynb "import pandas" -t code
```

## Output Modes
- **minimal**: Cell markers + source only (default)
- **standard**: Adds execution count and tags
- **full**: Adds cell outputs

## Supported Formats
- `.ipynb` — Jupyter notebook (nbformat v4)
- `.py` — Percent format (# %% markers)
- `.py` — Marimo format (@app.cell decorators)
- `.qmd` — Quarto markdown
- `.md` — Markdown with code blocks
```

- [ ] **Step 2: Verify file exists**

Run:
```bash
cat skills/notebookllm/SKILL.md | head -10
```

Expected: Skill file content visible.

- [ ] **Step 3: Commit**

```bash
git add skills/notebookllm/SKILL.md
git commit -m "feat: add agent skill for notebookllm CLI"
```

---

## Task 17: Round-trip Tests

**Files:**
- Create: `tests/test_roundtrip.py`

- [ ] **Step 1: Write the test**

Create `tests/test_roundtrip.py`:

```python
"""Tests for round-trip fidelity — format A → B → A preserves content."""
import pytest
from pathlib import Path
from notebookllm.loaders import load_file, dump_file, loads_text
from notebookllm.models import CellType


FIXTURES = Path(__file__).parent / "fixtures"


class TestRoundTrips:
    def test_ipynb_to_percent_to_ipynb(self, tmp_path):
        """ipynb → percent → ipynb preserves cell sources."""
        doc = load_file(FIXTURES / "sample.ipynb")
        # Dump to percent
        percent_path = tmp_path / "out.py"
        dump_file(doc, percent_path)
        # Load back
        doc2 = load_file(percent_path)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source == c2.source

    def test_percent_roundtrip(self, tmp_path):
        """percent → ipynb → percent preserves content."""
        doc = load_file(FIXTURES / "sample_percent.py")
        # Dump to ipynb
        ipynb_path = tmp_path / "out.ipynb"
        dump_file(doc, ipynb_path)
        # Load back
        doc2 = load_file(ipynb_path)
        # Dump back to percent
        percent_path = tmp_path / "out2.py"
        dump_file(doc2, percent_path)
        doc3 = load_file(percent_path)
        assert len(doc3.cells) == len(doc.cells)
        for c1, c3 in zip(doc.cells, doc3.cells):
            assert c1.cell_type == c3.cell_type
            assert c1.source.strip() == c3.source.strip()

    def test_quarto_roundtrip(self, tmp_path):
        """quarto → ipynb → quarto preserves content."""
        doc = load_file(FIXTURES / "sample_quarto.qmd")
        ipynb_path = tmp_path / "out.ipynb"
        dump_file(doc, ipynb_path)
        doc2 = load_file(ipynb_path)
        qmd_path = tmp_path / "out.qmd"
        dump_file(doc2, qmd_path)
        doc3 = load_file(qmd_path)
        assert len(doc3.cells) == len(doc.cells)

    def test_markdown_roundtrip(self, tmp_path):
        """markdown → ipynb → markdown preserves content."""
        doc = load_file(FIXTURES / "sample_markdown.md")
        ipynb_path = tmp_path / "out.ipynb"
        dump_file(doc, ipynb_path)
        doc2 = load_file(ipynb_path)
        md_path = tmp_path / "out.md"
        dump_file(doc2, md_path)
        doc3 = load_file(md_path)
        assert len(doc3.cells) == len(doc.cells)

    def test_text_roundtrip(self):
        """text → NotebookDocument → text preserves cell content."""
        text = "# %% [code]\nimport pandas as pd\n\n# %% [markdown]\n# Title\n"
        doc = loads_text(text)
        result = doc.to_text()
        doc2 = loads_text(result)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source.strip() == c2.source.strip()
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/test_roundtrip.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_roundtrip.py
git commit -m "test: add round-trip fidelity tests for all format conversions"
```

---

## Task 18: Cleanup

**Files:**
- Delete: `build/` directory
- Delete: `main.py`
- Delete: `__init__.py` (root)
- Delete: `mcp_llm.md`
- Delete: `notebookllm/mcp_server.py` (old standalone MCP server)
- Delete: `notebookllm/cli.py` (old CLI)
- Delete: `notebookllm/notebookllm/notebookllm.py` (old core — replaced by models.py + loaders)

- [ ] **Step 1: Remove stale artifacts**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
rm -rf build/
rm -f main.py
rm -f __init__.py
rm -f mcp_llm.md
rm -f notebookllm/mcp_server.py
rm -f notebookllm/cli.py
rm -rf notebookllm/notebookllm/  # Old inner package
rm -rf notebookllm.egg-info/
```

- [ ] **Step 2: Verify structure**

Run:
```bash
find notebookllm -name "*.py" | sort
ls -la
```

Expected: Clean structure, no stale files.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove stale build artifacts and old source files"
```

---

## Task 19: Update Public API

**Files:**
- Modify: `notebookllm/__init__.py`

- [ ] **Step 1: Update __init__.py**

Write `notebookllm/__init__.py`:

```python
"""notebookllm — Convert and optimize Jupyter notebooks for LLMs."""

__version__ = "3.0.0"

from notebookllm.models import (
    Cell,
    CellOutput,
    CellType,
    NotebookDocument,
    OutputMode,
)
from notebookllm.loaders import load_file, dump_file, loads_text

__all__ = [
    "Cell",
    "CellOutput",
    "CellType",
    "NotebookDocument",
    "OutputMode",
    "load_file",
    "dump_file",
    "loads_text",
]
```

- [ ] **Step 2: Verify imports**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -c "from notebookllm import NotebookDocument, Cell, CellType, load_file, dump_file; print('All imports OK')"
```

Expected: `All imports OK`

- [ ] **Step 3: Commit**

```bash
git add notebookllm/__init__.py
git commit -m "feat: update public API with all core exports"
```

---

## Task 20: Final Integration Test

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Verify CLI works**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
python -m notebookllm.cli.commands convert tests/fixtures/sample_percent.py
python -m notebookllm.cli.commands inspect tests/fixtures/sample.ipynb
python -m notebookllm.cli.commands search tests/fixtures/sample_percent.py "pandas"
python -m notebookllm.cli.commands get tests/fixtures/sample_percent.py 0
```

Expected: All commands produce correct output.

- [ ] **Step 3: Verify package builds**

Run:
```bash
cd /media/D/Dbackup/notebookllm/notebookllm
pip install -e ".[all]" 2>&1 | tail -5
python -c "import notebookllm; print(notebookllm.__version__)"
```

Expected: Version `3.0.0` printed.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "release: notebookllm v3.0.0 — multi-format support, CLI, MCP server"
```
