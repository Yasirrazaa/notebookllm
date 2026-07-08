notebookllm
===========

Convert, inspect, and optimize Jupyter notebooks for **AI Agents** — Claude Code,
Cursor, GitHub Copilot, Claude Desktop, VS Code, Zed, and more.

``notebookllm`` converts notebooks to a clean, Agent-optimized plain text format,
reducing token usage by **up to 80%**. It reads and writes **8+ formats** —
``.ipynb``, percent scripts, Quarto, Markdown, Marimo, R Markdown, Deepnote, and
flat scripts — through a single unified API. Use it from the CLI, Python library,
or MCP server.

.. image:: https://img.shields.io/pypi/v/notebookllm
   :target: https://pypi.org/project/notebookllm
   :alt: PyPI

.. image:: https://img.shields.io/pypi/dm/notebookllm
   :target: https://pypi.org/project/notebookllm
   :alt: Downloads

.. important::
   **⚡ Unified Package — One Install, Everything You Need**

   The standalone ``notebookllm-mcp`` server has been fully integrated into the
   core ``notebookllm`` package. Both the Python library and MCP server now ship
   together — one ``pip install``, zero headaches. The legacy ``notebookllm-mcp``
   package is **deprecated**. Install ``notebookllm[mcp]`` to get everything.

---

Why notebookllm?
----------------

Raw ``.ipynb`` files waste AI Agent context. The JSON structure, metadata,
execution counts, and base64-encoded image outputs burn tokens without adding
value. ``notebookllm`` strips all that noise and produces clean, structured
text that Agents can reason over effectively.

But it doesn't stop at one-way conversion. ``notebookllm`` is a **bidirectional
notebook toolkit**: it reads, writes, edits, searches, executes, and converts
notebooks across 8+ formats. Whether you're feeding a notebook into Claude Code,
building a VS Code extension, or automating a data pipeline, ``notebookllm``
has you covered.

---

Key Features
------------

