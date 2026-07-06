notebookllm
===========

Convert, inspect, and optimize Jupyter notebooks for AI Agents (Claude Code, Cursor, GitHub Copilot, etc.).

``notebookllm`` converts notebooks to a clean, Agent-optimized plain text format,
reducing token usage by up to 80%. It reads and writes **8 formats** — ``.ipynb``,
percent scripts, Quarto, Markdown, Marimo, R Markdown, Deepnote, and flat scripts —
through a single unified API. Use it from the CLI, Python library, or MCP server.

.. image:: https://img.shields.io/pypi/v/notebookllm
   :target: https://pypi.org/project/notebookllm
   :alt: PyPI

.. image:: https://img.shields.io/pypi/dm/notebookllm
   :target: https://pypi.org/project/notebookllm
   :alt: Downloads

.. note::
   **⚡ Important Update: Unified Agent Experience**
   
   The standalone ``notebookllm-mcp`` server has been natively integrated into the core ``notebookllm`` package. This unification provides a seamless, single-package experience for developers and AI agents alike. The legacy ``notebookllm-mcp`` package is now officially deprecated — please use ``notebookllm[mcp]`` moving forward.

Why?
----

Raw ``.ipynb`` files waste Agent context. The JSON structure, metadata, execution
counts, and base64-encoded image outputs burn tokens without adding value.
``notebookllm`` strips all that noise and produces clean text that AI Agents can
reason over effectively. It also writes notebooks back, enabling Agent-driven
editing workflows.

Features
--------

