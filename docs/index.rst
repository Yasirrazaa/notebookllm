notebookllm
===========

Convert, inspect, and optimize Jupyter notebooks for **AI Agents** — Claude Code,
Cursor, GitHub Copilot, Claude Desktop, VS Code, Zed, and more.

``notebookllm`` converts notebooks to a clean, token-efficient format,
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

   The standalone ``notebookllm-mcp`` package has been fully merged into the core
   ``notebookllm`` package. Both the Python library and MCP server now ship together.
   The legacy ``notebookllm-mcp`` package is **deprecated** — install
   ``notebookllm[mcp]`` to get everything.

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   cli
   agent_integration
   api

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
* **Smart token budget** — Automatically drops lowest-priority cells to stay
  within an Agent's context window.
* **Token counting** — Per-notebook and per-cell token measurement via tiktoken
  (GPT-4 ``cl100k_base`` encoding) or built-in heuristic fallback.
* **Batch conversion** — Convert multiple files at once with ``--outdir`` for
  auto-named output.
* **Cell operations** — Add, edit, delete, move, and search cells programmatically.
* **Async cell execution** — Run code cells via Jupyter kernels (thread-pooled,
  non-blocking, stateful across calls).
* **Output summarization** — Images get size metadata, DataFrames get shape/column
  summaries, tracebacks are compressed to the last line.
* **Streaming** — Handle notebooks larger than 10 MB via ``ijson`` streaming
  (cell-by-cell, no memory spike).
* **MCP server** — Expose all operations as MCP tools, resources, and prompts
  for AI Agent clients (Claude Desktop, VS Code, Zed, Cursor, Claude Code).
* **Validation** — Detect orphaned outputs, empty cells, and invalid cell types.
* **Atomic writes** — Crash-safe file saving via temp file + rename.
* **Agent Skill** — Ships with a native ``SKILL.md`` for Claude Code, Cursor,
  and Antigravity agents.

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

**CLI:**

.. code-block:: bash

   # Convert to optimized text for agents (stdout)
   notebookllm convert notebook.ipynb

   # Convert between formats
   notebookllm convert notebook.ipynb -o output.py -f percent

   # Count tokens per cell
   notebookllm tokens notebook.ipynb --breakdown

   # Inspect notebook structure
   notebookllm inspect notebook.ipynb

See the full :doc:`cli` reference for all commands and options.

**Python API:**

.. code-block:: python

   from notebookllm import load_file, OutputMode

   doc = load_file("notebook.ipynb")
   print(doc.to_text())                                      # minimal (default)
   print(doc.to_text(mode=OutputMode.FULL))                  # + cell outputs
   print(doc.to_text(mode="token-budget", max_tokens=2000))  # budget mode

**MCP Server:**

.. code-block:: bash

   notebookllm server          # stdio transport (Claude Desktop, Cursor, Zed)
   notebookllm server --transport sse  # SSE transport (remote connections)

---

Output Modes
------------

Controls how much detail appears in the optimized output:

``minimal`` (default)
   ``# %% [type]`` markers + source code only — cleanest for agents::

      # %% [markdown]
      # Data Analysis Pipeline

      # %% [code]
      import pandas as pd

``standard``
   Adds execution count and cell metadata tags::

      # %% [code]
      # exec_count: 3
      # tags: preprocessing
      df = pd.read_csv("data.csv")

``full``
   Adds cell execution outputs (stdout, results, errors)::

      # %% [code]
      print(df.head())
      # --- outputs ---
      # [stdout]    col1  col2
      # 0     1     2

``token-budget``
   Drops lowest-priority cells first to stay within a ``max_tokens`` limit.
   Drop order: code cells without outputs → code cells with outputs → markdown.

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

---

MCP Server
----------

The MCP server exposes all notebook operations as MCP tools, resources, and
prompts for AI Agent clients (Claude Desktop, VS Code, Zed, Cursor, Claude Code).

Setup
^^^^^

.. code-block:: bash

   notebookllm server                   # stdio (default)
   notebookllm server --transport sse   # SSE

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

To pin a specific version:

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

**VS Code** (``.vscode/mcp.json``):

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

**Zed** (``~/.config/zed/mcp.json``):

.. code-block:: json

    {
      "notebookllm": {
        "command": "uvx",
        "args": ["notebookllm-server"]
      }
    }

Tools
^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 55 10

   * - Tool / Aliases
     - Description
     - Modifies
   * - ``load`` / ``load_notebook``
     - Load a notebook into a session
     - No
   * - ``create`` / ``create_notebook``
     - Create an empty notebook session in memory
     - No
   * - ``list_sessions``
     - List all active sessions with cell counts
     - No
   * - ``close_session``
     - Close session and free its kernel
     - No
   * - ``save`` / ``save_notebook``
     - Save session to file (atomic write)
     - Yes
   * - ``to_text``
     - Convert to optimized text for agents (supports ``max_tokens``)
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
     - Edit an existing cell's source or type
     - Yes
   * - ``delete_cell``
     - Delete a cell by index
     - Yes
   * - ``move_cell``
     - Move a cell between positions
     - No
   * - ``search_cells``
     - Search cells by content (case-insensitive)
     - No
   * - ``count_tokens``
     - Count tokens in the session notebook
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
     - Full notebook as optimized text for agents
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
local SQLite database at ``~/.local/share/notebookllm/sessions.db``. Sessions
have optional Jupyter kernels (if execution is used). Sessions survive server
restarts — use ``close_session`` to clean up explicitly.

---

Agent Skill Integration
-----------------------

For autonomous AI Agents (Claude Code, Cursor, Claude Desktop, GitHub Copilot
Workspaces, Antigravity), ``notebookllm`` ships with a **native agent skill** at
``skills/notebookllm/SKILL.md``.

This file teaches agents exactly when and how to use ``notebookllm`` — covering
CLI commands, Python API, output modes, token counting, format conversion, and
MCP server integration. See :doc:`agent_integration` for the full guide.

---

Development
-----------

.. code-block:: bash

   git clone https://github.com/yasirrazaa/notebookllm.git
   cd notebookllm
   uv sync && uv pip install -e ".[dev]"

   uv run pytest                      # run tests
   uv run pytest --cov=notebookllm    # with coverage
   uv run pytest tests/benchmarks --benchmark-only  # benchmarks
   uv run ruff check .                # lint
   uv run mypy notebookllm            # type check
   uv run sphinx-build -b html -E docs docs/_build/html  # build docs

---

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

License
-------

MIT
