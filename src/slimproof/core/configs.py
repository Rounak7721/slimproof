"""Find and parse MCP client config files."""

import json
import os
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


def config_paths(cwd: Path) -> list[Path]:
    """Known Claude Code / Claude Desktop config locations that exist on this machine."""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
    candidates = [
        cwd / ".mcp.json",  # Claude Code, project scope
        home / ".claude.json",  # Claude Code, user scope
        home / "Library/Application Support/Claude/claude_desktop_config.json",  # macOS
        appdata / "Claude/claude_desktop_config.json",  # Windows
    ]
    return [p for p in candidates if p.is_file()]
