import json
from pathlib import Path

import pytest

from slimproof.core.configs import config_paths, load_servers


def test_load_servers_reads_stdio_and_skips_http(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    servers_json = {
        "fs": {"command": "npx", "args": ["-y", "server-filesystem"], "env": {"TOKEN": "x"}},
        "remote": {"type": "http", "url": "https://example.com/mcp"},
    }
    config.write_text(json.dumps({"mcpServers": servers_json}), encoding="utf-8")

    servers = load_servers(config)

    assert list(servers) == ["fs"]
    assert servers["fs"].args == ["-y", "server-filesystem"]


def test_config_paths_finds_existing_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    (tmp_path / ".claude.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")

    assert config_paths(tmp_path) == [tmp_path / ".mcp.json", tmp_path / ".claude.json"]
