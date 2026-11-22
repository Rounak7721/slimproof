import httpx2
import pytest
from mcp.server.mcpserver import MCPServer
from starlette.types import Receive, Scope, Send

from slimproof.core.client import HttpServer, list_tools


@pytest.mark.anyio
async def test_list_tools_return_server_tools() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    tools = await list_tools(server=server)

    assert [t.name for t in tools] == ["ping"]


@pytest.mark.anyio
async def test_list_tools_over_http_sends_headers() -> None:
    server = MCPServer("fake")

    @server.tool()
    def ping() -> str:
        """Reply with pong."""
        return "pong"

    app = server.streamable_http_app()
    seen: list[bytes] = []

    async def spy(scope: Scope, receive: Receive, send: Send) -> None:
        seen.extend(v for k, v in scope.get("headers", []) if k == b"authorization")
        await app(scope, receive, send)

    remote = HttpServer("http://127.0.0.1:8000/mcp", {"Authorization": "Bearer t"})
    async with app.router.lifespan_context(app):
        tools = await list_tools(remote, transport=httpx2.ASGITransport(app=spy))

    assert [t.name for t in tools] == ["ping"]
    assert b"Bearer t" in seen
