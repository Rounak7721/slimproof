import json
import os
import stat
import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from slimproof.core.apply import apply, real_command, real_server, revert
from slimproof.core.overrides import overrides_path

ENTRY = {"command": "npx", "args": ["-y", "pkg", "${HOME}"], "env": {"TOKEN": "${TOKEN}"}}


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def _config(tmp_path: Path, servers: dict[str, object]) -> Path:
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}))
    return path


def _save_overrides(name: str) -> None:
    path = overrides_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "server": name, "tools": {}}))


def test_real_command_unwraps_only_proxy_commands() -> None:
    proxied = ["uvx", "slimproof", "proxy", "fs", "--", "npx", "-y", "pkg"]
    assert real_command(proxied) == ["npx", "-y", "pkg"]
    assert real_command(["npx", "-y", "pkg"]) is None
    assert real_command(["uvx", "slimproof", "proxy", "fs", "--"]) is None


def test_real_server_unwraps_the_proxy_and_keeps_env() -> None:
    server = StdioServerParameters(
        command="uvx", args=["slimproof", "proxy", "fs", "--", "npx", "pkg"], env={"A": "1"}
    )
    assert real_server(server) == StdioServerParameters(command="npx", args=["pkg"], env={"A": "1"})


def test_apply_then_revert_round_trips_the_raw_entry(tmp_path: Path, home: Path) -> None:
    config = _config(tmp_path, {"fs": ENTRY, "other": {"command": "x"}})
    _save_overrides("fs")

    assert apply("fs", [config], tmp_path) == config
    entry = json.loads(config.read_text())["mcpServers"]["fs"]
    assert entry["command"] == "uvx"
    assert entry["args"] == ["slimproof", "proxy", "fs", "--", "npx", "-y", "pkg", "${HOME}"]
    assert entry["env"] == {"TOKEN": "${TOKEN}"}  # never expanded into the file
    revert("fs", [config], tmp_path)
    backups = sorted(p.name for p in (home / ".slimproof" / "backups").iterdir())
    assert len(backups) == 2 and backups[0].startswith("mcp-") and backups[0].endswith(".json")
    assert json.loads(config.read_text())["mcpServers"] == {"fs": ENTRY, "other": {"command": "x"}}


def test_apply_edits_the_local_scope_entry_first(tmp_path: Path) -> None:
    user = tmp_path / ".claude.json"
    project = {"mcpServers": {"fs": {"command": "local-fs"}}}
    user.write_text(
        json.dumps({"mcpServers": {"fs": ENTRY}, "projects": {tmp_path.as_posix(): project}})
    )
    _save_overrides("fs")

    apply("fs", [user], tmp_path)

    data = json.loads(user.read_text())
    assert data["projects"][tmp_path.as_posix()]["mcpServers"]["fs"]["command"] == "uvx"
    assert data["mcpServers"]["fs"] == ENTRY


def test_apply_refuses_bad_cases(tmp_path: Path) -> None:
    config = _config(tmp_path, {"fs": ENTRY, "web": {"type": "http", "url": "https://x"}})

    with pytest.raises(ValueError, match="No slim tools saved"):
        apply("fs", [config], tmp_path)
    _save_overrides("fs")
    _save_overrides("web")
    with pytest.raises(ValueError, match="not a stdio server"):
        apply("web", [config], tmp_path)
    with pytest.raises(ValueError, match="No server named 'nope'"):
        _save_overrides("nope")
        apply("nope", [config], tmp_path)
    apply("fs", [config], tmp_path)
    with pytest.raises(ValueError, match="already uses the proxy"):
        apply("fs", [config], tmp_path)
    revert("fs", [config], tmp_path)
    with pytest.raises(ValueError, match="doesn't use the proxy"):
        revert("fs", [config], tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_apply_keeps_owner_only_permissions(tmp_path: Path) -> None:
    config = _config(tmp_path, {"fs": ENTRY})
    os.chmod(config, 0o600)
    _save_overrides("fs")

    apply("fs", [config], tmp_path)

    assert stat.S_IMODE(config.stat().st_mode) == 0o600
