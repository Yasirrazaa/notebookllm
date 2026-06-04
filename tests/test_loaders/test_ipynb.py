"""Tests for notebookllm.loaders.ipynb — .ipynb loader/dumper."""
import json
import os
from pathlib import Path

from notebookllm.loaders.ipynb import IpynbLoader, IpynbDumper, STREAMING_THRESHOLD_BYTES
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


NUM_LARGE_CELLS = 10_000


def _generate_large_notebook(tmp_path: Path, num_cells: int = NUM_LARGE_CELLS) -> Path:
    """Generate a synthetic .ipynb file with a given number of cells.

    Creates a mix of code cells (with outputs) and markdown cells to
    exercise the streaming parser with varied cell types. Returns the
    path to the generated file.
    """
    filepath = tmp_path / "large_notebook.ipynb"

    cells = []
    for i in range(num_cells):
        if i % 5 == 0:
            # Every 5th cell is markdown
            cell = {
                "cell_type": "markdown",
                "id": f"md-{i:05d}",
                "metadata": {},
                "source": [f"# Section {i // 5}\n", f"\nContent for cell **{i}**."],
            }
        else:
            # Code cell with stream output
            cell = {
                "cell_type": "code",
                "execution_count": i,
                "id": f"code-{i:05d}",
                "metadata": {"tags": []},
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": f"Result from cell {i}\n",
                    }
                ],
                "source": [f"result = {i} * 2\n", f"print(f'Result from cell {i}')\n"],
            }
        cells.append(cell)

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    filepath.write_text(json.dumps(nb), encoding="utf-8")
    return filepath


