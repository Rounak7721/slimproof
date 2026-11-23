"""Measure how many tokens each MCP tool definition costs."""

from dataclasses import dataclass
from pathlib import Path

from mcp import StdioServerParameters
from mcp.server.mcpserver import MCPServer

from slimproof.core.client import HttpServer, list_tools
from slimproof.core.configs import load_servers
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


async def audit_server(
    name: str, server: StdioServerParameters | MCPServer | HttpServer
) -> list[ToolCost]:
    """List `server`'s tools and estimate each tool's token cost."""
    tools = await list_tools(server)
    return [ToolCost(name, t.name, estimate_tokens(tool_text(t))) for t in tools]


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
        costs = await audit_server(name, server)
    except Exception as e:
        return AuditResult(costs=[], errors={name: _error_message(e, _secrets(server))}, skipped={})
    costs.sort(key=lambda c: c.tokens, reverse=True)
    return AuditResult(costs=costs, errors={}, skipped={})


async def audit(paths: list[Path]) -> AuditResult:
    """Audit every server in `paths`, with costs ranked high -> low."""
    result = AuditResult(costs=[], errors={}, skipped={})
    for path in paths:
        servers, skipped = load_servers(path)
        result.skipped.update(skipped)
        for name, server in servers.items():
            try:  # ponytail: one server at a time; run concurrently if audits feel slow
                result.costs.extend(await audit_server(name, server))
            except Exception as e:
                result.errors[name] = _error_message(e, _secrets(server))
    result.costs.sort(key=lambda c: c.tokens, reverse=True)
    return result
