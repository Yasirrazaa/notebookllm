"""ipynb loader/dumper — Jupyter notebook format."""
from __future__ import annotations

from pathlib import Path

import nbformat

from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument


class IpynbLoader(BaseLoader):
    """Load .ipynb files using nbformat."""

    def load(self, source: str | Path) -> NotebookDocument:
        source = Path(source)
        nb = nbformat.read(str(source), as_version=4)
        return self._convert(nb)

    def loads(self, content: str) -> NotebookDocument:
        nb = nbformat.reads(content, as_version=4)
        return self._convert(nb)

    def _convert(self, nb: nbformat.NotebookNode) -> NotebookDocument:
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

    def _parse_output(self, out: dict) -> CellOutput:
        output_type = out.get("output_type", "unknown")
        if output_type == "stream":
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            return CellOutput(output_type=output_type, content=text, name=out.get("name"))
        elif output_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            content = data.get("text/plain", str(data))
            if isinstance(content, list):
                content = "".join(content)
            return CellOutput(output_type=output_type, content=content)
        elif output_type == "error":
            traceback = out.get("traceback", [])
            content = "\n".join(traceback) if isinstance(traceback, list) else str(traceback)
            return CellOutput(output_type=output_type, content=content)
        else:
            return CellOutput(output_type=output_type, content=str(out))


class IpynbDumper(BaseDumper):
    """Dump to .ipynb format."""

    def dump(self, doc: NotebookDocument, filepath: Path | None = None) -> str | None:
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
        if out.output_type == "stream":
            return nbformat.v4.new_output(
                "stream",
                text=out.content,
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
        return nbformat.v4.new_output(out.output_type, data=str(out.content))
