"""ipynb loader/dumper — Jupyter notebook format (``.ipynb``).

Uses ``nbformat`` for normal-sized files and optional ``ijson`` streaming
for files larger than 10 MB.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import nbformat
from nbformat.notebooknode import NotebookNode

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument

# Default threshold for streaming (10 MB). Files larger than this use ijson streaming.
STREAMING_THRESHOLD_BYTES = 10 * 1024 * 1024


class IpynbLoader(BaseLoader):
    """Load ``.ipynb`` files into :class:`~notebookllm.models.NotebookDocument`.

    For files smaller than :attr:`streaming_threshold`, uses ``nbformat``
    (fast, full in-memory parsing). For larger files, uses ``ijson`` to
    stream-parse cells one at a time, keeping memory usage low.

    Falls back to ``nbformat`` if ``ijson`` is not installed.
    """

    streaming_threshold: int = STREAMING_THRESHOLD_BYTES

    def load(self, source: str | Path) -> NotebookDocument:
        """Load a ``.ipynb`` file from disk.

        Args:
            source: Path to the ``.ipynb`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        file_size = source.stat().st_size

        if file_size >= self.streaming_threshold:
            return self._load_streaming(source, file_size=file_size)

        nb = nbformat.read(str(source), as_version=4)
        return self._convert(nb)

    def loads(self, content: str) -> NotebookDocument:
        """Load a ``.ipynb`` notebook from a JSON string.

        Args:
            content: The raw JSON content of a ``.ipynb`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        nb = nbformat.reads(content, as_version=4)
        return self._convert(nb)

    def _load_streaming(self, filepath: Path, file_size: int | None = None) -> NotebookDocument:
        """Stream-parse a large ``.ipynb`` file using ``ijson``.

        Avoids loading the entire JSON into memory by processing one cell
        at a time. Falls back to ``nbformat`` if ``ijson`` is not installed.

        Args:
            filepath: Path to the ``.ipynb`` file.
            file_size: Known file size (avoids an extra ``stat()`` call).

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        try:
            import ijson  # type: ignore[import-untyped]
        except ImportError:
            # Fall back to nbformat if ijson is not available
            nb = nbformat.read(str(filepath), as_version=4)
            return self._convert(nb)

        # Extract metadata from file tail — pass known file_size to avoid extra stat()
        metadata = self._extract_metadata(filepath, file_size=file_size)
        kernel_name = None
        if "kernelspec" in metadata:
            kernel_name = metadata["kernelspec"].get("name")

        # Stream cells using ijson — processes one cell at a time
        cells = []
        with open(filepath, "rb") as f:
            for cell_dict in ijson.items(f, "cells.item"):
                cells.append(self._cell_from_dict(cell_dict))

        return NotebookDocument(
            cells=cells,
            metadata=metadata,
            kernel_name=kernel_name,
            source_format="ipynb",
        )

    @staticmethod
    def _extract_metadata(filepath: Path, file_size: int | None = None) -> dict:
        """Extract notebook-level metadata by reading the end of the file.

        In ``.ipynb`` format, metadata always appears after the cells array
        and before ``nbformat``/``nbformat_minor``. This method reads the
        last 64 KB of the file (metadata is typically < 1 KB) and extracts
        it without loading the full file into memory.

        .. note::
            Uses brace-depth tracking which may fail if metadata values
            contain unescaped braces (``{`` or ``}``) inside strings. This
            is a known limitation of the heuristic approach — production
            notebooks rarely have such values in notebook-level metadata.

        Args:
            filepath: Path to the ``.ipynb`` file.
            file_size: Known file size (optional, avoids extra ``stat()``).

        Returns:
            The notebook-level metadata dict, or ``{}`` if extraction fails.
        """
        if file_size is None:
            file_size = filepath.stat().st_size
        read_size = min(file_size, 65536)

        with open(filepath, "rb") as f:
            f.seek(file_size - read_size)
            tail = f.read()

        try:
            text = tail.decode("utf-8")
        except UnicodeDecodeError:
            return {}

        # Find the LAST "metadata" key — notebook-level metadata is at the end,
        # after the cells array. Cell-level metadata appears earlier inside each cell.
        meta_key_idx = text.rfind('"metadata"')
        if meta_key_idx < 0:
            return {}

        # Extract the JSON object value for the metadata key
        meta_section = text[meta_key_idx + len('"metadata"'):]
        brace_start = meta_section.find("{")
        if brace_start < 0:
            return {}

        # Track brace depth to find the matching closing brace
        depth = 0
        close_pos = -1
        for i, ch in enumerate(meta_section[brace_start:]):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    close_pos = brace_start + i
                    break

        if close_pos < 0:
            return {}

        try:
            return json.loads(meta_section[brace_start:close_pos + 1])
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _cell_from_dict(cell_dict: dict) -> Cell:
        """Convert a plain dict (from ijson parsing) to a :class:`~notebookllm.models.Cell`.

        Mirrors :meth:`_convert` but works with dicts from ``ijson`` instead
        of ``nbformat.NotebookNode`` objects.

        Args:
            cell_dict: A dict representing one notebook cell.

        Returns:
            A :class:`~notebookllm.models.Cell`.
        """
        source = cell_dict.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        outputs = []
        if cell_dict.get("cell_type") == "code":
            for out in cell_dict.get("outputs", []):
                outputs.append(IpynbLoader._parse_output_static(out))

        metadata = cell_dict.get("metadata", {}) or {}
        cell_id = cell_dict.get("id", None)
        if cell_id is None:
            cell_id = str(uuid.uuid4())

        return Cell(
            cell_type=CellType(cell_dict.get("cell_type", "code")),
            source=source,
            execution_count=cell_dict.get("execution_count", None),
            outputs=outputs,
            metadata=metadata,
            cell_id=cell_id,
        )

    @staticmethod
    def _parse_output_static(out: dict) -> CellOutput:
        """Parse a cell output dict into :class:`~notebookllm.models.CellOutput`.

        Works with both ``nbformat`` output dicts and plain dicts from
        ``ijson``.

        Args:
            out: A dict representing a single cell output.

        Returns:
            A :class:`~notebookllm.models.CellOutput`.
        """
        output_type = out.get("output_type", "unknown")
        if output_type == "stream":
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            return CellOutput(output_type=output_type, content=text, name=out.get("name"))
        elif output_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            # Store the entire MIME bundle (text/plain, text/html, image/png, etc.)
            # as a dict so rich outputs are preserved for FULL mode
            if isinstance(data, dict):
                mime_bundle = {}
                for mime_key, mime_value in data.items():
                    if isinstance(mime_value, list):
                        mime_value = "".join(mime_value)
                    mime_bundle[mime_key] = mime_value
                return CellOutput(output_type=output_type, content=mime_bundle)
            else:
                text_content = data.get("text/plain", str(data))
                if isinstance(text_content, list):
                    text_content = "".join(text_content)
                return CellOutput(output_type=output_type, content=text_content)
        elif output_type == "error":
            traceback = out.get("traceback", [])
            err_content = "\n".join(traceback) if isinstance(traceback, list) else str(traceback)
            return CellOutput(output_type=output_type, content=err_content)
        else:
            return CellOutput(output_type=output_type, content=str(out))

    def _convert(self, nb: nbformat.NotebookNode) -> NotebookDocument:
        """Convert an ``nbformat`` notebook to :class:`~notebookllm.models.NotebookDocument`.

        Args:
            nb: An ``nbformat`` notebook node.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        cells = []
        for nb_cell in nb.cells:
            source = nb_cell.source
            if isinstance(source, list):
                source = "".join(source)

            outputs = []
            if nb_cell.cell_type == "code" and hasattr(nb_cell, "outputs"):
                for out in nb_cell.outputs:
                    outputs.append(self._parse_output(out))

            metadata = dict(nb_cell.metadata) if nb_cell.metadata else {}
            cell_id = getattr(nb_cell, "id", None)
            if cell_id is None:
                cell_id = str(uuid.uuid4())

            cells.append(Cell(
                cell_type=CellType(nb_cell.cell_type),
                source=source,
                execution_count=getattr(nb_cell, "execution_count", None),
                outputs=outputs,
                metadata=metadata,
                cell_id=cell_id,
            ))

        nb_metadata = dict(nb.metadata) if nb.metadata else {}
        kernel_name = None
        if "kernelspec" in nb_metadata:
            kernel_name = nb_metadata["kernelspec"].get("name")

        return NotebookDocument(
            cells=cells,
            metadata=nb_metadata,
            kernel_name=kernel_name,
            source_format="ipynb",
        )

    def _parse_output(self, out: NotebookNode) -> CellOutput:
        """Parse a cell output ``NotebookNode`` into :class:`~notebookllm.models.CellOutput`.

        Args:
            out: A ``nbformat`` output node.

        Returns:
            A :class:`~notebookllm.models.CellOutput`.
        """
        return self._parse_output_static(dict(out))


class IpynbDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to ``.ipynb`` format.

    Produces standard Jupyter notebook JSON, compatible with JupyterLab,
    VS Code, and nbformat v4.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to ``.ipynb`` JSON.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The ``.ipynb`` JSON string.
        """
        nb = nbformat.v4.new_notebook()
        nb.metadata = doc.metadata.copy()
        if doc.kernel_name:
            nb.metadata.setdefault("kernelspec", {})["name"] = doc.kernel_name

        nb.cells = []
        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                nb_cell = nbformat.v4.new_code_cell(source=cell.source)
                nb_cell.execution_count = cell.execution_count
                nb_cell.outputs = [self._dump_output(o) for o in cell.outputs]
            elif cell.cell_type == CellType.MARKDOWN:
                nb_cell = nbformat.v4.new_markdown_cell(source=cell.source)
            elif cell.cell_type == CellType.RAW:
                nb_cell = nbformat.v4.new_raw_cell(source=cell.source)
            else:
                continue

            nb_cell.metadata = cell.metadata.copy()
            if cell.cell_id:
                nb_cell.id = cell.cell_id
            nb.cells.append(nb_cell)

        content = nbformat.writes(nb)
        if filepath:
            filepath.write_text(content, encoding="utf-8")
        return content

    def _dump_output(self, out: CellOutput) -> dict:
        """Convert a :class:`~notebookllm.models.CellOutput` to an ``nbformat`` output dict.

        Args:
            out: The output to convert.

        Returns:
            An ``nbformat``-compatible output dict.
        """
        if out.output_type == "stream":
            text = out.content
            if isinstance(text, list):
                text = "".join(text)
            return nbformat.v4.new_output(
                "stream",
                text=text,
                name=out.name or "stdout",
            )
        elif out.output_type in ("execute_result", "display_data"):
            data = {}
            if isinstance(out.content, str):
                data["text/plain"] = out.content
            else:
                data = out.content
            return nbformat.v4.new_output(out.output_type, data=data)
        elif out.output_type == "error":
            return nbformat.v4.new_output(
                "error",
                traceback=[out.content],
            )
        # Fallback: construct minimal output for unknown types
        fallback = nbformat.v4.new_output("execute_result", data={"text/plain": str(out.content)})
        fallback.output_type = out.output_type
        return fallback