* **8 notebook formats** — Load and save ``.ipynb``, percent (``# %%``),
  Quarto (``.qmd``), Markdown (``.md``), Marimo (``.py``), R Markdown (``.Rmd``),
  Deepnote (``.deepnote``), and flat scripts.
* **4 output modes** — ``minimal`` (source only), ``standard`` (+ metadata),
  ``full`` (+ outputs), ``token-budget`` (drops cells to fit a token limit).
* **Token counting** — Per-notebook and per-cell token measurement via tiktoken
  (GPT-4) or built-in heuristic fallback. Budget mode drops lowest-priority
  cells automatically.
* **Batch conversion** — Convert multiple files at once with ``--outdir`` for
  auto-named output.
* **Cell operations** — Add, edit, delete, move, and search cells programmatically.
* **Cell execution** — Run code cells via Jupyter kernels (async, thread-pooled).
* **Streaming** — Handle notebooks larger than 10 MB via ``ijson`` streaming.
* **MCP server** — Expose all operations as MCP tools, resources, and prompts
  for AI Agent clients (Claude Desktop, VS Code, Zed, etc.).
* **Output summarization** — DataFrames get shape/column summaries, images get
  size metadata, tracebacks get compressed to the last line.
* **Validation** — Detect orphaned outputs, empty cells, and invalid cell types.
* **Atomic writes** — Crash-safe file saving via temp file + rename.

Installation
------------

.. code-block:: bash

   pip install notebookllm            # core: format conversion, streaming, execution
   pip install notebookllm[cli]       # + CLI (click, rich)
   pip install notebookllm[mcp]       # + MCP server
   pip install notebookllm[token]     # + accurate token counting (tiktoken)
   pip install notebookllm[all]       # everything

The base install includes all core features: format conversion, streaming,
cell execution, and the Python API. Extras add the CLI, MCP server, and
tiktoken-based token counting.

Without ``[token]``, token counting uses a ``len(text)/4`` heuristic — instant
but approximate (±20%). With ``[token]``, it uses GPT-4's ``cl100k_base``
encoding for exact counts.

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

CLI Reference
-------------

All commands support ``--help`` inline documentation.

``notebookllm convert``
^^^^^^^^^^^^^^^^^^^^^^^

Convert notebook(s) between formats or to Agent-optimized text.

**Single file to Agent text (stdout)**:

.. code-block:: bash

   notebookllm convert notebook.ipynb

**Single file to a specific format**:

.. code-block:: bash

   notebookllm convert notebook.ipynb -o output.py -f percent
   notebookllm convert notebook.ipynb -o output.qmd -f quarto

**Output verbosity**:

.. code-block:: bash

   notebookllm convert notebook.ipynb              # minimal (default)
   notebookllm convert notebook.ipynb -m standard  # + metadata
   notebookllm convert notebook.ipynb -m full      # + outputs

**Batch to stdout**:

.. code-block:: bash

   notebookllm convert a.ipynb b.qmd c.py

**Batch to directory** (auto-named ``{stem}_converted.{ext}``):

.. code-block:: bash

   notebookllm convert *.ipynb --outdir ./out
   notebookllm convert a.ipynb b.qmd --outdir ./out -f markdown

``notebookllm inspect``
^^^^^^^^^^^^^^^^^^^^^^^

Show notebook structure — format, language, cell count, and a Rich table
of cells with previews.

.. code-block:: bash

   notebookllm inspect notebook.ipynb

Output example::

   Format: ipynb
   Cells: 12
   Language: python

   ┌───────┬──────────┬──────────────────────────────────────────────┐
   │ Index │   Type   │ Preview                                      │
   ├───────┼──────────┼──────────────────────────────────────────────┤
   │   0   │ markdown │ # Data Analysis Pipeline                     │
   │   1   │   code   │ import pandas as pd                          │
   │   2   │   code   │ def clean_data(df):                          │
   └───────┴──────────┴──────────────────────────────────────────────┘

``notebookllm search``
^^^^^^^^^^^^^^^^^^^^^^

Search cells by content (case-insensitive substring match). Use ``-t``
to filter by cell type (``code``, ``markdown``, ``raw``). Results are
highlighted with Rich markup.

.. code-block:: bash

   notebookllm search notebook.ipynb "import pandas"
   notebookllm search notebook.ipynb "def train" -t code

``notebookllm get``
^^^^^^^^^^^^^^^^^^^

Extract a single cell by its 0-based index. Displays with Rich syntax
highlighting.

.. code-block:: bash

   notebookllm get notebook.ipynb 3

``notebookllm tokens``
^^^^^^^^^^^^^^^^^^^^^^

Estimate token usage for a notebook. Uses tiktoken when the ``[token]``
extra is installed, otherwise falls back to ``len(text)/4``.

.. code-block:: bash

   notebookllm tokens notebook.ipynb              # total tokens
   notebookllm tokens notebook.ipynb --breakdown  # per-cell table
   notebookllm tokens notebook.ipynb -m full      # count with outputs

``notebookllm server``
^^^^^^^^^^^^^^^^^^^^^^

Start the MCP server for AI agent integration. Uses stdio transport by
default (for Claude Desktop, VS Code, Zed). Use ``--transport sse`` for
SSE-based connections.

.. code-block:: bash

   notebookllm server                    # stdio (default)
   notebookllm server --transport sse    # SSE

Python API
----------

Loading and Saving
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from notebookllm import NotebookDocument, load_file, dump_file, loads_text

   # Load (auto-detects format from extension)
   doc = load_file("notebook.ipynb")
   doc = load_file("analysis.qmd")

   # Load from string
   doc = loads_text("# %% [code]\nprint('hi')\n", source_format="percent")

   # Class method
   doc = NotebookDocument.from_file("notebook.ipynb")

   # From text with auto-detection
   doc = NotebookDocument.from_text(text, source_format="quarto")

   # Save
   doc.to_file("output.ipynb")
   doc.to_file("output.py", fmt="percent")
   dump_file(doc, "output.md", fmt="markdown")

   # Serialize/deserialize (CIR JSON)
   json_str = doc.to_json()
   restored = NotebookDocument.from_json(json_str)

Converting to AI Agent Text
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Output Modes
------------

Controls how much detail appears in the Agent-optimized text output:

* **minimal** (default) — ``# %% [type]`` markers + source code only.
  Cleanest for Agent input. Output format::

      # %% [markdown]
      # Data Analysis Pipeline

      # %% [code]
      import pandas as pd
      import numpy as np

* **standard** — Adds execution count and cell metadata tags::

      # %% [code]
      # exec_count: 3
      # tags: preprocessing, data-cleaning
      df = pd.read_csv("data.csv")

* **full** — Adds cell execution outputs (stdout, results, errors)::

      # %% [code]
      print(df.head())
      # --- outputs ---
      # [stdout]    col1  col2
      # 0     1     2

* **token-budget** — Drops lowest-priority cells to stay within a
  ``max_tokens`` budget. Drop order:

  1. Code cells without outputs (scaffolding — dropped first)
  2. Code cells with outputs
  3. Markdown cells (kept longest, never dropped if only one remains)

Output Summarization
--------------------

When using ``token-budget`` mode (or with ``summarize_outputs=True`` via the
:class:`~notebookllm.converters.llm_optimizer.LLMOptimizer` API),
long and rich outputs are compressed:

.. code-block:: python

   from notebookllm.converters.llm_optimizer import LLMOptimizer
   from notebookllm.models import OutputMode

   optimizer = LLMOptimizer(mode=OutputMode.FULL, summarize_outputs=True)
   text = optimizer.optimize(doc)

* **DataFrames**: Shape and column names extracted from the ASCII repr.
  ``# [DataFrame(1000, 5)] Columns: col1, col2, col3 (values hidden)``
* **Images**: MIME type and approximate size.
  ``# [Plot: image/png, ~42KB]``
* **Tracebacks**: Last line only (the actual error message).
  ``# [error] ValueError: invalid literal for int()``
* **Long text**: Truncated at 500 characters with a note.

Token Counting
--------------

Measures notebook token consumption for Agent context planning.

**CLI**: ``notebookllm tokens <file>`` prints total token count.
``--breakdown`` shows a per-cell table with index, type, tokens, and preview.

**Accuracy**: Uses tiktoken (GPT-4 ``cl100k_base`` encoding) when the
``[token]`` extra is installed. Otherwise falls back to ``len(text)/4``
heuristic — fast but approximate.

**Budget mode**: ``doc.to_text(mode="token-budget", max_tokens=5000)``
drops cells to fit within the token limit.

Supported Formats
-----------------

.. list-table::
   :header-rows: 1
   :widths: 14 45 8 8

   * - Extension
     - Format
     - Load
     - Dump
   * - ``.ipynb``
     - Jupyter Notebook
     - Yes
     - Yes
   * - ``.py``
     - Percent (``# %%`` markers)
     - Yes
     - Yes
   * - ``.py``
     - Marimo (``@app.cell`` decorators)
     - Yes
     - Yes
   * - ``.qmd``
     - Quarto documents
     - Yes
     - Yes
   * - ``.md``
     - Markdown with fenced code blocks
     - Yes
     - Yes
   * - ``.Rmd``
     - R Markdown
     - Yes
     - Yes
   * - ``.deepnote``
     - Deepnote YAML project
     - Yes
     - Yes
   * - (none)
     - Flat script (one-way export)
     - No
     - Yes

Large File Streaming
--------------------

Notebooks larger than 10 MB are parsed using ``ijson`` streaming, which
processes cells one at a time without loading the entire JSON into memory.
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
is closed. Available kernels can be listed with:

.. code-block:: bash

   # via MCP server:
   #   list_kernels()

The underlying :class:`~notebookllm.mcp.engine.KernelPool` handles kernel
lifecycle and thread-pooled execution for MCP server sessions.

MCP Server
----------

The MCP server exposes notebook operations for AI Agent clients (Claude Desktop,
VS Code, Zed, etc.).

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
         "args": ["--from", "notebookllm[all]", "notebookllm-server"]
       }
     }
   }

