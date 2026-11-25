"""Find and parse MCP client config files."""

import json
import os
import re
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters

from slimproof.core.client import HttpServer

_VAR = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand(text: str) -> str:
    """Expand `${VAR}` and `${VAR:-default}` like Claude Code; unknown vars stay as written."""
    return _VAR.sub(lambda m: os.environ.get(m[1], m[2] if m[2] is not None else m[0]), text)


def _server(entry: dict[str, Any]) -> StdioServerParameters | HttpServer | str:
    """One config entry as a server, or the reason it is skipped."""
    if "command" in entry:
        env = entry.get("env")
        return StdioServerParameters(
            command=_expand(entry["command"]),
            args=[_expand(a) for a in entry.get("args", [])],
            env={k: _expand(v) for k, v in env.items()} if env is not None else None,
        )
    if entry.get("type") == "http":
        headers = entry.get("headers", {})
        return HttpServer(_expand(entry["url"]), {k: _expand(v) for k, v in headers.items()})
    return f"{entry.get('type', 'unknown')} servers not supported yet"


def _read(path: Path) -> dict[str, Any]:
    """The JSON object in config file `path`; a clear ValueError if it isn't one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON ({e})") from None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def load_servers(
    paths: list[Path], cwd: Path | None = None
) -> tuple[dict[str, StdioServerParameters | HttpServer], dict[str, str]]:
    """Read the `mcpServers` blocks of all `paths`.

    A name found in several scopes keeps the entry Claude Code uses: local > project > user.
    `paths` must list the project config before the user config (as `config_paths` does).
    Return (stdio and HTTP servers, {name: reason} for skipped ones).
    """
    here = cwd or Path.cwd()
    local: dict[str, Any] = {}
    shared: dict[str, Any] = {}
    for path in paths:
        data = _read(path)
        projects = data.get("projects", {})
        project = projects.get(here.as_posix()) or projects.get(str(here), {})
        local = {**project.get("mcpServers", {}), **local}  # earlier paths win
        shared = {**data.get("mcpServers", {}), **shared}

    servers: dict[str, StdioServerParameters | HttpServer] = {}
    skipped: dict[str, str] = {}
    for name, entry in {**shared, **local}.items():
        try:
            server = _server(entry)
        except (AttributeError, KeyError, TypeError, ValueError):  # wrong shape or field type
            server = "invalid config entry"
        if isinstance(server, str):
            skipped[name] = server
        else:
            servers[name] = server
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


def find_server(name: str, paths: list[Path]) -> StdioServerParameters | HttpServer:
    """The stdio or HTTP server called `name`, picked in Claude Code's scope order."""
    servers, _ = load_servers(paths)
    if name in servers:
        return servers[name]
    raise ValueError(f"No stdio or HTTP server named '{name}' in the MCP configs.")
