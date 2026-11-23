"""Connect to an MCP server and list its tools."""

import asyncio
from dataclasses import dataclass, field

import httpx2
from mcp import Client, StdioServerParameters, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer

FILESYSTEM_SERVER = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "."],
)


@dataclass(frozen=True)
class HttpServer:
    """An MCP server reached over Streamable HTTP."""

    url: str
    headers: dict[str, str] = field(default_factory=dict)


def server_from(
    command: list[str] | None, url: str | None
) -> tuple[str, StdioServerParameters | HttpServer]:
    """Build a server from a stdio command or an HTTP url (exactly one): (display name, server)."""
    if bool(command) == bool(url):
        raise ValueError("Give either a stdio command or a url, not both.")
    if url:
        return url, HttpServer(url)
    assert command  # narrows the type for pyright
    return command[0], StdioServerParameters(command=command[0], args=command[1:])


async def list_tools(
    server: StdioServerParameters | MCPServer | HttpServer,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> list[types.Tool]:
    """Connect to `server` and return all of its tools.

    `transport` replaces the network layer for HTTP servers (tests pass an in-process app).
    """
    if not isinstance(server, HttpServer):
        return await _all_tools(Client(server))
    async with httpx2.AsyncClient(headers=server.headers, transport=transport, timeout=30) as http:
        return await _all_tools(Client(streamable_http_client(server.url, http_client=http)))


async def _all_tools(client: Client) -> list[types.Tool]:
    """Do the MCP handshake on `client` and page through `tools/list`."""
    tools: list[types.Tool] = []
    async with client:
        cursor: str | None = None
        while True:
            page = await client.list_tools(cursor=cursor)
            tools.extend(page.tools)
            cursor = page.next_cursor
            if cursor is None:
                return tools


async def main() -> None:
    """Print each tool on the filesystem server."""
    for tool in await list_tools(FILESYSTEM_SERVER):
        print(f"{tool.name}: {tool.description}")


if __name__ == "__main__":
    asyncio.run(main())
