"""Connect to an MCP server and list its tools."""

import asyncio

from mcp import Client, StdioServerParameters, types

FILESYSTEM_SERVER = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "."],
)


async def list_tools(server: StdioServerParameters) -> list[types.Tool]:
    """Start `server`, do the MCP handshake, and return all of its tools."""
    tools: list[types.Tool] = []
    async with Client(server) as client:
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
