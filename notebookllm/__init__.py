"""notebookllm — Convert and optimize Jupyter notebooks for LLMs.

Supports multiple notebook formats:
- .ipynb (Jupyter Notebook)
- .py percent format (# %% markers)
- .py marimo format (@app.cell decorators)
- .qmd (Quarto)
- .md (Markdown with code blocks)
"""

__version__ = "3.0.0"

from notebookllm.models import NotebookDocument, Cell, CellType, CellOutput, OutputMode
from notebookllm.loaders import load_file, dump_file, loads_text

__all__ = [
    "NotebookDocument",
    "Cell",
    "CellType",
    "CellOutput",
    "OutputMode",
    "load_file",
    "dump_file",
    "loads_text",
]
