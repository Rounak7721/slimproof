"""Connect to an MCP server and list its tools."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2
from mcp import Client, StdioServerParameters, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer

# Seconds to wait for each MCP reply, the handshake included. A first `npx -y` run
# downloads the package inside this time, so keep it generous.
TIMEOUT = 60


@dataclass(frozen=True)
class HttpServer:
    """An MCP server reached over Streamable HTTP."""

    url: str
    headers: dict[str, str] = field(default_factory=dict)


class NeedsLogin(Exception):
    """An HTTP server answered 401: it wants an OAuth login, which slimproof can't do yet."""

    def __init__(self) -> None:
        super().__init__("needs OAuth login; add an Authorization header in the config to audit it")


async def _raise_on_401(response: httpx2.Response) -> None:
    """httpx response hook: the MCP SDK hides HTTP statuses, so catch 401 here."""
    if response.status_code == 401:
        raise NeedsLogin()


def server_from(
    command: list[str] | None, url: str | None
) -> tuple[str, StdioServerParameters | HttpServer]:
    """Build a server from a stdio command or an HTTP url (exactly one): (display name, server)."""
    if bool(command) == bool(url):
        raise ValueError("Give exactly one of a stdio command or a url.")
    if url:
        return url_name(url), HttpServer(url)
    assert command  # narrows the type for pyright
    return command_name(command), StdioServerParameters(command=command[0], args=command[1:])


LAUNCHERS = {"npx", "uvx", "bunx", "pnpx", "pnpm", "npm", "yarn", "node", "bun", "deno"}
LAUNCHERS |= {"python", "python3", "py", "uv", "pipx", "docker", "podman"}
SUBCOMMANDS = {"run", "dlx", "exec", "x", "tool"}
VALUE_FLAGS = {"-e", "--env", "-v", "--volume", "--from", "--with", "--directory", "--name"}


def _last_part(path: str) -> str:
    """Last segment of a POSIX or Windows path, URL path or package name."""
    return re.split(r"[\\/]", path.rstrip("\\/"))[-1]


def command_name(command: list[str]) -> str:
    """Short, path-free name for a stdio command: the package or script it launches.

    `npx -y @scope/server-x@1.2 /dir` -> `server-x`, `/venv/bin/python app.py` -> `app`.
    """
    program = re.sub(r"\.(exe|cmd|bat)$", "", _last_part(command[0]), flags=re.IGNORECASE)
    if program.lower() not in LAUNCHERS:
        return program
    skip_next = False
    for arg in command[1:]:
        if skip_next or arg.startswith("-") or arg in SUBCOMMANDS or "=" in arg:
            skip_next = arg in VALUE_FLAGS
            continue
        name = _last_part(arg).split(":")[0]  # docker image tag
        name = re.sub(r"\.(py|js|mjs|cjs|ts)$", "", name)
        return name.rsplit("@", 1)[0] if name.rfind("@") > 0 else name.lstrip("@")
    return program


def url_name(url: str) -> str:
    """Host and path of `url`; never the query or user:password, which can hold secrets."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    return f"{host}:{parts.port}{parts.path}" if parts.port else f"{host}{parts.path}"


async def list_tools(
    server: StdioServerParameters | MCPServer | HttpServer,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> list[types.Tool]:
    """Connect to `server` and return all of its tools.

    `transport` replaces the network layer for HTTP servers (tests pass an in-process app).
    """
    if not isinstance(server, HttpServer):
        return await _all_tools(Client(server, read_timeout_seconds=TIMEOUT))
    async with httpx2.AsyncClient(
        headers=server.headers,
        transport=transport,
        timeout=TIMEOUT,
        event_hooks={"response": [_raise_on_401]},
    ) as http:
        mcp_transport = streamable_http_client(server.url, http_client=http)
        return await _all_tools(Client(mcp_transport, read_timeout_seconds=TIMEOUT))


async def _all_tools(client: Client) -> list[types.Tool]:
    """Do the MCP handshake on `client` and page through `tools/list`."""
    tools: list[types.Tool] = []
    seen: set[str] = set()  # a buggy server that repeats a cursor would loop forever
    async with client:
        cursor: str | None = None
        while True:
            page = await client.list_tools(cursor=cursor)
            tools.extend(page.tools)
            cursor = page.next_cursor
            if cursor is None or cursor in seen:
                return tools
            seen.add(cursor)
