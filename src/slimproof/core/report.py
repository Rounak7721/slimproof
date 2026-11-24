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
    table = Table(title=title)
    table.add_column("Server")
    table.add_column("Tool")
    table.add_column(column, justify="right")
    for c in costs:
        table.add_row(c.server, c.tool, str(c.tokens))
    table.add_row("", "[bold]Total", f"[bold]{sum(c.tokens for c in costs)}")
    return table
