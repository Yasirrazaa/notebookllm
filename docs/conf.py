"""Sphinx configuration for notebookllm documentation."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "notebookllm"
copyright = "2026, Yasir Raza"
author = "Yasir Raza"
release = "2.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "superpowers"]

html_theme = "sphinx_rtd_theme"
html_static_path: list[str] = []

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_attr_annotations = True
