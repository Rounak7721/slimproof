"""Measure how many tokens each MCP tool definition costs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from mcp.server.mcpserver import MCPServer

from slimproof.core.client import HttpServer, list_tools
from slimproof.core.configs import load_servers
from slimproof.core.rules import Finding, check
from slimproof.core.tokens import estimate_tokens, tool_text


@dataclass(frozen=True)
class ToolCost:
    """Token cost of one tool on one server."""

    server: str
    tool: str
    tokens: int


@dataclass(frozen=True)
class AuditResult:
    """Everything one audit found."""

    costs: list[ToolCost]
    errors: dict[str, str]  # server -> why auditing it failed
    skipped: dict[str, str]  # server -> why we deliberately didn't try
    findings: list[Finding] = field(default_factory=list)


async def audit_server(
    name: str, server: StdioServerParameters | MCPServer | HttpServer
) -> AuditResult:
    """List `server`'s tools, estimate each tool's token cost and run the bloat rules."""
    tools = await list_tools(server)
    costs = [ToolCost(name, t.name, estimate_tokens(tool_text(t))) for t in tools]
    return AuditResult(costs=costs, errors={}, skipped={}, findings=check(name, tools))


def _secrets(server: StdioServerParameters | HttpServer) -> list[str]:
    """Values that must never be printed: stdio env values and HTTP header values."""
    values = (
        server.headers.values() if isinstance(server, HttpServer) else (server.env or {}).values()
    )
    return [word for v in values for word in v.split()]


def _error_message(e: BaseException, secrets: list[str]) -> str:
    """Readable error text: unwrap async exception groups, then mask secret values."""
    while sub := getattr(e, "exceptions", None):
        e = sub[0]
    msg = f"{type(e).__name__}: {e}"
    for secret in secrets:
        if len(secret) >= 4:  # ponytail: skip short values like "1" so messages stay readable
            msg = msg.replace(secret, "***")
    return msg


async def audit_one(name: str, server: StdioServerParameters | HttpServer) -> AuditResult:
    """Audit a single server; a failure becomes an error entry, not an exception."""
    try:
        result = await audit_server(name, server)
    except Exception as e:
        return AuditResult(costs=[], errors={name: _error_message(e, _secrets(server))}, skipped={})
    result.costs.sort(key=lambda c: c.tokens, reverse=True)
    return result


async def tool_definitions(server: StdioServerParameters | HttpServer) -> list[dict[str, Any]]:
    """Every tool on `server` as JSON-ready dicts; a failure is raised with secrets masked."""
    try:
        tools = await list_tools(server)
    except Exception as e:
        raise RuntimeError(_error_message(e, _secrets(server))) from None
    return [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]


async def audit(paths: list[Path]) -> AuditResult:
    """Audit every server in `paths`, with costs ranked high -> low."""
    result = AuditResult(costs=[], errors={}, skipped={})
    for path in paths:
        servers, skipped = load_servers(path)
        result.skipped.update(skipped)
        for name, server in servers.items():
            try:  # ponytail: one server at a time; run concurrently if audits feel slow
                one = await audit_server(name, server)
                result.costs.extend(one.costs)
                result.findings.extend(one.findings)
            except Exception as e:
                result.errors[name] = _error_message(e, _secrets(server))
    result.costs.sort(key=lambda c: c.tokens, reverse=True)
    return result
