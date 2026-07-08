Agent Integration & Advanced Features
=====================================

``notebookllm`` is designed from the ground up for agentic workflows, moving beyond simple format conversion to provide a stateful, token-efficient orchestrator for AI Agents (Claude Code, Cursor, GitHub Copilot, etc.).

This guide covers key architectural features that enable high-quality Developer Experience (DX) for agents.

.. _agent_skill:

Agent Skill (SKILL.md)
----------------------

AI agents work best when they are given explicit, structured instructions on how to use tools. ``notebookllm`` ships with a built-in Agent Skill located at:

.. code-block:: text

   skills/notebookllm/SKILL.md

This file defines:
- **Triggers**: When the agent should decide to use ``notebookllm`` (e.g., when requested to inspect a notebook, optimize token budgets, or run cells).
- **CLI Command Syntax**: A quick reference of commands with parameters.
- **API Snippets**: Python usage examples for programmatically manipulating cells.
- **Best Practices**: Rules for agents to conserve token budget using ``token-budget`` mode.

How to equip your agent:
- For **Claude Code** or **Cursor**, add the ``skills/`` folder path to the agent's environment or workspace, allowing the agent to reference the skill guidelines.
- You can prompt the agent: *"Read the skill instructions in skills/notebookllm/SKILL.md to learn how to manage notebooks."*

----

.. _async_execution:

Async Cell Execution
--------------------

For interactive agents to execute code cells in real time, ``notebookllm`` manages Jupyter kernels asynchronously. 

The execution architecture, housed in :class:`~notebookllm.mcp.engine.KernelPool`, ensures thread-safety and performance:

1.  **Non-Blocking Event Loop**: Jupyter's client API is synchronous and blocking. To prevent blocking the main asyncio event loop of the MCP server, ``notebookllm`` delegates execution to background worker threads using ``asyncio.to_thread``.
2.  **Lazy Kernel Lifecycle**: Kernels are not started on boot. Instead, a kernel is spawned lazily the first time an agent requests execution (e.g. `execute_cell` or `execute_all_cells`) for a specific session.
3.  **Stateful Session Management**: Each session's kernel is kept active in the pool. This allows variables, functions, and imports to persist across multiple execution calls.
4.  **Graceful Cleanup**: Kernels are terminated and resources are freed when a session is closed (via the `close_session` MCP tool) or when a session is auto-evicted from the 100-session cache.

**Execution Job Statuses:**
Each execution runs as an ``ExecutionJob`` which tracks states:
- ``running``: The cell is currently executing in the kernel.
- ``completed``: The cell finished execution successfully.
- ``failed``: Execution raised an exception or timed out.

----

.. _output_optimization:

Image & Rich Output Optimization
--------------------------------

Jupyter notebooks often contain large cell outputs, such as base64-encoded PNG/JPEG plots, massive Pandas DataFrames, or multi-page tracebacks. Sending these raw outputs to an AI Agent burns through token context and degrades reasoning.

When using ``token-budget`` mode, or with ``summarize_outputs=True`` via the Python API, ``notebookllm`` automatically intercepts and optimizes rich outputs:

Images and Plots
^^^^^^^^^^^^^^^^

Instead of displaying the raw base64 string, the output summarizer detects image MIME types (``image/png``, ``image/jpeg``, ``image/svg+xml``, ``image/gif``), computes their byte size, and replaces them with a single-line summary:

.. code-block:: python

   # [Plot: image/png, ~42KB]

This gives the agent immediate context that a plot was generated (and its format/size) without wasting thousands of tokens.

Pandas DataFrames
^^^^^^^^^^^^^^^^^

Large dataframes are summarized to prevent tabular data dump. The shape and columns are parsed from the ASCII representation:

.. code-block:: python

   # [DataFrame(1000, 5)] Columns: age, income, city, status, date (values hidden)

Compressing Tracebacks
^^^^^^^^^^^^^^^^^^^^^^

If a code cell execution fails, python tracebacks can span dozens of lines. ``notebookllm`` compresses tracebacks to the last line, exposing the exact exception message and type directly to the agent:

.. code-block:: python

   # [error] ValueError: invalid literal for int() with base 10: 'abc'
