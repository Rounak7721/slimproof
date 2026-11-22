import pytest
from mcp.server.mcpserver import MCPServer

from slimproof.core.audit import audit_server


@pytest.mark.anyio
async def test_audit_server_costs_each_tool() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    costs = await audit_server("fake", server)

    assert len(costs) == 1
    assert costs[0].server == "fake"
    assert costs[0].tool == "ping"
    assert costs[0].tokens > 0
