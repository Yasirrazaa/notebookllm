"""Sphinx configuration for notebookllm."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(".."))


project = "notebookllm"
copyright = "2024, Yasir Raza"
author = "Yasir Raza"
release = "2.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path: list[str] = []
