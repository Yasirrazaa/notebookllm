"""notebookllm — Convert and optimize Jupyter notebooks for LLMs.

Supports multiple notebook formats:
- .ipynb (Jupyter Notebook)
- .py percent format (# %% markers)
- .py marimo format (@app.cell decorators)
- .qmd (Quarto)
- .md (Markdown with code blocks)
"""

__version__ = "3.0.0"

from notebookllm.loaders import dump_file, load_file, loads_text
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument, OutputMode
from notebookllm.utils.tokenizer import CellTokenInfo, NotebookTokenReport, count_tokens, tokenize_notebook

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
