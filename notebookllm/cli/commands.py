"""CLI commands for notebookllm — convert, inspect, search, get, tokens, server.

Uses Click for argument parsing and Rich for formatted output (tables,
syntax highlighting). All commands accept a file path and produce output
to stdout or a specified output file.
"""
from __future__ import annotations

from pathlib import Path

import click

from notebookllm.loaders import dump_file, load_file
from notebookllm.models import CellType, NotebookDocument, OutputMode


@click.group()
@click.version_option(package_name="notebookllm")
def cli():
    """notebookllm — Convert and optimize Jupyter notebooks for AI Agents."""
    pass


def _load_or_abort(file: str) -> NotebookDocument:
    """Load a notebook file and abort with a clean error message on failure.

    Args:
        file: Path to the notebook file.

    Returns:
        The loaded :class:`~notebookllm.models.NotebookDocument`.

    Raises:
        click.Abort: If the file cannot be loaded.
    """
    try:
        return load_file(file)
    except Exception as e:
        click.echo(f"Error: Cannot load {file}: {e}", err=True)
        raise click.Abort() from e


_FORMAT_EXTENSIONS = {
    "ipynb": ".ipynb",
    "percent": ".py",
    "quarto": ".qmd",
    "markdown": ".md",
}


def _batch_output_path(source: str, outdir: str, fmt: str | None) -> str:
    """Derive an output path for a source file inside a batch output directory.

    The output filename follows the pattern ``{stem}_converted{ext}``.

    Args:
        source: Source file path.
        outdir: Output directory path.
        fmt: Target format (used to pick the file extension).

    Returns:
        The full output path as a string.
    """
    stem = Path(source).stem
    ext = _FORMAT_EXTENSIONS.get(fmt, ".py") if fmt else ".py"
    return str(Path(outdir) / f"{stem}_converted{ext}")


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("-o", "--output", type=click.Path(), help="Output file path (single file only)")
@click.option("--outdir", type=click.Path(), help="Output directory (batch mode)")
@click.option("-f", "--format", "fmt", help="Output format (ipynb, percent, quarto, markdown)")
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="AI Agent output mode")
def convert(
    files: tuple[str, ...],
    output: str | None,
    outdir: str | None,
    fmt: str | None,
    mode: str,
):
    """Convert notebook(s) between formats.

    When no ``--output`` or ``--outdir`` is given, outputs Agent-optimized
    text to stdout. Supports batch conversion of multiple files with
    auto-named output.
    """
    from rich.console import Console
    console = Console()

    if len(files) > 1 and output:
        console.print(
            "[red]Error:[/red] --output cannot be used with multiple files"
            " (use --outdir instead)."
        )
        raise click.Abort()

    if len(files) > 1 or outdir:
        if output:
            _convert_single(files[0], output, fmt, mode, console)
        else:
            for file in files:
                if outdir:
                    Path(outdir).mkdir(parents=True, exist_ok=True)
                    out_path = _batch_output_path(file, outdir, fmt)
                    _convert_single(file, out_path, fmt, mode, console)
                else:
                    doc = _load_or_abort(file)
                    output_mode = OutputMode(mode)
                    text = doc.to_text(mode=output_mode)
                    console.print(f"[bold]{file}[/bold]", markup=False)
                    console.print(text, markup=False)
                    console.print()
    else:
        if output:
            _convert_single(files[0], output, fmt, mode, console)
        else:
            doc = _load_or_abort(files[0])
            output_mode = OutputMode(mode)
            text = doc.to_text(mode=output_mode)
            console.print(text, markup=False)


def _convert_single(file: str, output: str, fmt: str | None, mode: str, console):
    """Load a file and dump it to the output path, printing a success message.

    Args:
        file: Source file path.
        output: Destination file path.
        fmt: Output format override.
        mode: Output mode (unused in dump, kept for API consistency).
        console: Rich console instance.
    """
    doc = _load_or_abort(file)
    dump_file(doc, output, fmt=fmt)
    console.print(f"[green]✓[/green] [bold]{output}[/bold]")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def inspect(file: str):
    """Inspect notebook structure — show format, cell count, language, and a cell table."""
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
    """Search cells by content (case-insensitive substring match)."""
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
        escaped = re.escape(query)
        preview = re.sub(
            f"({escaped})", r"[bold green]\1[/bold green]",
            preview, flags=re.IGNORECASE,
        )
        table.add_row(str(idx), cell.cell_type.value, preview)

    console.print(table)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("index", type=int)
def get(file: str, index: int):
    """Get a specific cell by index (0-based)."""
    doc = _load_or_abort(file)
    cell = doc.get_cell(index)
    from rich.console import Console
    from rich.syntax import Syntax
    console = Console()
    console.print(f"Cell [{index}] ({cell.cell_type.value}):")
    lang = "python" if cell.cell_type == CellType.CODE else "markdown"
    syntax = Syntax(cell.source, lang, theme="monokai")
    console.print(syntax)


@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport type")
def server(transport: str):
    """Start the MCP server for AI agent integration.

    Uses stdio transport by default (for Claude Desktop, VS Code, Zed).
    Use ``--transport sse`` for SSE-based connections.
    """
    from notebookllm.mcp.server import main
    main(transport=transport)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-m", "--mode", type=click.Choice(["minimal", "standard", "full"]), default="minimal",
              help="Output mode for token estimation")
@click.option("--breakdown", is_flag=True, help="Show per-cell token breakdown")
def tokens(file: str, mode: str, breakdown: bool):
    """Estimate token usage for a notebook.

    Shows total token count and, with ``--breakdown``, a per-cell table
    with index, type, tokens, and source preview.
    """
    doc = _load_or_abort(file)
    from rich.console import Console
    from rich.table import Table

    from notebookllm.utils.tokenizer import tokenize_notebook
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
