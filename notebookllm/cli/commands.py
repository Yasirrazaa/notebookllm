"""CLI commands for notebookllm — convert, inspect, search, get."""
from __future__ import annotations

import click

from notebookllm.loaders import dump_file, load_file
from notebookllm.models import CellType, NotebookDocument, OutputMode


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
        raise click.Abort() from e


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
    from rich.console import Console
    from rich.table import Table
    console = Console()
    console.print(f"Format: {doc.source_format}")
    console.print(f"Cells: {len(doc.cells)}")
    console.print(f"Language: {doc.language}\n")
    
    table = Table(title="Cells")
    table.add_column("Index", justify="right", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Preview")
    
    for i, cell in enumerate(doc.cells):
        preview = cell.source[:80].replace("\n", " ")
        if len(cell.source) > 80:
            preview += "..."
        table.add_row(str(i), cell.cell_type.value, preview)
        
    console.print(table)


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
    
    from rich.console import Console
    from rich.table import Table
    console = Console()
    
    if not results:
        console.print("[yellow]No matches found.[/yellow]")
        return
        
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Index", justify="right", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Preview")
    
    for idx, cell in results:
        preview = cell.source[:80].replace("\n", " ")
        import re
        preview = re.sub(f"({re.escape(query)})", r"[bold green]\1[/bold green]", preview, flags=re.IGNORECASE)
        table.add_row(str(idx), cell.cell_type.value, preview)
        
    console.print(table)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("index", type=int)
def get(file: str, index: int):
    """Get a specific cell by index."""
    doc = _load_or_abort(file)
    cell = doc.get_cell(index)
    from rich.console import Console
    from rich.syntax import Syntax
    console = Console()
    console.print(f"Cell [{index}] ({cell.cell_type.value}):")
    syntax = Syntax(cell.source, "python" if cell.cell_type == CellType.CODE else "markdown", theme="monokai")
    console.print(syntax)


@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport type")
def server(transport: str):
    """Start MCP server."""
    from notebookllm.mcp.server import main
    main(transport=transport)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="Output mode for token estimation")
@click.option("--breakdown", is_flag=True, help="Show per-cell token breakdown")
def tokens(file: str, mode: str, breakdown: bool):
    """Estimate token usage for a notebook."""
    doc = _load_or_abort(file)
    from notebookllm.utils.tokenizer import tokenize_notebook
    from rich.console import Console
    from rich.table import Table
    console = Console()

    report = tokenize_notebook(doc, mode=mode)
    console.print(report.token_summary)
    if breakdown and report.cell_tokens:
        table = Table(title="Token Breakdown")
        table.add_column("Index", justify="right", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Tokens", justify="right", style="green")
        table.add_column("Preview")
        
        for ct in report.cell_tokens:
            table.add_row(str(ct.cell_index), ct.cell_type, str(ct.tokens), ct.preview)
            
        console.print(table)
