"""A fake MCP server with one bloated and one lean tool, for tests."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("bloated")

BLOATED = "Search the files. " + "This tool is very powerful and useful. " * 40


@server.tool(description=BLOATED)
def search(query: str) -> str:
    return query


@server.tool()
def ping() -> str:
    """Reply with pong."""
    return "pong"


if __name__ == "__main__":
    server.run()
