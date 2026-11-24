"""Measure how many tokens each MCP tool definition costs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from mcp.server.mcpserver import MCPServer

from slimproof.core.client import HttpServer, NeedsLogin, list_tools
from slimproof.core.configs import load_servers
from slimproof.core.guard import without_wording
from slimproof.core.rules import Finding, check
from slimproof.core.tokens import DEFAULT_RATIO, count_tokens


@dataclass(frozen=True)
class ToolCost:
    """Token cost of one tool on one server."""

    server: str
    tool: str
    tokens: int
    description_tokens: int  # the part in descriptions/titles: what slimming can shrink


@dataclass(frozen=True)
class AuditResult:
    """Everything one audit found."""

    costs: list[ToolCost]
    errors: dict[str, str]  # server -> why auditing it failed
    skipped: dict[str, str]  # server -> why we deliberately didn't try
    findings: list[Finding] = field(default_factory=list)
    exact: bool = False  # True: Claude count_tokens API; False: chars / ratio estimate


async def audit_server(
    name: str,
    server: StdioServerParameters | MCPServer | HttpServer,
    exact: bool = False,
    ratio: float = DEFAULT_RATIO,
) -> AuditResult:
    """List `server`'s tools, count each tool's tokens and run the bloat rules.

    `exact` counts with Claude's count_tokens API (needs ANTHROPIC_API_KEY);
    else estimates as characters / `ratio`.
    """
    tools = await list_tools(server)
    bare = [without_wording(t) for t in tools]
    counts = count_tokens(tools + bare, exact, ratio)  # one batch shares the API baseline
    full, structure = counts[: len(tools)], counts[len(tools) :]
    costs = [
        ToolCost(name, t.name, n, max(n - s, 0))  # exact counts can wobble by a token
        for t, n, s in zip(tools, full, structure, strict=True)
    ]
    return AuditResult(costs, errors={}, skipped={}, findings=check(name, tools), exact=exact)


def _secrets(server: StdioServerParameters | HttpServer) -> list[str]:
    """Values that must never be printed: stdio env values and HTTP header values."""
    values = (
        server.headers.values() if isinstance(server, HttpServer) else (server.env or {}).values()
    )
    return [word for v in values for word in v.split()]


def _root(e: BaseException) -> BaseException:
    """The first real error inside nested async exception groups."""
    while sub := getattr(e, "exceptions", None):
        e = sub[0]
    return e


def _error_message(e: BaseException, secrets: list[str]) -> str:
    """Readable error text: unwrap async exception groups, then mask secret values."""
    e = _root(e)
    msg = str(e) if isinstance(e, NeedsLogin) else f"{type(e).__name__}: {e}"
    for secret in secrets:
        if len(secret) >= 4:  # ponytail: skip short values like "1" so messages stay readable
            msg = msg.replace(secret, "***")
    return msg


async def audit_one(
    name: str,
    server: StdioServerParameters | HttpServer,
    exact: bool = False,
    ratio: float = DEFAULT_RATIO,
) -> AuditResult:
    """Audit a single server; a failure becomes an error (or skipped) entry, not an exception."""
    try:
        result = await audit_server(name, server, exact, ratio)
    except Exception as e:
        msg = {name: _error_message(e, _secrets(server))}
        if isinstance(_root(e), NeedsLogin):
            return AuditResult(costs=[], errors={}, skipped=msg, exact=exact)
        return AuditResult(costs=[], errors=msg, skipped={}, exact=exact)
    result.costs.sort(key=lambda c: c.tokens, reverse=True)
    return result


async def tool_definitions(server: StdioServerParameters | HttpServer) -> list[dict[str, Any]]:
    """Every tool on `server` as JSON-ready dicts; a failure is raised with secrets masked."""
    try:
        tools = await list_tools(server)
    except Exception as e:
        raise RuntimeError(_error_message(e, _secrets(server))) from None
    return [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]


async def audit(
    paths: list[Path], exact: bool = False, ratio: float = DEFAULT_RATIO
) -> AuditResult:
    """Audit every server in `paths`, with costs ranked high -> low."""
    result = AuditResult(costs=[], errors={}, skipped={}, exact=exact)
    servers, skipped = load_servers(paths)
    result.skipped.update(skipped)
    for name, server in servers.items():
        # ponytail: one server at a time; run concurrently if audits feel slow
        one = await audit_one(name, server, exact, ratio)
        result.costs.extend(one.costs)
        result.findings.extend(one.findings)
        result.errors.update(one.errors)
        result.skipped.update(one.skipped)
    result.costs.sort(key=lambda c: c.tokens, reverse=True)
    return result
