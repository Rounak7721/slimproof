"""slimproof's own MCP server: tool registration only, all logic lives in slimproof.core."""

from pathlib import Path

from mcp import types
from mcp.server.mcpserver import MCPServer

from slimproof.core.audit import audit
from slimproof.core.configs import config_paths
from slimproof.core.report import to_json

mcp = MCPServer("slimproof")

READ_ONLY = types.ToolAnnotations(read_only_hint=True)


@mcp.tool(annotations=READ_ONLY)
async def audit_config(config_path: str | None = None) -> str:
    """Rank every tool in the MCP configs by token cost (JSON). Auto-detects configs if no path."""
    paths = [Path(config_path)] if config_path else config_paths(Path.cwd())
    if not paths:
        return "No MCP config files found. Pass config_path."
    return to_json(await audit(paths))
