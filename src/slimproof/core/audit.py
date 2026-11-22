"""Measure how many tokens each MCP tool definition costs."""

from dataclasses import dataclass

from mcp import StdioServerParameters
from mcp.server.mcpserver import MCPServer

from slimproof.core.client import list_tools
from slimproof.core.tokens import estimate_tokens, tool_text


@dataclass(frozen=True)
class ToolCost:
    """Token cost of one tool on one server."""

    server: str
    tool: str
    tokens: int


async def audit_server(name: str, server: StdioServerParameters | MCPServer) -> list[ToolCost]:
    """List `server`'s tools and estimate each tool's token cost."""
    tools = await list_tools(server)
    return [ToolCost(name, t.name, estimate_tokens(tool_text(t))) for t in tools]
