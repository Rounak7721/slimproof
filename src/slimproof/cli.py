"""Command-line interface: a thin layer over slimproof.core."""

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from slimproof.core.audit import AuditResult, audit_one
from slimproof.core.audit import audit as run_audit
from slimproof.core.client import server_from
from slimproof.core.configs import config_paths
from slimproof.core.report import to_json, to_table
from slimproof.server import mcp as mcp_server

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

    _print_result(asyncio.run(run_audit(paths)), fmt)


@app.command()
def server(
    command: Annotated[list[str] | None, typer.Argument(help="Stdio command, after --.")] = None,
    url: Annotated[str | None, typer.Option(help="Streamable HTTP URL.")] = None,
    fmt: Annotated[Literal["table", "json"], typer.Option("--format")] = "table",
) -> None:
    """Audit one server without a config: `server -- CMD ARGS...` or `server --url URL`."""
    try:
        name, params = server_from(command, url)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from None
    _print_result(asyncio.run(audit_one(name, params)), fmt)


@app.command("mcp")
def run_mcp() -> None:
    """Run slimproof as an MCP server over stdio (for Claude Code and other clients)."""
    mcp_server.run()


def _print_result(result: AuditResult, fmt: Literal["table", "json"]) -> None:
    """Print `result` as a table or JSON; exit 2 if any server failed."""
    if fmt == "json":
        typer.echo(to_json(result))
    else:
        if result.costs:
            Console().print(to_table(result.costs))
            for f in result.findings:
                typer.echo(f"{f.rule} {f.server}/{f.tool}: {f.message}")

        for name, msg in result.skipped.items():
            typer.echo(f"{name}: skipped ({msg})", err=True)

        for name, msg in result.errors.items():
            typer.echo(f"{name}: failed ({msg})", err=True)

    if result.errors:
        raise typer.Exit(2)
