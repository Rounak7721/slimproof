"""slimproof's own MCP server: tool registration only, all logic lives in slimproof.core."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from slimproof.core.apply import real_server
from slimproof.core.audit import audit, audit_one, tool_definitions
from slimproof.core.client import HttpServer, server_from
from slimproof.core.configs import config_paths, find_server
from slimproof.core.guard import compare as compare_tools
from slimproof.core.overrides import save_overrides as save
from slimproof.core.report import to_json

mcp = MCPServer("slimproof", log_level="WARNING")

READ_ONLY = types.ToolAnnotations(read_only_hint=True)


def _paths(config_path: str | None) -> list[Path]:
    """The given config, or every config auto-detected from the working directory."""
    return [Path(config_path)] if config_path else config_paths(Path.cwd())


@mcp.tool(annotations=READ_ONLY)
async def audit_config(config_path: str | None = None) -> str:
    """Rank every tool in the MCP configs by token cost (JSON). Auto-detects configs if no path."""
    paths = _paths(config_path)
    if not paths:
        return "No MCP config files found. Pass config_path."
    return to_json(await audit(paths))


@mcp.tool(annotations=READ_ONLY)
async def audit_server(command: list[str] | None = None, url: str | None = None) -> str:
    """Audit one MCP server by stdio command (["npx", "-y", "pkg"]) or HTTP url."""
    try:
        name, server = server_from(command, url)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return to_json(await audit_one(name, server))


@mcp.tool(annotations=READ_ONLY)
def compare(original: list[dict[str, Any]], slim: list[dict[str, Any]]) -> str:
    """Check slim tools against originals: token savings + lossless-guard problems."""
    before = [types.Tool.model_validate(t) for t in original]
    after = [types.Tool.model_validate(t) for t in slim]
    return json.dumps([asdict(c) for c in compare_tools(before, after)], indent=2)


@mcp.tool(annotations=READ_ONLY)
async def get_tools(
    name: str | None = None,
    command: list[str] | None = None,
    url: str | None = None,
    config_path: str | None = None,
) -> str:
    """Full tool definitions (JSON) of one server: by config `name`, stdio `command` or `url`."""
    try:
        server = find_server(name, _paths(config_path)) if name else server_from(command, url)[1]
        return json.dumps(await tool_definitions(real_server(server)))
    except (ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=types.ToolAnnotations(destructive_hint=False, idempotent_hint=True))
async def save_overrides(
    name: str, slim: list[dict[str, Any]], config_path: str | None = None
) -> str:
    """Save slim tools of configured server `name` for the proxy; guards them against live tools."""
    try:
        server = real_server(find_server(name, _paths(config_path)))
        if isinstance(server, HttpServer):
            raise ValueError(f"'{name}' is a remote HTTP server; the proxy can't serve those yet.")
        originals = [types.Tool.model_validate(t) for t in await tool_definitions(server)]
        path = save(name, originals, [types.Tool.model_validate(t) for t in slim])
    except (ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e
    return (
        f"Saved {len(slim)} slim tool(s) to {path}. To use them, the user runs "
        f"`slimproof apply {name}` in a terminal and restarts Claude Code."
    )
