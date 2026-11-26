"""Command-line interface: a thin layer over slimproof.core."""

import asyncio
import json
import shlex
from collections.abc import Callable
from dataclasses import asdict
from functools import partial
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal

import anyio
import typer
from mcp import types
from rich.console import Console

from slimproof.core.apply import apply as apply_proxy
from slimproof.core.apply import revert as revert_proxy
from slimproof.core.audit import AuditResult, audit_one
from slimproof.core.audit import audit as run_audit
from slimproof.core.client import server_from
from slimproof.core.configs import config_paths
from slimproof.core.guard import compare as compare_tools
from slimproof.core.proxy import run_proxy
from slimproof.core.report import (
    compare_markdown,
    compare_table,
    over_budget,
    to_json,
    to_markdown,
    to_table,
)
from slimproof.core.tokens import DEFAULT_RATIO, claude_setup_problem
from slimproof.server import mcp as mcp_server

app = typer.Typer(no_args_is_help=True)

Format = Literal["table", "json", "markdown"]
FormatOption = Annotated[Format, typer.Option("--format")]

ExactOption = Annotated[
    bool,
    typer.Option(
        "--exact", help="Exact Claude token counts via the free count_tokens API (needs API key)."
    ),
]

RatioOption = Annotated[
    float,
    typer.Option(min=0.5, help="Characters per token for the estimate. Lower = higher counts."),
]

BudgetOption = Annotated[
    float | None,
    typer.Option(min=0, help="Exit 1 if tools use more than this % of the context window."),
]

WindowOption = Annotated[
    int, typer.Option(min=1, help="Context window size in tokens for --budget, e.g. 1000000.")
]


def _check_exact(exact: bool) -> None:
    """Exit 2 with a clear message if --exact can't run on this machine."""
    if exact and (problem := claude_setup_problem()):
        typer.echo(problem, err=True)
        raise typer.Exit(2)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"slimproof {version('slimproof')}")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option("--version", callback=_print_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Audit MCP tool definitions for token bloat."""


ConfigOption = Annotated[
    list[Path] | None,
    typer.Option(exists=True, dir_okay=False, help="Config file(s). Default: auto-detect."),
]


@app.command()
def audit(
    config: ConfigOption = None,
    fmt: FormatOption = "table",
    exact: ExactOption = False,
    ratio: RatioOption = DEFAULT_RATIO,
    budget: BudgetOption = None,
    window: WindowOption = 200_000,
) -> None:
    """Rank every tool in your MCP configs by token cost."""
    _check_exact(exact)
    paths = config or config_paths(Path.cwd())
    if not paths:
        typer.echo("No MCP config files found. Pass one with --config.", err=True)
        raise typer.Exit(2)

    try:
        result = asyncio.run(run_audit(paths, exact, ratio))
    except (OSError, ValueError) as e:  # unreadable config; server failures are in the result
        typer.echo(f"Can't read the MCP config: {e}", err=True)
        raise typer.Exit(2) from None
    _print_result(result, fmt, budget, window)


@app.command()
def server(
    command: Annotated[list[str] | None, typer.Argument(help="Stdio command, after --.")] = None,
    url: Annotated[str | None, typer.Option(help="Streamable HTTP URL.")] = None,
    fmt: FormatOption = "table",
    exact: ExactOption = False,
    ratio: RatioOption = DEFAULT_RATIO,
    budget: BudgetOption = None,
    window: WindowOption = 200_000,
) -> None:
    """Audit one server without a config: `server -- CMD ARGS...` or `server --url URL`."""
    _check_exact(exact)
    try:
        name, params = server_from(command, url)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from None
    _print_result(asyncio.run(audit_one(name, params, exact, ratio)), fmt, budget, window)


@app.command()
def compare(
    original: Annotated[Path, typer.Argument(help="JSON list of the original tools.")],
    slim: Annotated[Path, typer.Argument(help="JSON list of the slim tools.")],
    fmt: FormatOption = "table",
    exact: ExactOption = False,
    ratio: RatioOption = DEFAULT_RATIO,
) -> None:
    """Check slim tools against the originals: token savings and the lossless guard."""
    _check_exact(exact)
    try:
        before, after = _read_tools(original), _read_tools(slim)
    except (OSError, ValueError) as e:
        typer.echo(f"Can't read the tools: {e}", err=True)
        raise typer.Exit(2) from None

    changes = compare_tools(before, after, exact, ratio)
    if fmt == "json":
        typer.echo(json.dumps([asdict(c) for c in changes], indent=2))
    elif fmt == "markdown":
        typer.echo(compare_markdown(changes, exact), nl=False)
    else:
        Console().print(compare_table(changes, exact))
    if any(c.problems for c in changes):
        raise typer.Exit(1)


def _read_tools(path: Path) -> list[types.Tool]:
    """Tools from a JSON file holding a list of MCP tool definitions."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must hold a JSON list of tools")
    return [types.Tool.model_validate(t) for t in data]


