"""Format audit results as JSON or a terminal table."""

import json
from dataclasses import asdict

from rich.table import Table

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.tokens import CLAUDE_MODEL


def to_json(result: AuditResult) -> str:
    """Audit results as a JSON string, for scripts and CI."""
    return json.dumps(asdict(result), indent=2)


def to_table(costs: list[ToolCost], exact: bool = False) -> Table:
    """Audit results as a rich table, one row per tool, plus a total."""
    if exact:
        title, column = f"MCP tool token cost (exact, {CLAUDE_MODEL})", "Tokens"
    else:
        title, column = "MCP tool token cost (~ = estimate)", "~Tokens"
    total = sum(c.tokens for c in costs)
    table = Table(title=title, caption=context_share(total))
    table.add_column("Server")
    table.add_column("Tool")
    table.add_column(column, justify="right")
    for c in costs:
        table.add_row(c.server, c.tool, f"{c.tokens:,}")
    table.add_row("", "[bold]Total", f"[bold]{total:,}")
    return table


def over_budget(total: int, budget: float, window: int = 200_000) -> str | None:
    """Why `total` tool tokens break a `budget` (% of `window`), or None if they fit."""
    share = 100 * total / window
    if share <= budget:
        return None
    return (
        f"Over budget: tool definitions use {share:.1f}% of a {window:,}-token context window "
        f"(budget {budget:g}%)."
    )


def context_share(total: int) -> str:
    """`total` tool tokens as a share of Claude's 200K and 1M context windows."""
    return (
        f"Uses {total / 200_000:.1%} of a 200K context window "
        f"({total / 1_000_000:.1%} of 1M) in every request."
    )
