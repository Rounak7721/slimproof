import pytest
from mcp.server.mcpserver import MCPServer

from slimproof.core.client import list_tools


@pytest.mark.anyio
async def test_list_tools_return_server_tools() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    tools = await list_tools(server=server)

    assert [t.name for t in tools] == ["ping"]
