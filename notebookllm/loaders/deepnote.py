"""Deepnote YAML loader/dumper — .deepnote project format."""
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

# Reverse mapping: CellType → default Deepnote block type
REVERSE_TYPE_MAP: dict[CellType, str] = {
    CellType.CODE: "code",
    CellType.MARKDOWN: "markdown",
    CellType.RAW: "raw",
}


def _block_type_to_cell_type(block_type: str) -> CellType:
    """Map Deepnote block type to standard CellType."""
    return DEEPNOTE_TYPE_MAP.get(block_type, CellType.CODE)


def _deepnote_to_cell_output(output: dict) -> CellOutput:
    """Convert a Deepnote block output dict to CellOutput."""
    return CellOutput(
        output_type=output.get("output_type", "execute_result"),
        content=output.get("data") or output.get("text") or output.get("name") or "",
        name=output.get("name"),
    )


def _cell_output_to_deepnote(output: CellOutput) -> dict:
    """Convert CellOutput to Deepnote block output dict."""
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
    """Compute SHA-256 content hash (first 16 hex chars)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class DeepnoteLoader(BaseLoader):
    """Load .deepnote YAML project files."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        content = source.read_text(encoding="utf-8")
        return self.loads(content)

    def loads(self, content: str) -> NotebookDocument:
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

        # Preserve project-level metadata
        metadata: dict[str, Any] = {}
        if "metadata" in data:
            metadata["deepnote_metadata"] = data["metadata"]
        if "settings" in project:
            metadata["deepnote_settings"] = project["settings"]
        if "integrations" in project:
            metadata["deepnote_integrations"] = project["integrations"]

        return NotebookDocument(cells=cells, source_format="deepnote", metadata=metadata)

    def _block_to_cell(self, block: dict, notebook_name: str, notebook_id: str) -> Cell:
        """Convert a Deepnote block dict to Cell."""
        block_type = block.get("type", "code")
        cell_type = _block_type_to_cell_type(block_type)
        content = block.get("content", "")

        # Build metadata
        meta: dict[str, Any] = {}
        if block_type in CUSTOM_BLOCK_TYPES:
            meta["block_type"] = block_type
        if block.get("blockGroup"):
            meta["block_group"] = block["blockGroup"]
        if block.get("sortingKey"):
            meta["sorting_key"] = block["sortingKey"]
        meta["notebook_name"] = notebook_name
        meta["notebook_id"] = notebook_id

        # Merge any extra block metadata
        block_meta = block.get("metadata") or {}
        for k, v in block_meta.items():
            if k not in meta:
                meta[k] = v

        # Compute content hash
        content_hash = block.get("contentHash") or _compute_content_hash(content)

        # Map outputs
        outputs = []
        for out in block.get("outputs") or []:
            outputs.append(_deepnote_to_cell_output(out))

        # Determine execution count
        exec_count = block.get("executionCount")

        # Determine language
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
    """Dump NotebookDocument to .deepnote YAML format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str:
        yaml_str = self._to_yaml(doc)
        if filepath:
            filepath.write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def _to_yaml(self, doc: NotebookDocument) -> str:
        """Convert notebook doc to Deepnote YAML string."""
        # Group cells by notebook_name
        notebooks_map: dict[str, list[Cell]] = {}
        for cell in doc.cells:
            nb_name = cell.metadata.get("notebook_name") if isinstance(cell.metadata, dict) else None
            nb_name = nb_name or "Notebook"
            notebooks_map.setdefault(nb_name, []).append(cell)

        # Build notebooks list
        notebooks = []
        for nb_name, cells in notebooks_map.items():
            blocks = []
            for cell in cells:
                block = self._cell_to_block(cell)
                blocks.append(block)

            # Sort blocks by sorting_key
            blocks.sort(key=lambda b: (b.get("sortingKey") or "0"))

            notebook: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "name": nb_name,
                "blocks": blocks,
                "executionMode": "downstream",
                "isModule": False,
            }

            # Preserve original notebook_id if available
            first_cell = cells[0] if cells else None
            if first_cell and isinstance(first_cell.metadata, dict) and first_cell.metadata.get("notebook_id"):
                notebook["id"] = first_cell.metadata["notebook_id"]

            notebooks.append(notebook)

        # Extract project-level metadata
        deepnote_settings = {}
        deepnote_integrations = []
        if doc.metadata:
            if isinstance(doc.metadata, dict):
                deepnote_settings = doc.metadata.get("deepnote_settings", {})
                deepnote_integrations = doc.metadata.get("deepnote_integrations", [])

        # Build top-level structure
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
        """Convert Cell to Deepnote block dict."""
        meta = cell.metadata if isinstance(cell.metadata, dict) else {}

        # Determine block type
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

        # Add optional fields
        if cell.block_group or meta.get("block_group"):
            block["blockGroup"] = cell.block_group or meta["block_group"]
        if cell.execution_count is not None:
            block["executionCount"] = cell.execution_count
        if cell.language:
            block["language"] = cell.language
        if cell.content_hash:
            block["contentHash"] = cell.content_hash

        # Convert outputs
        if cell.outputs:
            block["outputs"] = [_cell_output_to_deepnote(out) for out in cell.outputs]

        # Preserve extra metadata (exclude internal fields)
        skip_keys = {
            "block_type", "block_group", "sorting_key", "content_hash",
            "notebook_name", "notebook_id",
        }
        extra_meta = {k: v for k, v in meta.items() if k not in skip_keys}
        if extra_meta:
            block["metadata"].update(extra_meta)

        return block
