"""Tests for Deepnote YAML loader/dumper."""
from __future__ import annotations

import textwrap
import uuid
from pathlib import Path

import pytest
import yaml

from notebookllm.loaders.deepnote import DeepnoteDumper, DeepnoteLoader
from notebookllm.models import Cell, CellOutput, CellType, NotebookDocument


@pytest.fixture
def sample_yaml():
    return textwrap.dedent("""\
        metadata:
          version: "1.0.0"
          createdAt: "2025-01-27T12:00:00Z"
        project:
          id: "proj-001"
          name: "Test Project"
          notebooks:
            - id: "nb-001"
              name: "Analysis"
              executionMode: "block"
              isModule: false
              blocks:
                - id: "blk-001"
                  type: "markdown"
                  sortingKey: "1"
                  content: |
                    # Title
                    Hello world
                  version: 1
                  metadata: {}
                - id: "blk-002"
                  type: "code"
                  sortingKey: "2"
                  content: |
                    import pandas as pd
                    df = pd.DataFrame({"x": [1, 2, 3]})
                  version: 1
                  metadata:
                    key: "value"
                  outputs:
                    - output_type: "execute_result"
                      data:
                        text/plain: "   x\\n0  1\\n1  2\\n2  3"
                - id: "blk-003"
                  type: "sql"
                  sortingKey: "3"
                  content: "SELECT * FROM users"
                  blockGroup: "grp-001"
                  version: 1
                  metadata: {}
          integrations:
            - id: "int-001"
              name: "Snowflake"
              type: "snowflake"
          settings:
            environment:
              pythonVersion: "3.11"
    """)


