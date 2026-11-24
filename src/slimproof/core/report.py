"""Format audit results as JSON, Markdown or a terminal table."""

import json
from dataclasses import asdict

from rich.table import Table

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.tokens import CLAUDE_MODEL


def to_json(result: AuditResult) -> str:
    """Audit results as a JSON string, for scripts and CI."""
    return json.dumps(asdict(result), indent=2)


def _headings(exact: bool) -> tuple[str, str]:
    """(title, token column header): the `~` marks an estimate."""
    if exact:
        return f"MCP tool token cost (exact, {CLAUDE_MODEL})", "Tokens"
    return "MCP tool token cost (~ = estimate)", "~Tokens"


def to_markdown(result: AuditResult) -> str:
    """Audit results as Markdown, e.g. for a PR comment or a CI job summary."""
    title, column = _headings(result.exact)
    total = sum(c.tokens for c in result.costs)
    in_descriptions = sum(c.description_tokens for c in result.costs)
    lines = [
        f"## {title}",
        "",
        f"| Server | Tool | {column} | In descriptions |",
        "|---|---|--:|--:|",
        *(
            f"| {_cell(c.server)} | {_cell(c.tool)} | {c.tokens:,} | "
            f"{_part(c.description_tokens, c.tokens)} |"
            for c in result.costs
        ),
        f"| | **Total** | **{total:,}** | **{_part(in_descriptions, total)}** |",
        "",
        context_share(total),
    ]
    sections = [
        ("Findings", [f"`{f.rule}` {f.server}/{f.tool}: {f.message}" for f in result.findings]),
        ("Skipped", [f"**{name}**: {msg}" for name, msg in result.skipped.items()]),
        ("Failed", [f"**{name}**: {msg}" for name, msg in result.errors.items()]),
    ]
    for heading, items in sections:
        if items:
            lines += ["", f"### {heading}", "", *(f"- {item}" for item in items)]
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    """`text` made safe inside a Markdown table cell."""
    return text.replace("|", "\\|")


def to_table(costs: list[ToolCost], exact: bool = False) -> Table:
    """Audit results as a rich table, one row per tool, plus a total."""
    title, column = _headings(exact)
    total = sum(c.tokens for c in costs)
    in_descriptions = sum(c.description_tokens for c in costs)
    table = Table(title=title, caption=context_share(total))
    table.add_column("Server")
    table.add_column("Tool")
    table.add_column(column, justify="right")
    table.add_column("In descriptions", justify="right")
    for c in costs:
        table.add_row(c.server, c.tool, f"{c.tokens:,}", _part(c.description_tokens, c.tokens))
    table.add_row("", "[bold]Total", f"[bold]{total:,}", f"[bold]{_part(in_descriptions, total)}")
    return table


def _part(part: int, whole: int) -> str:
    """'part (share%)', e.g. '1,200 (40%)'."""
    return f"{part:,} ({part / whole:.0%})" if whole else "0"


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
