import sys
from pathlib import Path

import httpx2
import pytest
from mcp import StdioServerParameters
from mcp.server.mcpserver import MCPServer
from starlette.types import Receive, Scope, Send

from slimproof.core.client import (
    HttpServer,
    ServerFailed,
    command_name,
    list_tools,
    url_name,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bloated_server.py"


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


@pytest.mark.parametrize(
    ("command", "name"),
    [
        (
            ["npx", "-y", "@modelcontextprotocol/server-filesystem@1.2", "/home/me"],
            "server-filesystem",
        ),
        (["uvx", "mcp-server-fetch"], "mcp-server-fetch"),
        (["/home/me/.venv/bin/python3", "/home/me/app/my_server.py"], "my_server"),
        (["C:\\Python312\\python.exe", "C:\\work\\srv.py"], "srv"),
        (["python", "-m", "pkg.server"], "pkg.server"),
        (
            ["docker", "run", "-i", "--rm", "-e", "TOKEN", "ghcr.io/github/github-mcp-server:v1"],
            "github-mcp-server",
        ),
        (["docker", "run", "-e", "TOKEN=secret", "img"], "img"),
        (["/usr/local/bin/my-mcp", "--port", "1"], "my-mcp"),
    ],
)
def test_command_name_is_short_and_path_free(command: list[str], name: str) -> None:
    assert command_name(command) == name


def test_url_name_drops_secrets() -> None:
    assert url_name("https://user:pw@api.example.com:8443/mcp?api_key=secret") == (
        "api.example.com:8443/mcp"
    )


@pytest.mark.anyio
async def test_stdio_server_log_stays_hidden(capfd: pytest.CaptureFixture[str]) -> None:
    noisy = (
        "import runpy, sys; print('server log line', file=sys.stderr); "
        f"runpy.run_path({str(FIXTURE)!r}, run_name='__main__')"
    )
    server = StdioServerParameters(command=sys.executable, args=["-c", noisy])

    tools = await list_tools(server)

    assert {t.name for t in tools} == {"search", "ping"}
    assert "server log line" not in capfd.readouterr().err


@pytest.mark.anyio
async def test_failed_stdio_server_shows_its_last_log_lines() -> None:
    crash = (
        "import sys; print('starting', file=sys.stderr); "
        "print('Error: API_KEY missing', file=sys.stderr); sys.exit(1)"
    )
    server = StdioServerParameters(command=sys.executable, args=["-c", crash])

    with pytest.raises(ServerFailed) as failed:
        await list_tools(server)

    assert str(failed.value).endswith("  | starting\n  | Error: API_KEY missing")
