"""Format audit results as JSON or a terminal table."""

import json
from dataclasses import asdict

from rich.table import Table

from slimproof.core.audit import AuditResult, ToolCost


def to_json(result: AuditResult) -> str:
    """Audit results as a JSON string, for scripts and CI."""
    return json.dumps(asdict(result), indent=2)


def to_table(costs: list[ToolCost]) -> Table:
    """Audit results as a rich table, one row per tool, plus a total."""
    table = Table(title="MCP tool token cost (~ = estimate)")
    table.add_column("Server")
    table.add_column("Tool")
    table.add_column("~Tokens", justify="right")
    for c in costs:
        table.add_row(c.server, c.tool, str(c.tokens))
    table.add_row("", "[bold]Total", f"[bold]{sum(c.tokens for c in costs)}")
    return table
