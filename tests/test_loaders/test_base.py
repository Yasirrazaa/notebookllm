"""Tests for notebookllm.loaders.base — abstract base classes."""
import pytest
from notebookllm.loaders.base import BaseLoader, BaseDumper
from notebookllm.models import NotebookDocument, Cell, CellType


class ConcreteLoader(BaseLoader):
    """Concrete loader for testing abstract base."""

    def load(self, source):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        return doc

    def loads(self, content):
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source=content))
        return doc


class ConcreteDumper(BaseDumper):
    """Concrete dumper for testing abstract base."""

    def dump(self, doc, filepath=None):
        lines = []
        for cell in doc.cells:
            lines.append(f"# %% [{cell.cell_type.value}]")
            lines.append(cell.source)
        result = "\n".join(lines)
        if filepath:
            filepath.write_text(result)
        return result


class TestBaseLoader:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseLoader()

    def test_concrete_loader_load(self):
        loader = ConcreteLoader()
        doc = loader.load("fake.ipynb")
        assert isinstance(doc, NotebookDocument)
        assert len(doc.cells) == 1

    def test_concrete_loader_loads(self):
        loader = ConcreteLoader()
        doc = loader.loads("print('hello')")
        assert doc.cells[0].source == "print('hello')"


class TestBaseDumper:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseDumper()

    def test_concrete_dumper_dump_to_string(self):
        dumper = ConcreteDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        result = dumper.dump(doc)
        assert "# %% [code]" in result
        assert "x = 1" in result

    def test_concrete_dumper_dump_to_file(self, tmp_path):
        dumper = ConcreteDumper()
        doc = NotebookDocument()
        doc.add_cell(Cell(cell_type=CellType.CODE, source="x = 1"))
        filepath = tmp_path / "output.py"
        result = dumper.dump(doc, filepath=filepath)
        assert filepath.read_text() == result