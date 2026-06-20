"""CLI commands for notebookllm — convert, inspect, search, get."""
from __future__ import annotations

import click

from notebookllm.loaders import load_file, dump_file
from notebookllm.models import NotebookDocument, OutputMode, CellType


@click.group()
@click.version_option(package_name="notebookllm")
def cli():
    """notebookllm — Convert and optimize Jupyter notebooks for LLMs."""
    pass


def _load_or_abort(file: str) -> NotebookDocument:
    """Load a notebook file and abort with a clean error on failure."""
    try:
        return load_file(file)
    except Exception as e:
        click.echo(f"Error: Cannot load {file}: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output file path")
@click.option("-f", "--format", "fmt", help="Output format (ipynb, percent, quarto, markdown)")
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="LLM output mode")
def convert(file: str, output: str | None, fmt: str | None, mode: str):
    """Convert notebook between formats."""
    doc = _load_or_abort(file)

    if output:
        dump_file(doc, output, fmt=fmt)
        click.echo(f"Converted to {output}")
    else:
        output_mode = OutputMode(mode)
        text = doc.to_text(mode=output_mode)
        click.echo(text)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def inspect(file: str):
    """Inspect notebook structure."""
    doc = _load_or_abort(file)
    click.echo(f"Format: {doc.source_format}")
    click.echo(f"Cells: {len(doc.cells)}")
    click.echo(f"Language: {doc.language}")
    click.echo()
    for i, cell in enumerate(doc.cells):
        preview = cell.source[:80].replace("\n", " ")
        if len(cell.source) > 80:
            preview += "..."
        click.echo(f"  [{i}] {cell.cell_type.value:10s} {preview}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("query")
@click.option("-t", "--type", "cell_type", type=click.Choice(["code", "markdown", "raw"]),
              help="Filter by cell type")
def search(file: str, query: str, cell_type: str | None):
    """Search cells by content."""
    doc = _load_or_abort(file)
    ct = CellType(cell_type) if cell_type else None
    results = doc.search(query, cell_type=ct)
    if not results:
        click.echo("No matches found.")
        return
    for idx, cell in results:
        preview = cell.source[:80].replace("\n", " ")
        click.echo(f"  [{idx}] {cell.cell_type.value:10s} {preview}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("index", type=int)
def get(file: str, index: int):
    """Get a specific cell by index."""
    doc = _load_or_abort(file)
    cell = doc.get_cell(index)
    click.echo(f"Cell [{index}] ({cell.cell_type.value}):")
    click.echo(cell.source)


@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport type")
def server(transport: str):
    """Start MCP server."""
    from notebookllm.mcp.server import main
    main(transport=transport)
