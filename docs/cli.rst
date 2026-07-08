CLI Reference
=============

``notebookllm`` provides a powerful Command-Line Interface (CLI) built with Click and styled with Rich. It allows you to convert, inspect, search, get cells, count tokens, and launch the Model Context Protocol (MCP) server directly from your terminal.

To use the CLI, make sure you install the CLI extras:

.. code-block:: bash

   pip install notebookllm[cli]

Global Options
--------------

All commands support the following global options:

*   ``--help``: Show the help message and exit.
*   ``--version``: Show the version of ``notebookllm`` and exit.

Commands
--------

notebookllm convert
^^^^^^^^^^^^^^^^^^^

Convert notebooks between formats or to Agent-optimized plain text.

**Usage:**

.. code-block:: bash

   notebookllm convert [OPTIONS] FILES...

**Arguments:**

*   ``FILES``: One or more paths to notebook files (e.g., ``.ipynb``, ``.py``, ``.qmd``, ``.md``). Supports wildcards (e.g., ``*.ipynb``).

**Options:**

*   ``-o, --output PATH``: Path to write the output file (only allowed when converting a single file).
*   ``--outdir PATH``: Output directory (enables batch mode; outputs will be auto-named as ``{stem}_converted{ext}``).
*   ``-f, --format [ipynb|percent|quarto|markdown]``: Explicitly set the target format.
*   ``-m, --mode [minimal|standard|full]``: Select the Agent-optimized plain text output mode:
    *   ``minimal`` (default): Cell markers and source code only.
    *   ``standard``: Cell markers, source code, execution count, and metadata tags.
    *   ``full``: Cell markers, source code, and cell outputs (stdout, results, errors).

**Examples:**

.. code-block:: bash

   # Convert an ipynb file to Agent-optimized text (stdout)
   notebookllm convert analysis.ipynb

   # Convert an ipynb file to a percent script
   notebookllm convert analysis.ipynb -o clean.py -f percent

   # Batch convert all notebooks in a folder to markdown
   notebookllm convert *.ipynb --outdir ./markdown_docs -f markdown

----

notebookllm inspect
^^^^^^^^^^^^^^^^^^^

Inspect the structural metadata of a notebook.

**Usage:**

.. code-block:: bash

   notebookllm inspect [OPTIONS] FILE

**Arguments:**

*   ``FILE``: Path to the notebook file to inspect.

**Output:**

Prints a summary including source format, cell count, and programming language, followed by a formatted Rich table containing every cell's index, type, and source code preview.

**Example:**

.. code-block:: bash

   notebookllm inspect analysis.ipynb

----

notebookllm search
^^^^^^^^^^^^^^^^^^

Search for text across cells in a notebook.

**Usage:**

.. code-block:: bash

   notebookllm search [OPTIONS] FILE QUERY

**Arguments:**

*   ``FILE``: Path to the notebook file to search.
*   ``QUERY``: Text query to search for (case-insensitive substring match).

**Options:**

*   ``-t, --type [code|markdown|raw]``: Filter the search to specific cell types.

**Output:**

Prints a Rich table showing matching cell indices, types, and previews with the query term highlighted.

**Example:**

.. code-block:: bash

   notebookllm search analysis.ipynb "import pandas" --type code

----

notebookllm get
^^^^^^^^^^^^^^^

Retrieve the raw source code of a specific cell.

**Usage:**

.. code-block:: bash

   notebookllm get [OPTIONS] FILE INDEX

**Arguments:**

*   ``FILE``: Path to the notebook file.
*   ``INDEX``: The 0-based index of the cell.

**Output:**

Prints the cell header followed by the syntax-highlighted source code of the requested cell.

**Example:**

.. code-block:: bash

   notebookllm get analysis.ipynb 3

----

notebookllm tokens
^^^^^^^^^^^^^^^^^^

Estimate token consumption for AI Agent context planning.

**Usage:**

.. code-block:: bash

   notebookllm tokens [OPTIONS] FILE

**Arguments:**

*   ``FILE``: Path to the notebook file.

**Options:**

*   ``-m, --mode [minimal|standard|full]``: Select output mode for token estimation.
*   ``--breakdown``: Show a per-cell token usage breakdown table.

**Example:**

.. code-block:: bash

   notebookllm tokens analysis.ipynb --breakdown --mode full

----

notebookllm server
^^^^^^^^^^^^^^^^^^

Start the Model Context Protocol (MCP) server.

**Usage:**

.. code-block:: bash

   notebookllm server [OPTIONS]

**Options:**

*   ``--transport [stdio|sse]``: Choose the transport layer. Defaults to ``stdio`` (standard input/output), which is used by desktop agents like Claude Desktop, Cursor, and Zed. Use ``sse`` (Server-Sent Events) for remote network connections.

**Example:**

.. code-block:: bash

   notebookllm server --transport stdio