**VS Code** (``.vscode/mcp.json``):

.. code-block:: json

   {
     "mcp": {
       "servers": {
         "notebookllm": {
           "command": "uvx",
           "args": ["--from", "notebookllm[all]", "notebookllm-server"]
         }
       }
     }
   }

Tools (18 unique, 26 with aliases)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 55 15

   * - Tool
     - Description
     - Destructive
   * - ``load`` / ``load_notebook``
     - Load a notebook into a session
     - No
   * - ``create`` / ``create_notebook``
     - Create an empty notebook session
     - No
   * - ``list_sessions``
     - List all active sessions
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
     - Edit an existing cell
     - Yes
   * - ``delete_cell``
     - Delete a cell
     - Yes
   * - ``move_cell``
     - Move a cell
     - No
   * - ``search_cells``
     - Search cells by content
     - No
   * - ``count_tokens``
     - Count tokens in session
     - No
   * - ``convert`` / ``convert_format``
     - Convert to another format
     - No
   * - ``execute`` / ``execute_cell``
     - Execute a code cell (async, thread-pooled)
     - Yes
   * - ``execute_all`` / ``execute_all_cells``
     - Execute all code cells (async)
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
     - Summarize notebook contents
   * - ``review_code(session_id)``
     - Review code quality
   * - ``explain_notebook(session_id)``
     - Explain step by step

Session Management
^^^^^^^^^^^^^^^^^^

The MCP server maintains up to 100 concurrent sessions, persisted in a
local SQLite database at ``~/.local/share/notebookllm/sessions.db``.
Each session has its own kernel (if execution is used). Sessions are
auto-evicted (oldest first) when the limit is reached. Use
``close_session`` to clean up explicitly.

Agent Skill Integration
-----------------------

For autonomous AI agents (like Claude Code, Cursor, GitHub Copilot Workspaces, and Antigravity), ``notebookllm`` includes a native agent skill definition located in ``skills/notebookllm/SKILL.md``. 

This skill document teaches agents exactly how to leverage ``notebookllm`` to manipulate and inspect notebooks efficiently on your behalf. To equip your agent with this skill, simply ensure the ``skills/`` directory is discoverable by your agent's environment, or instruct the agent to read ``skills/notebookllm/SKILL.md`` directly.

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

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

License
-------

MIT
