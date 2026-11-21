import json
from pathlib import Path

from slimproof.core.configs import load_servers


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
