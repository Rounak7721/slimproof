import json
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from slimproof.core.client import HttpServer
from slimproof.core.configs import config_paths, find_server, load_servers


def test_load_servers_reads_stdio_and_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SP_TEST_TOKEN", "abc")
    config = tmp_path / ".mcp.json"
    servers_json = {
        "fs": {"command": "npx", "args": ["-y", "server-filesystem"], "env": {"TOKEN": "x"}},
        "remote": {
            "type": "http",
            "url": "https://example.com/mcp",
            "headers": {"Authorization": "Bearer ${SP_TEST_TOKEN}"},
        },
        "legacy": {"type": "sse", "url": "https://example.com/sse"},
    }
    config.write_text(json.dumps({"mcpServers": servers_json}), encoding="utf-8")

    servers, skipped = load_servers(config)

    assert servers["fs"] == StdioServerParameters(
        command="npx", args=["-y", "server-filesystem"], env={"TOKEN": "x"}
    )
    assert servers["remote"] == HttpServer(
        "https://example.com/mcp", {"Authorization": "Bearer abc"}
    )
    assert skipped == {"legacy": "sse servers not supported yet"}


def test_config_paths_finds_existing_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    (tmp_path / ".claude.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")

    assert config_paths(tmp_path) == [tmp_path / ".mcp.json", tmp_path / ".claude.json"]


def test_load_servers_reads_local_scope_for_cwd(tmp_path: Path) -> None:
    config = tmp_path / ".claude.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {"user": {"command": "a"}},
                "projects": {
                    "/work/app": {"mcpServers": {"local": {"command": "b"}}},
                    "/work/other": {"mcpServers": {"elsewhere": {"command": "c"}}},
                },
            }
        )
    )

    servers, _ = load_servers(config, cwd=Path("/work/app"))

    assert servers.keys() == {"user", "local"}


def test_find_server_by_name(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"fs": {"command": "npx"}}}), encoding="utf-8")

    assert find_server("fs", [config]) == StdioServerParameters(command="npx", args=[])
    with pytest.raises(ValueError, match="'nope'"):
        find_server("nope", [config])
