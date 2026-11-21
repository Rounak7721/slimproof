"""Find and parse MCP client config files."""

import json
from pathlib import Path

from mcp import StdioServerParameters


def load_servers(path: Path) -> dict[str, StdioServerParameters]:
    """Read the stdio servers from a config file's `mcpServers` block."""

    data = json.loads(path.read_text(encoding="utf-8"))
    servers: dict[str, StdioServerParameters] = {}
    for name, entry in data.get("mcpServers", {}).items():
        if "command" in entry:  # ponytail: HTTP servers skipped until client.py supports them
            servers[name] = StdioServerParameters(
                command=entry["command"], args=entry.get("args", []), env=entry.get("env")
            )

    return servers
