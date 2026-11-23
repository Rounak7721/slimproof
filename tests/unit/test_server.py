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


@pytest.mark.anyio
async def test_audit_server_returns_findings() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("audit_server", {"command": [sys.executable, str(FIXTURE)]})

    text = result.content[0]
    assert isinstance(text, types.TextContent)
    assert {f["rule"] for f in json.loads(text.text)["findings"]} == {"SP006"}


@pytest.mark.anyio
async def test_audit_server_without_target_is_tool_error() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("audit_server", {})

    assert result.is_error


@pytest.mark.anyio
async def test_compare_reports_savings() -> None:
    original = {
        "name": "read",
        "description": "This tool allows you to read a file.",
        "inputSchema": {"type": "object"},
    }
    slim = {**original, "description": "Read a file."}

    async with Client(mcp) as client:
        result = await client.call_tool("compare", {"original": [original], "slim": [slim]})

    text = result.content[0]
    assert isinstance(text, types.TextContent)
    [change] = json.loads(text.text)
    assert change["problems"] == [] and change["after"] < change["before"]


@pytest.mark.anyio
async def test_get_tools_output_feeds_compare() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_tools", {"command": [sys.executable, str(FIXTURE)]})
        text = result.content[0]
        assert isinstance(text, types.TextContent)
        tools = json.loads(text.text)
        result = await client.call_tool("compare", {"original": tools, "slim": tools})

    text = result.content[0]
    assert isinstance(text, types.TextContent)
    assert [c["problems"] for c in json.loads(text.text)] == [[], []]
