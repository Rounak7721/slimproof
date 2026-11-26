"""Format audit results as JSON, Markdown or a terminal table."""

import json
from dataclasses import asdict

from rich.table import Table

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.guard import ToolChange
from slimproof.core.rules import Finding
from slimproof.core.tokens import CLAUDE_MODEL


def to_json(result: AuditResult) -> str:
    """Audit results as a JSON string, for scripts and CI."""
    return json.dumps(asdict(result), indent=2)


def _headings(exact: bool) -> tuple[str, str]:
    """(title, token column header): the `~` marks an estimate."""
    if exact:
        return f"MCP tool token cost (exact, {CLAUDE_MODEL})", "Tokens"
    return "MCP tool token cost (~ = estimate)", "~Tokens"


def heaviest(costs: list[ToolCost], top: int | None) -> tuple[list[ToolCost], list[ToolCost]]:
    """(the `top` heaviest tools, the rest); all tools are shown when `top` is None."""
    ranked = sorted(costs, key=lambda c: c.tokens, reverse=True)
    return (ranked, []) if top is None else (ranked[:top], ranked[top:])


def shown_findings(
    findings: list[Finding], costs: list[ToolCost], top: int | None
) -> list[Finding]:
    """All findings, or with `top`: at most `top` findings, from the `top` heaviest tools."""
    if top is None:
        return findings
    visible = {(c.server, c.tool) for c in heaviest(costs, top)[0]}
    return [f for f in findings if (f.server, f.tool) in visible][:top]


def summary(result: AuditResult, top: int | None) -> str:
    """One closing line with the totals, so they stay visible after long findings."""
    total = sum(c.tokens for c in result.costs)
    described = sum(c.description_tokens for c in result.costs)
    approx = "" if result.exact else "~"
    line = (
        f"Total: {len(result.costs)} tools, {approx}{total:,} tokens "
        f"({described / total:.0%} in descriptions), {total / 200_000:.1%} of a 200K context "
        f"window. {len(result.findings)} finding(s)."
    )
    if top is None and len(result.findings) > LONG_OUTPUT:
        line += " Add --top 10 for a short view."
    return line


# Findings above this count scroll the table off a normal terminal.
LONG_OUTPUT = 20


def more_findings(hidden: int) -> str:
    """The note under a --top report about findings it leaves out."""
    return f"+ {hidden} more finding(s). Run without --top to see all."


def _more_tools(rest: list[ToolCost]) -> tuple[str, int, int]:
    """('… N more tools', tokens, description tokens) for the tools a --top report hides."""
    return (
        f"… {len(rest)} more tools",
        sum(c.tokens for c in rest),
        sum(c.description_tokens for c in rest),
    )


def to_markdown(result: AuditResult, top: int | None = None) -> str:
    """Audit results as Markdown, e.g. for a PR comment or a CI job summary."""
    title, column = _headings(result.exact)
    total = sum(c.tokens for c in result.costs)
    in_descriptions = sum(c.description_tokens for c in result.costs)
    shown, rest = heaviest(result.costs, top)
    more = []
    if rest:
        label, tokens, desc = _more_tools(rest)
        more = [f"| | _{label}_ | {tokens:,} | {_part(desc, tokens)} |"]
    lines = [
        f"## {title}",
        "",
        f"| Server | Tool | {column} | In descriptions |",
        "|---|---|--:|--:|",
        *(
            f"| {_cell(c.server)} | {_cell(c.tool)} | {c.tokens:,} | "
            f"{_part(c.description_tokens, c.tokens)} |"
            for c in shown
        ),
        *more,
        f"| | **Total** | **{total:,}** | **{_part(in_descriptions, total)}** |",
        "",
        context_share(total),
    ]
    findings = shown_findings(result.findings, result.costs, top)
    finding_lines = [f"`{f.rule}` {f.server}/{f.tool}: {f.message}" for f in findings]
    if hidden := len(result.findings) - len(findings):
        finding_lines.append(more_findings(hidden))
    sections = [
        ("Findings", finding_lines),
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


def to_table(costs: list[ToolCost], exact: bool = False, top: int | None = None) -> Table:
    """Audit results as a rich table: one row per tool (or the `top` heaviest), plus a total.

    The total always counts every tool; hidden tools share one '… N more tools' row.
    """
    title, column = _headings(exact)
    total = sum(c.tokens for c in costs)
    in_descriptions = sum(c.description_tokens for c in costs)
    table = Table(title=title, caption=context_share(total))
    table.add_column("Server")
    table.add_column("Tool")
    table.add_column(column, justify="right")
    table.add_column("In descriptions", justify="right")
    shown, rest = heaviest(costs, top)
    for c in shown:
        table.add_row(c.server, c.tool, f"{c.tokens:,}", _part(c.description_tokens, c.tokens))
    if rest:
        label, tokens, desc = _more_tools(rest)
        table.add_row("", f"[dim]{label}", f"[dim]{tokens:,}", f"[dim]{_part(desc, tokens)}")
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


def _compare_rows(changes: list[ToolChange]) -> list[tuple[str, str, str, str, str]]:
    """(tool, before, after, saved, guard) per change, plus a total row."""
    rows = [
        (
            c.tool,
            f"{c.before:,}",
            f"{c.after:,}",
            _saved(c.before, c.after),
            "; ".join(c.problems) or "ok",
        )
        for c in changes
    ]
    before, after = sum(c.before for c in changes), sum(c.after for c in changes)
    failed = sum(1 for c in changes if c.problems)
    guard = f"{failed} failed" if failed else "all ok"
    return [*rows, ("Total", f"{before:,}", f"{after:,}", _saved(before, after), guard)]


def _saved(before: int, after: int) -> str:
    """Tokens saved and the share of `before`, e.g. '1,200 (40%)'."""
    return _part(before - after, before)


def compare_table(changes: list[ToolChange], exact: bool = False) -> Table:
    """Slim-vs-original results as a rich table, with a total."""
    title, column = _headings(exact)
    table = Table(title=title.replace("MCP tool token cost", "Slim vs original"))
    table.add_column("Tool")
    table.add_column(f"{column} before", justify="right")
    table.add_column(f"{column} after", justify="right")
    table.add_column("Saved", justify="right")
    table.add_column("Guard")
    *rows, total = _compare_rows(changes)
    for row in rows:
        table.add_row(*row)
    table.add_row(*(f"[bold]{cell}" for cell in total))
    return table


def compare_markdown(changes: list[ToolChange], exact: bool = False) -> str:
    """Slim-vs-original results as Markdown."""
    title, column = _headings(exact)
    *rows, total = _compare_rows(changes)
    lines = [
        f"## {title.replace('MCP tool token cost', 'Slim vs original')}",
        "",
        f"| Tool | {column} before | {column} after | Saved | Guard |",
        "|---|--:|--:|--:|---|",
        *("| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows),
        "| " + " | ".join(f"**{_cell(cell)}**" for cell in total) + " |",
    ]
    return "\n".join(lines) + "\n"
