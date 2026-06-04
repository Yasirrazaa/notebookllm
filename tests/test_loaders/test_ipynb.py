"""Tests for notebookllm.loaders.ipynb — .ipynb loader/dumper."""
import json
from pathlib import Path
from notebookllm.loaders.ipynb import IpynbLoader, IpynbDumper, STREAMING_THRESHOLD_BYTES
from notebookllm.models import NotebookDocument, Cell, CellType


FIXTURES = Path(__file__).parent.parent / "fixtures"


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
