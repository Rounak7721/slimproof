"""Command-line interface: a thin layer over slimproof.core."""

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from slimproof.core.audit import audit as run_audit
from slimproof.core.configs import config_paths
from slimproof.core.report import to_json, to_table

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Audit MCP tool definitions for token bloat."""


@app.command()
def audit(
    config: Annotated[
        list[Path] | None, typer.Option(help="Config file(s). Default: auto-detect.")
    ] = None,
    fmt: Annotated[Literal["table", "json"], typer.Option("--format")] = "table",
) -> None:
    """Rank every tool in your MCP configs by token cost."""
    paths = config or config_paths(Path.cwd())
    if not paths:
        typer.echo("No MCP config files found. Pass one with --config.", err=True)
        raise typer.Exit(2)

    result = asyncio.run(run_audit(paths))
    if fmt == "json":
        typer.echo(to_json(result))
    else:
        Console().print(to_table(result.costs))
        for name, msg in result.skipped.items():
            typer.echo(f"{name}: skipped ({msg})", err=True)
        for name, msg in result.errors.items():
            typer.echo(f"{name}: failed ({msg})", err=True)
    if result.errors:
        raise typer.Exit(2)