class TestDeepnoteLoader:
    def test_load_basic(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert doc.source_format == "deepnote"
        assert len(doc.cells) == 3

    def test_cell_types(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert doc.cells[0].cell_type == CellType.MARKDOWN
        assert doc.cells[1].cell_type == CellType.CODE
        assert doc.cells[2].cell_type == CellType.CODE  # sql → CODE

    def test_cell_content(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert "Hello world" in doc.cells[0].source
        assert "pd.DataFrame" in doc.cells[1].source
        assert "SELECT" in doc.cells[2].source

    def test_custom_block_type(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        # sql block should have block_type in metadata
        assert doc.cells[2].metadata.get("block_type") == "sql"

    def test_block_group_and_sorting_key(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert doc.cells[0].sorting_key == "1"
        assert doc.cells[1].sorting_key == "2"
        assert doc.cells[2].sorting_key == "3"
        assert doc.cells[2].block_group == "grp-001"

    def test_notebook_name_in_metadata(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        for cell in doc.cells:
            assert cell.metadata.get("notebook_name") == "Analysis"

    def test_outputs(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert len(doc.cells[1].outputs) == 1
        out = doc.cells[1].outputs[0]
        assert out.output_type == "execute_result"
        assert "text/plain" in out.content if isinstance(out.content, dict) else True

    def test_content_hash(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert doc.cells[0].content_hash is not None
        assert len(doc.cells[0].content_hash) == 16  # SHA-256 first 16 chars

    def test_cell_ids(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert doc.cells[0].cell_id == "blk-001"
        assert doc.cells[1].cell_id == "blk-002"
        assert doc.cells[2].cell_id == "blk-003"

    def test_language_field(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        for cell in doc.cells:
            assert cell.language is None  # no language in sample

    def test_language_from_block(self):
        yaml_str = textwrap.dedent("""\
            project:
              notebooks:
                - id: "nb-001"
                  name: "NB"
                  blocks:
                    - id: "blk-001"
                      type: "code"
                      sortingKey: "1"
                      content: "print('hi')"
                      language: "r"
                      version: 1
                      metadata: {}
        """)
        doc = DeepnoteLoader().loads(yaml_str)
        assert doc.cells[0].language == "r"

    def test_empty_yaml(self):
        doc = DeepnoteLoader().loads("")
        assert len(doc.cells) == 0

    def test_no_notebooks(self):
        yaml_str = "project:\n  notebooks: []\n"
        doc = DeepnoteLoader().loads(yaml_str)
        assert len(doc.cells) == 0

    def test_multi_notebook(self):
        yaml_str = textwrap.dedent("""\
            project:
              notebooks:
                - id: "nb-001"
                  name: "Data Prep"
                  blocks:
                    - id: "blk-001"
                      type: "code"
                      sortingKey: "1"
                      content: "clean_data()"
                      version: 1
                      metadata: {}
                - id: "nb-002"
                  name: "Analysis"
                  blocks:
                    - id: "blk-002"
                      type: "code"
                      sortingKey: "1"
                      content: "analyze()"
                      version: 1
                      metadata: {}
        """)
        doc = DeepnoteLoader().loads(yaml_str)
        assert len(doc.cells) == 2
        assert doc.cells[0].metadata.get("notebook_name") == "Data Prep"
        assert doc.cells[1].metadata.get("notebook_name") == "Analysis"

    def test_load_from_file(self, sample_yaml, tmp_path):
        filepath = tmp_path / "test.deepnote"
        filepath.write_text(sample_yaml, encoding="utf-8")
        doc = DeepnoteLoader().load(filepath)
        assert len(doc.cells) == 3

    def test_project_metadata_preserved(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        assert "deepnote_metadata" in doc.metadata
        assert doc.metadata["deepnote_metadata"]["version"] == "1.0.0"
        assert "deepnote_settings" in doc.metadata
        assert "deepnote_integrations" in doc.metadata


class TestDeepnoteDumper:
    def test_dump_round_trip(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert len(doc2.cells) == 3
        assert doc2.cells[0].source.strip() == doc.cells[0].source.strip()
        assert doc2.cells[1].source.strip() == doc.cells[1].source.strip()

    def test_dump_preserves_block_type(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert doc2.cells[2].metadata.get("block_type") == "sql"

    def test_dump_preserves_block_group(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert doc2.cells[2].block_group == "grp-001"

    def test_dump_preserves_cell_ids(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert doc2.cells[0].cell_id == "blk-001"
        assert doc2.cells[1].cell_id == "blk-002"

    def test_dump_standard_code_cell(self):
        doc = NotebookDocument(
            cells=[Cell(source="x = 1", cell_type=CellType.CODE)],
            source_format="deepnote",
        )
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert len(doc2.cells) == 1
        assert doc2.cells[0].cell_type == CellType.CODE
        assert "x = 1" in doc2.cells[0].source

    def test_dump_standard_markdown_cell(self):
        doc = NotebookDocument(
            cells=[Cell(source="# Hello", cell_type=CellType.MARKDOWN)],
            source_format="deepnote",
        )
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert doc2.cells[0].cell_type == CellType.MARKDOWN

    def test_dump_with_outputs(self):
        doc = NotebookDocument(
            cells=[
                Cell(
                    source="print('hi')",
                    cell_type=CellType.CODE,
                    outputs=[CellOutput(output_type="stream", content="hi\n")],
                )
            ],
            source_format="deepnote",
        )
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert len(doc2.cells[0].outputs) == 1

    def test_dump_to_file(self, tmp_path):
        doc = NotebookDocument(
            cells=[Cell(source="x = 1", cell_type=CellType.CODE)],
            source_format="deepnote",
        )
        filepath = tmp_path / "test.deepnote"
        DeepnoteDumper().dump(doc, filepath)
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "project:" in content
        assert "notebooks:" in content
        assert "x = 1" in content

    def test_dump_is_valid_yaml(self):
        doc = NotebookDocument(
            cells=[Cell(source="x = 1", cell_type=CellType.CODE)],
            source_format="deepnote",
        )
        yaml_out = DeepnoteDumper().dump(doc)
        parsed = yaml.safe_load(yaml_out)
        assert "project" in parsed
        assert "notebooks" in parsed["project"]

    def test_dump_preserves_language(self):
        doc = NotebookDocument(
            cells=[
                Cell(
                    source="x <- 1",
                    cell_type=CellType.CODE,
                    language="r",
                )
            ],
            source_format="deepnote",
        )
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert doc2.cells[0].language == "r"

    def test_dump_multi_notebook_round_trip(self):
        cells = [
            Cell(
                source="clean()",
                cell_type=CellType.CODE,
                metadata={"notebook_name": "Data Prep"},
            ),
            Cell(
                source="analyze()",
                cell_type=CellType.CODE,
                metadata={"notebook_name": "Analysis"},
            ),
        ]
        doc = NotebookDocument(cells=cells, source_format="deepnote")
        yaml_out = DeepnoteDumper().dump(doc)
        data = yaml.safe_load(yaml_out)
        assert len(data["project"]["notebooks"]) == 2
        names = {nb["name"] for nb in data["project"]["notebooks"]}
        assert names == {"Data Prep", "Analysis"}


class TestDeepnoteIntegration:
    """End-to-end tests for Deepnote loader/dumper."""

    def test_round_trip_preserves_cell_count(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert len(doc.cells) == len(doc2.cells)

    def test_round_trip_preserves_content(self, sample_yaml):
        doc = DeepnoteLoader().loads(sample_yaml)
        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        for i, (c1, c2) in enumerate(zip(doc.cells, doc2.cells)):
            assert c1.source.strip() == c2.source.strip(), f"Cell {i} content differs"

    def test_round_trip_all_block_types(self):
        """Test that all custom block types round-trip correctly."""
        blocks = ["sql", "chart", "input", "visualization", "big_number", "divider", "rich_text"]
        yaml_blocks = []
        for i, bt in enumerate(blocks):
            yaml_blocks.append(f"""
                - id: "blk-{i:03d}"
                  type: "{bt}"
                  sortingKey: "{i}"
                  content: "# {bt} content"
                  version: 1
                  metadata: {{}}""")

        yaml_str = "project:\n  notebooks:\n    - id: nb-001\n      name: All Types\n      blocks:" + "".join(yaml_blocks)
        doc = DeepnoteLoader().loads(yaml_str)
        assert len(doc.cells) == len(blocks)

        yaml_out = DeepnoteDumper().dump(doc)
        doc2 = DeepnoteLoader().loads(yaml_out)
        assert len(doc2.cells) == len(blocks)
        for c in doc2.cells:
            bt = c.metadata.get("block_type")
            assert bt in blocks, f"Unexpected block_type: {bt}"