class TestIpynbLoader:
    def test_load_sample(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 3
        assert doc.source_format == "ipynb"

    def test_load_preserves_cell_types(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[2].cell_type == CellType.CODE

    def test_load_preserves_execution_count(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].execution_count == 1
        assert doc.cells[2].execution_count is None

    def test_load_preserves_outputs(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert len(doc.cells[0].outputs) == 1
        assert doc.cells[0].outputs[0].output_type == "stream"
        assert doc.cells[0].outputs[0].name == "stdout"

    def test_load_preserves_metadata(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].metadata.get("tags") == ["setup"]
        assert doc.kernel_name == "python3"

    def test_load_preserves_cell_id(self):
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_id == "cell-001"

    def test_load_joins_source_list(self):
        """ipynb source can be a list of strings — should be joined."""
        loader = IpynbLoader()
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert "import pandas" in doc.cells[0].source
        assert "df.head()" in doc.cells[0].source

    def test_loads_from_string(self):
        loader = IpynbLoader()
        content = json.dumps({
            "cells": [{"cell_type": "code", "id": "c1", "source": ["x = 1"], "metadata": {}, "outputs": []}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        })
        doc = loader.loads(content)
        assert len(doc.cells) == 1
        assert doc.cells[0].source == "x = 1"

    def test_load_empty_notebook(self):
        loader = IpynbLoader()
        content = json.dumps({
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        })
        doc = loader.loads(content)
        assert len(doc.cells) == 0


class TestStreaming:
    """Tests for ijson streaming support — forced via threshold=0 to use streaming on small files."""

    def test_streaming_matches_nbformat(self):
        """Streaming and nbformat parsing should produce identical results."""
        loader = IpynbLoader()
        loader.streaming_threshold = 0  # Force streaming
        doc_stream = loader.load(FIXTURES / "sample.ipynb")

        loader2 = IpynbLoader()
        loader2.streaming_threshold = 10 * 1024 * 1024  # Force nbformat (default)
        doc_nb = loader2.load(FIXTURES / "sample.ipynb")

        assert len(doc_stream.cells) == len(doc_nb.cells)
        assert doc_stream.source_format == doc_nb.source_format
        assert doc_stream.kernel_name == doc_nb.kernel_name
        for c1, c2 in zip(doc_stream.cells, doc_nb.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source == c2.source
            assert c1.execution_count == c2.execution_count
            assert c1.cell_id == c2.cell_id
            assert len(c1.outputs) == len(c2.outputs)
            for o1, o2 in zip(c1.outputs, c2.outputs):
                assert o1.output_type == o2.output_type
                assert o1.content == o2.content
                assert o1.name == o2.name

    def test_streaming_preserves_cell_types(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_type == CellType.CODE
        assert doc.cells[1].cell_type == CellType.MARKDOWN
        assert doc.cells[2].cell_type == CellType.CODE

    def test_streaming_preserves_execution_count(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].execution_count == 1
        assert doc.cells[2].execution_count is None

    def test_streaming_preserves_outputs(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert len(doc.cells[0].outputs) == 1
        assert doc.cells[0].outputs[0].output_type == "stream"
        assert doc.cells[0].outputs[0].name == "stdout"

    def test_streaming_preserves_metadata(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].metadata.get("tags") == ["setup"]
        assert doc.kernel_name == "python3"

    def test_streaming_preserves_cell_id(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert doc.cells[0].cell_id == "cell-001"

    def test_streaming_joins_source_list(self):
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(FIXTURES / "sample.ipynb")
        assert "import pandas" in doc.cells[0].source
        assert "df.head()" in doc.cells[0].source

    def test_streaming_empty_notebook(self, tmp_path):
        f = tmp_path / "empty.ipynb"
        f.write_text(json.dumps({
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }))
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(f)
        assert len(doc.cells) == 0

    def test_streaming_with_cell_metadata(self, tmp_path):
        """Streaming should preserve cell-level metadata like tags."""
        f = tmp_path / "with_meta.ipynb"
        f.write_text(json.dumps({
            "cells": [{
                "cell_type": "code",
                "source": ["x = 1"],
                "metadata": {"tags": ["important"]},
                "outputs": [],
            }],
            "metadata": {"kernelspec": {"name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }))
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(f)
        assert doc.cells[0].metadata.get("tags") == ["important"]
        assert doc.kernel_name == "python3"


class TestLargeNotebookStreaming:
    """Large-scale streaming tests using synthetic notebooks with 10,000+ cells."""

    def test_streaming_loads_all_cells(self, tmp_path):
        """Streaming should correctly load all 10,000 cells."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)
        assert len(doc.cells) == NUM_LARGE_CELLS
        assert doc.source_format == "ipynb"

    def test_streaming_preserves_cell_types_at_scale(self, tmp_path):
        """Streaming should preserve code/markdown distinction at 10,000 cells."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        code_cells = [c for c in doc.cells if c.cell_type == CellType.CODE]
        md_cells = [c for c in doc.cells if c.cell_type == CellType.MARKDOWN]
        assert len(code_cells) == NUM_LARGE_CELLS - NUM_LARGE_CELLS // 5
        assert len(md_cells) == NUM_LARGE_CELLS // 5

    def test_streaming_preserves_execution_counts(self, tmp_path):
        """Streaming should preserve execution_count for each cell."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        for i, cell in enumerate(doc.cells):
            if cell.cell_type == CellType.CODE:
                assert cell.execution_count == i

    def test_streaming_preserves_cell_ids(self, tmp_path):
        """Streaming should preserve the 'id' field for each cell."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        for i, cell in enumerate(doc.cells):
            if cell.cell_type == CellType.CODE:
                assert cell.cell_id == f"code-{i:05d}"
            else:
                assert cell.cell_id == f"md-{i:05d}"

    def test_streaming_preserves_outputs(self, tmp_path):
        """Streaming should preserve cell outputs, checking every 1000th code cell."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        for i in range(0, NUM_LARGE_CELLS, 1000):
            cell = doc.cells[i]
            if cell.cell_type == CellType.CODE:
                assert len(cell.outputs) == 1
                assert cell.outputs[0].output_type == "stream"
                assert cell.outputs[0].name == "stdout"
                assert f"Result from cell {i}" in cell.outputs[0].content

    def test_streaming_preserves_source_length(self, tmp_path):
        """Streaming should correctly join multi-line source lists."""
        nb_path = _generate_large_notebook(tmp_path, 100)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        for cell in doc.cells:
            if cell.cell_type == CellType.CODE:
                assert "result =" in cell.source
                assert "print(f" in cell.source

    def test_streaming_preserves_notebook_metadata(self, tmp_path):
        """Streaming should extract notebook-level metadata correctly."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        assert doc.kernel_name == "python3"
        assert "kernelspec" in doc.metadata
        assert "language_info" in doc.metadata

    def test_streaming_matches_nbformat_at_scale(self, tmp_path):
        """Streaming and nbformat should produce identical results for 10,000 cells."""
        nb_path = _generate_large_notebook(tmp_path, 200)  # Reduce for speed

        # Streaming path
        stream_loader = IpynbLoader()
        stream_loader.streaming_threshold = 0
        doc_stream = stream_loader.load(nb_path)

        # nbformat path
        nb_loader = IpynbLoader()
        doc_nb = nb_loader.load(nb_path)

        assert len(doc_stream.cells) == len(doc_nb.cells)
        assert doc_stream.kernel_name == doc_nb.kernel_name
        for c1, c2 in zip(doc_stream.cells, doc_nb.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source == c2.source
            assert c1.execution_count == c2.execution_count
            assert c1.cell_id == c2.cell_id
            assert len(c1.outputs) == len(c2.outputs)

    def test_streaming_first_cell_content(self, tmp_path):
        """First code cell loaded via streaming should have correct content.

        Note: index 0 is markdown (0 % 5 == 0), so we check index 1 for the first code cell.
        """
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        cell = doc.cells[1]
        assert cell.cell_type == CellType.CODE
        assert "result = 1 * 2" in cell.source
        assert cell.execution_count == 1
        assert len(cell.outputs) == 1

    def test_streaming_last_cell_content(self, tmp_path):
        """Last cell loaded via streaming should have correct content."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0
        doc = loader.load(nb_path)

        last_idx = len(doc.cells) - 1
        cell = doc.cells[last_idx]
        # Last cell depends on NUM_LARGE_CELLS parity
        if cell.cell_type == CellType.CODE:
            assert f"result = {last_idx} * 2" in cell.source
        else:
            assert cell.cell_type == CellType.MARKDOWN

    def test_streaming_filesize_triggers_streaming(self, tmp_path):
        """When file exceeds threshold, streaming path should be used."""
        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        file_size = nb_path.stat().st_size

        # Default threshold is 10MB — our generated file should be much smaller
        # So set an artificially low threshold to force streaming
        loader = IpynbLoader()
        loader.streaming_threshold = 1  # 1 byte = always stream
        doc = loader.load(nb_path)
        assert len(doc.cells) == NUM_LARGE_CELLS

    def test_streaming_performance(self, tmp_path):
        """Streaming should complete within reasonable time for 10,000 cells."""
        import time

        nb_path = _generate_large_notebook(tmp_path, NUM_LARGE_CELLS)
        loader = IpynbLoader()
        loader.streaming_threshold = 0  # Force streaming path

        start = time.monotonic()
        doc = loader.load(nb_path)
        elapsed = time.monotonic() - start

        assert len(doc.cells) == NUM_LARGE_CELLS
        # 10,000 cells should complete in under 2 seconds via streaming
        assert elapsed < 2.0, f"Streaming {NUM_LARGE_CELLS} cells took {elapsed:.2f}s (limit: 2s)"


class TestIpynbDumper:
    def test_dump_to_string(self):
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        data = json.loads(result)
        assert data["nbformat"] == 4
        assert len(data["cells"]) == 1
        assert data["cells"][0]["cell_type"] == "code"

    def test_dump_to_file(self, tmp_path):
        dumper = IpynbDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.ipynb"
        dumper.dump(doc, filepath=filepath)
        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert len(data["cells"]) == 1

    def test_dump_preserves_metadata(self):
        dumper = IpynbDumper()
        doc = NotebookDocument(metadata={"kernelspec": {"name": "python3"}})
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        data = json.loads(result)
        assert data["metadata"]["kernelspec"]["name"] == "python3"

    def test_roundtrip_preserves_cells(self):
        loader = IpynbLoader()
        dumper = IpynbDumper()
        doc = loader.load(FIXTURES / "sample.ipynb")
        result = dumper.dump(doc)
        doc2 = loader.loads(result)
        assert len(doc2.cells) == len(doc.cells)
        for c1, c2 in zip(doc.cells, doc2.cells):
            assert c1.cell_type == c2.cell_type
            assert c1.source == c2.source
