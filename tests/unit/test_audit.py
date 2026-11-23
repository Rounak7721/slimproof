import json
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

from slimproof.core.audit import _error_message, audit, audit_server, tool_definitions


@pytest.mark.anyio
async def test_audit_server_costs_each_tool() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    costs = (await audit_server("fake", server)).costs

    assert len(costs) == 1
    assert costs[0].server == "fake"
    assert costs[0].tool == "ping"
    assert costs[0].tokens > 0


@pytest.mark.anyio
async def test_audit_records_broken_server(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"broken": {"command": "slimproof-no-such-cmd"}}}))

    result = await audit([config])

    assert result.costs == []
    assert "broken" in result.errors


def test_error_message_masks_secrets() -> None:
    msg = _error_message(ValueError("bad token sp-secret-123"), ["sp-secret-123"])
    assert msg == "ValueError: bad token ***"


@pytest.mark.anyio
async def test_tool_definitions_returns_full_tools() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    [tool] = await tool_definitions(server)  # type: ignore[arg-type]

    assert tool["name"] == "ping" and tool["description"] == "Reply with pong."
    assert "inputSchema" in tool
