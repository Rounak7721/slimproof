"""Route a configured MCP server through `slimproof proxy`, and undo it."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from mcp import StdioServerParameters

from slimproof.core.client import HttpServer
from slimproof.core.configs import locate
from slimproof.core.overrides import overrides_path, write_atomic

# How a config entry starts the proxy. uvx runs the latest cached slimproof.
LAUNCHER = ["uvx", "slimproof"]


def real_command(command: list[str]) -> list[str] | None:
    """The real server in a `... slimproof proxy NAME -- CMD ARGS` command; None if not proxied."""
    for i in range(1, len(command) - 3):
        launcher = command[:i]
        if (
            command[i] == "proxy"
            and command[i + 2] == "--"
            and any("slimproof" in p for p in launcher)
        ):
            return command[i + 3 :]
    return None


def real_server(
    server: StdioServerParameters | HttpServer,
) -> StdioServerParameters | HttpServer:
    """`server` without the proxy in front, so its original tools can be read."""
    if isinstance(server, HttpServer):
        return server
    command = real_command([server.command, *server.args])
    if command is None:
        return server
    return server.model_copy(update={"command": command[0], "args": command[1:]})


def apply(
    name: str, paths: list[Path], cwd: Path | None = None, launcher: list[str] = LAUNCHER
) -> Path:
    """Make server `name` start through the proxy (run by `launcher`); the config file changed.

    A ValueError if no slim tools are saved, the entry isn't stdio, or it's already proxied.
    """
    if not overrides_path(name).is_file():
        raise ValueError(f"No slim tools saved for '{name}'. Slim and save them with /slimproof.")
    path, data, servers = locate(name, paths, cwd)
    entry = servers[name]
    if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
        raise ValueError(f"'{name}' is not a stdio server; only those can use the proxy yet.")
    command = [entry["command"], *entry.get("args", [])]
    if real_command(command) is not None:
        raise ValueError(f"'{name}' already uses the proxy.")
    entry["command"] = launcher[0]
    entry["args"] = [*launcher[1:], "proxy", name, "--", *command]
    _write(path, data)
    return path


def revert(name: str, paths: list[Path], cwd: Path | None = None) -> Path:
    """Make server `name` start without the proxy again; the config file that changed."""
    path, data, servers = locate(name, paths, cwd)
    entry = servers[name]
    command = (
        real_command([entry["command"], *entry.get("args", [])]) if "command" in entry else None
    )
    if not command:
        raise ValueError(f"'{name}' doesn't use the proxy.")
    entry["command"], entry["args"] = command[0], command[1:]
    _write(path, data)
    return path


def _write(path: Path, data: dict[str, object]) -> None:
    """Back up config `path` to `~/.slimproof/backups/`, then replace it with `data`."""
    backups = Path.home() / ".slimproof" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    shutil.copy2(path, backups / f"{path.stem.lstrip('.')}-{stamp}{path.suffix}")  # not hidden
    write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
