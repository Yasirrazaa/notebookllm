"""notebookllm — Convert, inspect, and optimize Jupyter notebooks for AI Agents.

Provides a unified API for reading, writing, and transforming notebooks across
8+ formats. Supports cell editing, execution, token analysis, and MCP-based
agent integration.

Key capabilities:
- **Format conversion**: Seamlessly convert between .ipynb, .py (percent),
  .py (marimo), .qmd (Quarto), .md, .Rmd, .deepnote, and flat scripts.
- **AI Agent optimization**: Strip JSON noise and produce clean, token-efficient
  text that AI Agents can reason over effectively.
- **Token analysis**: Per-notebook and per-cell token counting via tiktoken
  (GPT-4 encoding) with a budget mode that automatically drops low-priority cells.
- **Cell editing & execution**: Add, edit, delete, move, search, and execute
  code cells — all available via the Python API, CLI, or MCP server.
- **MCP server**: Expose every operation as MCP tools, resources, and prompts
  for AI Agent clients (Claude Desktop, VS Code, Zed, Cursor, etc.).
"""

__version__ = "2.1.0"

from notebookllm.loaders import dump_file, load_file, loads_text
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode
from notebookllm.utils.tokenizer import (
    CellTokenInfo,
    NotebookTokenReport,
    count_tokens,
    tokenize_notebook,
)

__all__ = [
    "NotebookDocument",
    "Cell",
    "CellType",
    "CellOutput",
    "CellTokenInfo",
    "NotebookTokenReport",
    "OutputMode",
    "count_tokens",
    "tokenize_notebook",
    "load_file",
    "dump_file",
    "loads_text",
]
