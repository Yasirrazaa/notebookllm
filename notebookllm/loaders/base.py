"""Abstract base classes for format loaders and dumpers.

Every supported notebook format provides a pair of classes:

- **Loader**: Reads a file (or string) in that format and produces a
  :class:`~notebookllm.models.NotebookDocument`.
- **Dumper**: Takes a :class:`~notebookllm.models.NotebookDocument` and
  serializes it to the format's text representation, optionally writing
  to a file.

New format support is added by subclassing ``BaseLoader`` and ``BaseDumper``
and registering the loader/dumper in :mod:`notebookllm.loaders`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from notebookllm.models import NotebookDocument


class BaseLoader(ABC):
    """Abstract base class for notebook format loaders.

    Subclasses must implement:

    - :meth:`load` — load from a file path.
    - :meth:`loads` — load from a string.
    """

    @abstractmethod
    def load(self, source: str | Path) -> NotebookDocument:
        """Load a notebook from a file path.

        Args:
            source: Path to the notebook file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument` instance.
        """
        ...

    @abstractmethod
    def loads(self, content: str) -> NotebookDocument:
        """Load a notebook from a string.

        Args:
            content: The raw text content of the notebook.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument` instance.
        """
        ...


class BaseDumper(ABC):
    """Abstract base class for notebook format dumpers.

    Subclasses must implement :meth:`dump`.
    """

    @abstractmethod
    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to the target format.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, serialized content is written to this file.

        Returns:
            The serialized notebook as a string.
        """
        ...
