"""Deepnote YAML loader/dumper — ``.deepnote`` project format.

Deepnote (https://deepnote.com) is a collaborative data science platform.
Projects are stored as YAML files with a rich block-based structure that
includes code, markdown, SQL, charts, visualizations, and more.

This loader/dumper maps Deepnote blocks onto the universal
:class:`~notebookllm.models.Cell` model, preserving Deepnote-specific
fields like ``block_type``, ``block_group``, ``content_hash``, and
``sorting_key``.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

import yaml

from notebookllm.loaders.base import BaseDumper, BaseLoader
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument

# Standard Deepnote block types and their mapping to CellType
DEEPNOTE_TYPE_MAP: dict[str, CellType] = {
    "code": CellType.CODE,
    "markdown": CellType.MARKDOWN,
    "sql": CellType.CODE,
    "chart": CellType.CODE,
    "input": CellType.CODE,
    "visualization": CellType.CODE,
    "raw": CellType.RAW,
    "divider": CellType.RAW,
    "big_number": CellType.CODE,
    "data_frame_viewer": CellType.CODE,
    "rich_text": CellType.MARKDOWN,
}

# Block types that should be tracked as custom block_type in metadata
CUSTOM_BLOCK_TYPES = {
    "sql", "chart", "input", "visualization",
    "big_number", "data_frame_viewer", "divider", "rich_text",
}

# Reverse mapping: CellType -> default Deepnote block type
REVERSE_TYPE_MAP: dict[CellType, str] = {
    CellType.CODE: "code",
    CellType.MARKDOWN: "markdown",
    CellType.RAW: "raw",
}


def _block_type_to_cell_type(block_type: str) -> CellType:
    """Map a Deepnote block type string to a :class:`~notebookllm.models.CellType`.

    Args:
        block_type: Deepnote block type (e.g. ``"code"``, ``"sql"``, ``"chart"``).

    Returns:
        The corresponding :class:`~notebookllm.models.CellType`.
    """
    return DEEPNOTE_TYPE_MAP.get(block_type, CellType.CODE)


def _deepnote_to_cell_output(output: dict) -> CellOutput:
    """Convert a Deepnote block output dict to :class:`~notebookllm.models.CellOutput`.

    Args:
        output: A Deepnote output dict.

    Returns:
        A :class:`~notebookllm.models.CellOutput`.
    """
    return CellOutput(
        output_type=output.get("output_type", "execute_result"),
        content=output.get("data") or output.get("text") or output.get("name") or "",
        name=output.get("name"),
    )


def _cell_output_to_deepnote(output: CellOutput) -> dict:
    """Convert :class:`~notebookllm.models.CellOutput` to a Deepnote block output dict.

    Args:
        output: The cell output to convert.

    Returns:
        A Deepnote-compatible output dict.
    """
    d: dict[str, Any] = {"output_type": output.output_type}
    if output.output_type == "stream":
        d["name"] = output.name or "stdout"
        d["text"] = str(output.content)
    elif output.output_type == "error":
        d["ename"] = "Error"
        d["evalue"] = str(output.content)
        d["traceback"] = []
    else:
        d["data"] = output.content if isinstance(output.content, dict) else {"text/plain": str(output.content)}
    return d


def _compute_content_hash(content: str) -> str:
    """Compute a SHA-256 content hash (first 16 hex characters).

    Args:
        content: The content to hash.

    Returns:
        A 16-character hex string.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class DeepnoteLoader(BaseLoader):
    """Load ``.deepnote`` YAML project files.

    Reads the Deepnote YAML structure, iterates over notebooks and their
    blocks, and converts each block to a :class:`~notebookllm.models.Cell`.
    Preserves Deepnote-specific metadata (block groups, content hashes,
    sorting keys) on the Cell objects.
    """

    def load(self, source: str | Path) -> NotebookDocument:
        """Load a Deepnote YAML file from disk.

        Args:
            source: Path to the ``.deepnote`` file.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
        """Load a Deepnote project from a YAML string.

        Args:
            content: The raw YAML content.

        Returns:
            A :class:`~notebookllm.models.NotebookDocument`.
        """
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return NotebookDocument(cells=[], source_format="deepnote")

        cells = []
        project = data.get("project", {})
        notebooks = project.get("notebooks", [])

        for notebook in notebooks:
            notebook_name = notebook.get("name", "Untitled")
            notebook_id = notebook.get("id", str(uuid.uuid4()))
            blocks = notebook.get("blocks", [])

            for block in blocks:
                cell = self._block_to_cell(block, notebook_name, notebook_id)
                cells.append(cell)

        metadata: dict[str, Any] = {}
        if "metadata" in data:
            metadata["deepnote_metadata"] = data["metadata"]
        if "settings" in project:
            metadata["deepnote_settings"] = project["settings"]
        if "integrations" in project:
            metadata["deepnote_integrations"] = project["integrations"]

        return NotebookDocument(cells=cells, source_format="deepnote", metadata=metadata)

    def _block_to_cell(self, block: dict, notebook_name: str, notebook_id: str) -> Cell:
        """Convert a Deepnote block dict to a :class:`~notebookllm.models.Cell`.

        Args:
            block: A Deepnote block dict.
            notebook_name: Name of the parent notebook.
            notebook_id: ID of the parent notebook.

        Returns:
            A :class:`~notebookllm.models.Cell`.
        """
        block_type = block.get("type", "code")
        cell_type = _block_type_to_cell_type(block_type)
        content = block.get("content", "")

        meta: dict[str, Any] = {}
        if block_type in CUSTOM_BLOCK_TYPES:
            meta["block_type"] = block_type
        if block.get("blockGroup"):
            meta["block_group"] = block["blockGroup"]
        if block.get("sortingKey"):
            meta["sorting_key"] = block["sortingKey"]
        meta["notebook_name"] = notebook_name
        meta["notebook_id"] = notebook_id

        block_meta = block.get("metadata") or {}
        for k, v in block_meta.items():
            if k not in meta:
                meta[k] = v

        content_hash = block.get("contentHash") or _compute_content_hash(content)

        outputs = []
        for out in block.get("outputs") or []:
            outputs.append(_deepnote_to_cell_output(out))

        exec_count = block.get("executionCount")
        language = block.get("language") or meta.get("language")

        return Cell(
            cell_id=block.get("id", str(uuid.uuid4())),
            source=content,
            cell_type=cell_type,
            execution_count=exec_count,
            metadata=meta,
            outputs=outputs,
            content_hash=content_hash,
            sorting_key=meta.get("sorting_key"),
            block_group=meta.get("block_group"),
            language=language,
        )


class DeepnoteDumper(BaseDumper):
    """Dump :class:`~notebookllm.models.NotebookDocument` to Deepnote YAML format.

    Groups cells by ``notebook_name`` metadata, sorts blocks by
    ``sorting_key``, and produces a valid Deepnote project YAML file.
    """

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        """Serialize a notebook to Deepnote YAML format.

        Args:
            doc: The notebook to serialize.
            filepath: If provided, write the output to this file.

        Returns:
            The Deepnote YAML content as a string.
        """
        yaml_str = self._to_yaml(doc)
        if filepath:
            filepath.write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def _to_yaml(self, doc: NotebookDocument) -> str:
        """Convert a notebook document to a Deepnote YAML string.

        Args:
            doc: The notebook document.

        Returns:
            The YAML string.
        """
        notebooks_map: dict[str, list[Cell]] = {}
        for cell in doc.cells:
            nb_name = cell.metadata.get("notebook_name") if isinstance(cell.metadata, dict) else None
            nb_name = nb_name or "Notebook"
            notebooks_map.setdefault(nb_name, []).append(cell)

        notebooks = []
        for nb_name, cells in notebooks_map.items():
            blocks = []
            for cell in cells:
                block = self._cell_to_block(cell)
                blocks.append(block)

            blocks.sort(key=lambda b: (b.get("sortingKey") or "0"))

            notebook: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "name": nb_name,
                "blocks": blocks,
                "executionMode": "downstream",
                "isModule": False,
            }

            first_cell = cells[0] if cells else None
            if first_cell and isinstance(first_cell.metadata, dict) and first_cell.metadata.get("notebook_id"):
                notebook["id"] = first_cell.metadata["notebook_id"]

            notebooks.append(notebook)

        deepnote_settings = {}
        deepnote_integrations = []
        if doc.metadata:
            if isinstance(doc.metadata, dict):
                deepnote_settings = doc.metadata.get("deepnote_settings", {})
                deepnote_integrations = doc.metadata.get("deepnote_integrations", [])

        data: dict[str, Any] = {
            "metadata": {
                "version": "1.0.0",
            },
            "project": {
                "id": str(uuid.uuid4()),
                "name": "NotebookLLM Project",
                "notebooks": notebooks,
            },
        }

        if deepnote_integrations:
            data["project"]["integrations"] = deepnote_integrations
        if deepnote_settings:
            data["project"]["settings"] = deepnote_settings

        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _cell_to_block(self, cell: Cell) -> dict:
        """Convert a :class:`~notebookllm.models.Cell` to a Deepnote block dict.

        Args:
            cell: The cell to convert.

        Returns:
            A Deepnote-compatible block dict.
        """
        meta = cell.metadata if isinstance(cell.metadata, dict) else {}

        block_type = meta.get("block_type")
        if not block_type:
            block_type = REVERSE_TYPE_MAP.get(cell.cell_type, "code")

        block: dict[str, Any] = {
            "id": cell.cell_id or str(uuid.uuid4()),
            "type": block_type,
            "sortingKey": cell.sorting_key or meta.get("sorting_key") or "0",
            "content": cell.source,
            "version": 1,
            "metadata": {},
        }

        if cell.block_group or meta.get("block_group"):
            block["blockGroup"] = cell.block_group or meta["block_group"]
        if cell.execution_count is not None:
            block["executionCount"] = cell.execution_count
        if cell.language:
            block["language"] = cell.language
        if cell.content_hash:
            block["contentHash"] = cell.content_hash

        if cell.outputs:
            block["outputs"] = [_cell_output_to_deepnote(out) for out in cell.outputs]

        skip_keys = {
            "block_type", "block_group", "sorting_key", "content_hash",
            "notebook_name", "notebook_id",
        }
        extra_meta = {k: v for k, v in meta.items() if k not in skip_keys}
        if extra_meta:
            block["metadata"].update(extra_meta)

        return block