@app.command()
def proxy(
    name: Annotated[str, typer.Argument(help="Server name the slim tools were saved for.")],
    command: Annotated[
        list[str], typer.Argument(help="The real server's stdio command, after --.")
    ],
) -> None:
    """Run a stdio MCP server and serve its saved slim tools: `proxy NAME -- CMD ARGS...`."""
    try:
        code = anyio.run(run_proxy, name, command)
    except OSError as e:
        typer.echo(f"Can't start {command[0]}: {e}", err=True)
        raise typer.Exit(2) from None
    raise typer.Exit(code)


@app.command()
def apply(
    name: str,
    config: ConfigOption = None,
    launcher: Annotated[
        str, typer.Option(help="Command that runs slimproof, e.g. to test an unreleased version.")
    ] = "uvx slimproof",
) -> None:
    """Start server NAME through the proxy, so Claude Code gets its saved slim tools."""
    path = _edit_config(partial(apply_proxy, launcher=shlex.split(launcher)), name, config)
    typer.echo(f"{name} now uses its slim tools ({path} changed).")
    typer.echo(f"Restart Claude Code to load them. To undo: slimproof revert {name}")


@app.command()
def revert(name: str, config: ConfigOption = None) -> None:
    """Start server NAME without the proxy again (its original tools)."""
    path = _edit_config(revert_proxy, name, config)
    typer.echo(f"{name} uses its original tools again ({path} changed). Restart Claude Code.")


def _edit_config(
    edit: Callable[[str, list[Path]], Path], name: str, config: list[Path] | None
) -> Path:
    """Run `edit` on the configs; exit 2 with the reason if it can't."""
    paths = config or config_paths(Path.cwd())
    try:
        return edit(name, paths)
    except (OSError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from None


@app.command("mcp")
def run_mcp() -> None:
    """Run slimproof as an MCP server over stdio (for Claude Code and other clients)."""
    mcp_server.run()


def _print_result(
    result: AuditResult,
    fmt: Format,
    budget: float | None = None,
    window: int = 200_000,
) -> None:
    """Print `result` in `fmt`; exit 2 if any server failed, 1 if over budget."""
    if fmt == "json":
        typer.echo(to_json(result))
    elif fmt == "markdown":
        typer.echo(to_markdown(result), nl=False)
    else:
        if result.costs:
            Console().print(to_table(result.costs, result.exact))
            for f in result.findings:
                typer.echo(f"{f.rule} {f.server}/{f.tool}: {f.message}")

        for name, msg in result.skipped.items():
            typer.echo(f"{name}: skipped ({msg})", err=True)

        for name, msg in result.errors.items():
            typer.echo(f"{name}: failed ({msg})", err=True)

    if result.errors:
        raise typer.Exit(2)
    total = sum(c.tokens for c in result.costs)
    if budget is not None and (problem := over_budget(total, budget, window)):
        typer.echo(problem, err=True)
        raise typer.Exit(1)
