"""Find and parse MCP client config files."""

import json
import os
from pathlib import Path

from mcp import StdioServerParameters

from slimproof.core.client import HttpServer


def load_servers(
    path: Path, cwd: Path | None = None
) -> tuple[dict[str, StdioServerParameters | HttpServer], dict[str, str]]:
    """Read a config's `mcpServers` block.

    Return (stdio and HTTP servers, {name: reason} for skipped ones).
    """

    data = json.loads(path.read_text(encoding="utf-8"))

    servers: dict[str, StdioServerParameters | HttpServer] = {}
    skipped: dict[str, str] = {}

    project = data.get("projects", {}).get(str(cwd or Path.cwd()), {})
    entries = {**data.get("mcpServers", {}), **project.get("mcpServers", {})}

    for name, entry in entries.items():
        if "command" in entry:
            servers[name] = StdioServerParameters(
                command=entry["command"], args=entry.get("args", []), env=entry.get("env")
            )
        elif entry.get("type") == "http":
            # ponytail: no ${VAR:-default} syntax, and stdio args/env aren't expanded yet
            servers[name] = HttpServer(
                url=os.path.expandvars(entry["url"]),
                headers={k: os.path.expandvars(v) for k, v in entry.get("headers", {}).items()},
            )
        else:
            skipped[name] = f"{entry.get('type', 'unknown')} servers not supported yet"
    return servers, skipped


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
