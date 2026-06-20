"""Abstract base classes for format loaders and dumpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from notebookllm.models import NotebookDocument


class BaseLoader(ABC):
    """Abstract base class for format loaders."""

    @abstractmethod
    def load(self, source: str | Path) -> NotebookDocument:
        """Load a notebook from a file path."""
        ...

    @abstractmethod
    def loads(self, content: str) -> NotebookDocument:
        """Load a notebook from a string."""
        ...


class BaseDumper(ABC):
    """Abstract base class for format dumpers."""

    @abstractmethod
    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Dump a notebook to string, optionally writing to file."""
        ...