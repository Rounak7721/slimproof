import json
import sys
from pathlib import Path

import pytest
from mcp import Client, types

from slimproof.server import mcp

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bloated_server.py"


@pytest.mark.anyio
async def test_audit_config_ranks_tools_from_config(tmp_path: Path) -> None:
    server = {"command": sys.executable, "args": [str(FIXTURE)]}
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"fx": server}}))

    async with Client(mcp) as client:
        result = await client.call_tool("audit_config", {"config_path": str(config)})

    text = result.content[0]
    assert isinstance(text, types.TextContent)
    assert [c["tool"] for c in json.loads(text.text)["costs"]] == ["search", "ping"]