* **8+ notebook formats** — Load and save ``.ipynb``, percent (``# %%``),
  Quarto (``.qmd``), Markdown (``.md``), Marimo (``.py``), R Markdown (``.Rmd``),
  Deepnote (``.deepnote``), and flat scripts.
* **4 output modes** — ``minimal`` (source only), ``standard`` (+ metadata),
  ``full`` (+ outputs), ``token-budget`` (drops cells to fit a token limit).
* **Smart token budget** — Automatically drops lowest-priority cells
  (bare code → code with outputs → markdown) to stay within an Agent's context
  window.
* **Token counting** — Per-notebook and per-cell token measurement via tiktoken
  (GPT-4 ``cl100k_base`` encoding) or built-in heuristic fallback.
* **Batch conversion** — Convert multiple files at once with ``--outdir`` for
  auto-named output.
* **Cell operations** — Add, edit, delete, move, and search cells programmatically.
* **Cell execution** — Run code cells via Jupyter kernels (async, thread-pooled).
* **Streaming** — Handle notebooks larger than 10 MB via ``ijson`` streaming
  (cell-by-cell, no memory spike).
* **MCP server** — Expose all operations as MCP tools, resources, and prompts
  for AI Agent clients (Claude Desktop, VS Code, Zed, Cursor, Claude Code).
* **Output summarization** — DataFrames get shape/column summaries, images get
  size metadata, tracebacks get compressed to the last line.
* **Validation** — Detect orphaned outputs, empty cells, and invalid cell types.
* **Atomic writes** — Crash-safe file saving via temp file + rename.

---

Installation
------------

.. code-block:: bash

   pip install notebookllm            # Core: format conversion, streaming, execution
   pip install notebookllm[cli]       # + CLI (click, rich)
   pip install notebookllm[mcp]       # + MCP server
   pip install notebookllm[token]     # + Accurate token counting (tiktoken)
   pip install notebookllm[all]       # Everything

Dependency breakdown:

=============== ================================================================
Extra           Packages
=============== ================================================================
*(base)*        ``nbformat``, ``jupyter_client``, ``ijson``, ``pyyaml``
``[cli]``       ``click``, ``rich``
``[mcp]``       ``mcp[cli]``
``[token]``     ``tiktoken``
=============== ================================================================

Without ``[token]``, token counting uses a ``len(text)/4`` heuristic — instant
but approximate (±20%). With ``[token]``, it uses GPT-4's ``cl100k_base``
encoding for exact counts.

---

Quick Start
-----------

.. code-block:: bash

   # Convert to Agent-optimized text
   notebookllm convert notebook.ipynb

   # Convert between formats
   notebookllm convert notebook.ipynb -o output.py -f percent

   # Count tokens
   notebookllm tokens notebook.ipynb --breakdown

   # Inspect structure
   notebookllm inspect notebook.ipynb

.. code-block:: python

   from notebookllm import load_file

   doc = load_file("notebook.ipynb")
   print(doc.to_text())                            # minimal Agent text
   print(doc.to_text(mode="token-budget", max_tokens=2000))  # budget mode

---

CLI Reference
-------------

All commands support ``--help`` inline documentation.

``notebookllm convert``
^^^^^^^^^^^^^^^^^^^^^^^^

Convert notebook(s) between formats or to Agent-optimized text.

.. code-block:: bash

   # Single file to Agent text (stdout)
   notebookllm convert notebook.ipynb

   # Single file to a specific format
   notebookllm convert notebook.ipynb -o output.py -f percent
   notebookllm convert notebook.ipynb -o output.qmd -f quarto

   # Output verbosity
   notebookllm convert notebook.ipynb              # minimal (default)
   notebookllm convert notebook.ipynb -m standard  # + execution counts, tags
   notebookllm convert notebook.ipynb -m full      # + cell outputs

   # Batch: multiple files to stdout
   notebookllm convert a.ipynb b.qmd c.py

   # Batch: multiple files to directory (auto-named ``{stem}_converted.{ext}``)
   notebookllm convert *.ipynb --outdir ./out
   notebookllm convert a.ipynb b.qmd --outdir ./out -f markdown

``notebookllm inspect``
^^^^^^^^^^^^^^^^^^^^^^^^^

Show notebook structure — format, language, cell count, and a Rich table
of cells with previews.

.. code-block:: bash

   notebookllm inspect notebook.ipynb

``notebookllm search``
^^^^^^^^^^^^^^^^^^^^^^^

Search cells by content (case-insensitive substring match). Use ``-t``
to filter by cell type (``code``, ``markdown``, ``raw``). Results are
highlighted with Rich markup.

.. code-block:: bash

   notebookllm search notebook.ipynb "import pandas"
   notebookllm search notebook.ipynb "def train" -t code

``notebookllm get``
^^^^^^^^^^^^^^^^^^^^

Extract a single cell by its 0-based index. Displays with Rich syntax
highlighting.

.. code-block:: bash

   notebookllm get notebook.ipynb 3

``notebookllm tokens``
^^^^^^^^^^^^^^^^^^^^^^^

Estimate token usage for a notebook. Uses tiktoken when the ``[token]``
extra is installed, otherwise falls back to ``len(text)/4``.

.. code-block:: bash

   notebookllm tokens notebook.ipynb              # total tokens
   notebookllm tokens notebook.ipynb --breakdown  # per-cell table
   notebookllm tokens notebook.ipynb -m full      # count with outputs

``notebookllm server``
^^^^^^^^^^^^^^^^^^^^^^^

Start the MCP server for AI Agent integration. Uses stdio transport by
default (for Claude Desktop, VS Code, Zed). Use ``--transport sse`` for
SSE-based connections.

.. code-block:: bash

   notebookllm server                    # stdio (default)
   notebookllm server --transport sse    # SSE

---

Python API
----------

Loading and Saving
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from notebookllm import NotebookDocument, load_file, dump_file, loads_text

   # Load — auto-detects format from extension
   doc = load_file("notebook.ipynb")
   doc = load_file("analysis.qmd")

   # Load from string
   doc = loads_text("# %% [code]\\nprint('hi')\\n", source_format="percent")

   # Class method
   doc = NotebookDocument.from_file("notebook.ipynb")

   # From text with auto-detection
   doc = NotebookDocument.from_text(text, source_format="quarto")

   # Save — auto-detects format from extension
   doc.to_file("output.ipynb")
   doc.to_file("output.py", fmt="percent")
   dump_file(doc, "output.md", fmt="markdown")

   # Serialize/deserialize (CIR JSON)
   json_str = doc.to_json()
   restored = NotebookDocument.from_json(json_str)

Converting to AI Agent Text
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from notebookllm import OutputMode

   text = doc.to_text()                                  # minimal (default)
   text = doc.to_text(mode=OutputMode.STANDARD)          # + execution counts, tags
   text = doc.to_text(mode=OutputMode.FULL)              # + cell outputs
   text = doc.to_text(mode="token-budget", max_tokens=5000)  # budget mode

Token Counting
^^^^^^^^^^^^^^

.. code-block:: python

   from notebookllm import tokenize_notebook, count_tokens

   # Notebook-level
   report = tokenize_notebook(doc, mode="minimal")
   print(report.token_summary)  # "Total: 420 tokens across 8 cells"
   for ct in report.cell_tokens:
       print(f"  [{ct.cell_index}] {ct.cell_type}: {ct.tokens} tokens — {ct.preview}")

   # Single string
   n = count_tokens("hello world")  # 2 tokens (tiktoken) or 3 (fallback)

   # Convenience method
   report = doc.token_breakdown(mode="minimal")

Cell Operations
^^^^^^^^^^^^^^^

.. code-block:: python

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

Search and Filter
^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Search (returns list of (index, cell) tuples)
   results = doc.search("import pandas", cell_type=CellType.CODE)
   for idx, cell in results:
       print(f"[{idx}] {cell.source[:60]}")

   # Filter
   code_cells = doc.filter_cells(cell_type=CellType.CODE)
   matches = doc.filter_cells(query="train")

Inspection
^^^^^^^^^^

.. code-block:: python

   print(len(doc.cells))           # cell count
   print(doc.source_format)        # "ipynb", "percent", "quarto", etc.
   print(doc.language)             # "python", "r", etc.
   print(doc.kernel_name)          # "python3", etc.

Validation
^^^^^^^^^^

.. code-block:: python

   from notebookllm.utils.validation import validate_notebook

   report = validate_notebook(doc)
   print(report.summary)       # "Validation passed." or "Validation found 2 errors, 3 warnings."
   print(report.format_text()) # human-readable error/warning listing
   print(report.is_valid)      # True if no errors

---

Output Modes
------------

Controls how much detail appears in the Agent-optimized text output:

``minimal`` (default)
   ``# %% [type]`` markers + source code only.
   Cleanest for Agent input. Output format::

      # %% [markdown]
      # Data Analysis Pipeline

      # %% [code]
      import pandas as pd
      import numpy as np

``standard``
   Adds execution count and cell metadata tags::

      # %% [code]
      # exec_count: 3
      # tags: preprocessing, data-cleaning
      df = pd.read_csv("data.csv")

``full``
   Adds cell execution outputs (stdout, results, errors)::

      # %% [code]
      print(df.head())
      # --- outputs ---
      # [stdout]    col1  col2
      # 0     1     2

``token-budget``
   Drops lowest-priority cells to stay within a ``max_tokens`` budget.
   Drop order (highest-value kept longest):

   1. Markdown cells (explanatory — never dropped if only one remains)
   2. Code cells with outputs (executed, have results)
   3. Code cells without outputs (scaffolding — dropped first)

---

Output Summarization
--------------------

When using ``token-budget`` mode (or with ``summarize_outputs=True`` via the
:class:`~notebookllm.converters.llm_optimizer.LLMOptimizer` API),
long and rich outputs are compressed:

* **DataFrames**: Shape and column names extracted from the ASCII repr.
  ``# [DataFrame(1000, 5)] Columns: col1, col2, col3 (values hidden)``
* **Images**: MIME type and approximate size.
  ``# [Plot: image/png, ~42KB]``
* **Tracebacks**: Last line only (the actual error message).
  ``# [error] ValueError: invalid literal for int()``
* **Long text**: Truncated at 500 characters with a remainder note.

---

Token Counting
--------------

Measures notebook token consumption for AI Agent context planning.

**CLI**: ``notebookllm tokens <file>`` prints total token count.
``--breakdown`` shows a per-cell table with index, type, tokens, and preview.

**Accuracy**: Uses tiktoken (GPT-4 ``cl100k_base`` encoding) when the
``[token]`` extra is installed. Otherwise falls back to ``len(text)/4``
heuristic — fast but approximate.

**Budget mode**: ``doc.to_text(mode="token-budget", max_tokens=5000)``
drops cells to fit within the token limit.

---

Supported Formats
-----------------

.. list-table::
   :header-rows: 1
   :widths: 16 44 8 8

   * - Extension
     - Format
     - Load
     - Dump
   * - ``.ipynb``
     - Jupyter Notebook (``nbformat`` v4)
     - ✅
     - ✅
   * - ``.py``
     - Percent script (``# %%`` markers)
     - ✅
     - ✅
   * - ``.py``
     - Marimo (``@app.cell`` decorators)
     - ✅
     - ✅
   * - ``.qmd``
     - Quarto document
     - ✅
     - ✅
   * - ``.md``
     - Markdown with fenced code blocks
     - ✅
     - ✅
   * - ``.Rmd``
     - R Markdown (``rmarkdown`` package)
     - ✅
     - ✅
   * - ``.deepnote``
     - Deepnote YAML project
     - ✅
     - ✅
   * - ``.py``
     - Flat script (one-way export)
     - ❌
     - ✅

Large File Streaming
--------------------

Notebooks larger than 10 MB are parsed using ``ijson`` streaming, which
processes cells one at a time without loading the entire JSON into memory.
Metadata is extracted from the file tail without reading the full file.
Falls back to ``nbformat`` if ``ijson`` is not installed.

Cell Execution
--------------

Run code cells via Jupyter kernels. Cell execution is available through the
MCP server tools ``execute`` and ``execute_all``:

.. code-block:: bash

   # via MCP server:
   #   execute(session_id="...", index=0)
   #   execute_all(session_id="...")

Execution is async and thread-pooled so the MCP server remains responsive.
Kernels are started lazily per session and cleaned up when the session
is closed. Available kernels can be listed with ``list_kernels()``.

The underlying :class:`~notebookllm.mcp.engine.KernelPool` manages kernel
lifecycle and thread-pooled execution for MCP server sessions.

---

MCP Server
----------

The MCP server exposes notebook operations for AI Agent clients (Claude Desktop,
VS Code, Zed, Cursor, Claude Code). 20 unique tools with 6 backward-compatible
aliases, plus resources and prompts.

Setup
^^^^^

.. code-block:: bash

   notebookllm server                    # stdio (default)
   notebookllm server --transport sse    # SSE

**Claude Desktop** (``claude_desktop_config.json``):

.. code-block:: json

    {
      "mcpServers": {
        "notebookllm": {
          "command": "uvx",
          "args": ["notebookllm-server"]
        }
      }
    }

To pin a specific version or extras:

.. code-block:: json

    {
      "mcpServers": {
        "notebookllm": {
          "command": "uvx",
          "args": ["--from", "notebookllm[all]", "notebookllm-server"]
        }
      }
    }

Using ``pip`` (manual install):

.. code-block:: bash

    pip install notebookllm[mcp]

.. code-block:: json

    {
      "mcpServers": {
        "notebookllm": {
          "command": "python",
          "args": ["-m", "notebookllm.mcp.server"]
        }
      }
    }

**VS Code****VS Code** (``.vscode/mcp.json``):

Using ``uvx``:

.. code-block:: json

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

Using ``pip``:

.. code-block:: json

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

**Zed****Zed** (``~/.config/zed/mcp.json``):

Using ``uvx``:

.. code-block:: json

    {
      "notebookllm": {
        "command": "uvx",
        "args": ["notebookllm-server"]
      }
    }

Using ``pip``:

.. code-block:: none

    {
      "notebookllm": {
        "command": "python",
        "args": ["-m", "notebookllm.mcp.server"]
      }
    }

     - Create an empty notebook session
     - No
   * - ``list_sessions``
     - List all active sessions with cell counts
     - No
   * - ``close_session``
     - Close session and clean up its kernel
     - No
   * - ``save`` / ``save_notebook``
     - Save session to file
     - Yes
   * - ``to_text``
     - Convert to Agent text (supports ``max_tokens``)
     - No
   * - ``list_cells``
     - List cells with index, type, preview
     - No
   * - ``get_cell``
     - Get a cell by index
     - No
   * - ``add_cell``
     - Add a new cell
     - No
   * - ``edit_cell``
     - Edit an existing cell's source/type
     - Yes
   * - ``delete_cell``
     - Delete a cell
     - Yes
   * - ``move_cell``
     - Move a cell between positions
     - No
   * - ``search_cells``
     - Search cells by content (case-insensitive)
     - No
   * - ``count_tokens``
     - Count tokens in session notebook
     - No
   * - ``convert`` / ``convert_format``
     - Convert session to another format
     - No
   * - ``execute`` / ``execute_cell``
     - Execute a code cell (async, thread-pooled)
     - Yes
   * - ``execute_all`` / ``execute_all_cells``
     - Execute all code cells sequentially
     - Yes
   * - ``list_kernels``
     - List available Jupyter kernels
     - No
   * - ``fingerprint``
     - Session summary (cells, imports, functions)
     - No
   * - ``diff``
     - Compare two sessions using unified diff
     - No

Resources
^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - URI
     - Description
   * - ``notebook://{session_id}``
     - Full notebook as Agent-optimized text
   * - ``notebook://{session_id}/cells``
     - Cell listing with index, type, preview
   * - ``notebook://{session_id}/cells/{index}``
     - Specific cell by index

Prompts
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Prompt
     - Description
   * - ``summarize_notebook(session_id)``
     - Summarize notebook contents and purpose
   * - ``review_code(session_id)``
     - Review code quality
   * - ``explain_notebook(session_id)``
     - Explain step by step

Session Management
^^^^^^^^^^^^^^^^^^

The MCP server maintains up to **100 concurrent sessions**, persisted in a
local SQLite database at ``~/.local/share/notebookllm/sessions.db``. Each
session has an optional Jupyter kernel (if execution is used). Sessions are
auto-evicted (oldest first) when the limit is reached. Sessions survive
server restarts — use ``close_session`` to clean up explicitly.

---

Agent Skill Integration
-----------------------

For autonomous AI Agents (Claude Code, Cursor, Claude Desktop, GitHub Copilot
Workspaces), ``notebookllm`` includes a **native agent skill** at
``skills/notebookllm/SKILL.md``.

This skill document teaches AI Agents exactly how to leverage ``notebookllm``
to manipulate and inspect notebooks efficiently on your behalf. To equip your
agent with this skill, simply ensure the ``skills/`` directory is discoverable
by your agent's environment, or instruct the agent to read
``skills/notebookllm/SKILL.md`` directly.

The skill covers: CLI commands, Python API usage, output modes, token counting,
format conversion, and MCP server integration.

---

Development
-----------

.. code-block:: bash

   git clone https://github.com/yasirrazaa/notebookllm.git
   cd notebookllm
   uv sync && uv pip install -e ".[dev]"

   uv run pytest                      # run tests
   uv run pytest --cov=notebookllm    # with coverage
   uv run pytest tests/benchmarks --benchmark-only  # performance benchmarks
   uv run ruff check .                # lint
   uv run mypy notebookllm            # type check
   uv run sphinx-build -b html -E docs docs/_build  # build this documentation

---

API Reference
-------------

.. toctree::
   :maxdepth: 2

   cli
   agent_integration
   api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

License
-------

MIT
