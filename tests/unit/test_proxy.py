import json
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters, types

from slimproof.core.client import list_tools
from slimproof.core.overrides import Override, dump, save_overrides, tool_hash
from slimproof.core.proxy import rewrite, slim_tools, track

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bloated_server.py"
READ = {"name": "read", "description": "This tool allows you to read a file.", "x-extra": 1}
READ_SLIM = types.Tool(name="read", description="Read a file.", input_schema={"type": "object"})


def _overrides(original: dict[str, object] = READ) -> dict[str, Override]:
    sha = tool_hash(types.Tool.model_validate({**original, "inputSchema": {"type": "object"}}))
    return {"read": Override(sha, READ_SLIM)}


def _read() -> dict[str, object]:
    return {**READ, "inputSchema": {"type": "object"}}


def test_slim_tools_swaps_matching_tools_and_keeps_unknown_fields() -> None:
    other = {"name": "other", "inputSchema": {"type": "object"}}

    tools, warnings = slim_tools([_read(), other], _overrides())

    assert tools == [{**dump(READ_SLIM), "x-extra": 1}, other]
    assert warnings == []


def test_slim_tools_serves_the_original_when_upstream_changed() -> None:
    changed = {**_read(), "description": "Read one file."}

    tools, warnings = slim_tools([changed], _overrides())

    assert tools == [changed]
    assert "changed since it was slimmed" in warnings[0]


def test_slim_tools_serves_the_original_when_slim_fails_guard() -> None:
    bad = READ_SLIM.model_copy(update={"input_schema": {"type": "object", "required": ["x"]}})
    overrides = {"read": Override(_overrides()["read"].original_sha256, bad)}

    tools, warnings = slim_tools([_read()], overrides)

    assert tools == [_read()]
    assert "fails the guard" in warnings[0]


def test_slim_tools_passes_malformed_tools_through() -> None:
    tools, _ = slim_tools([{"name": "read"}, "junk", {"name": ["x"]}], _overrides())
    assert tools == [{"name": "read"}, "junk", {"name": ["x"]}]


def _line(message: object) -> bytes:
    return json.dumps(message).encode()


def test_rewrite_only_touches_replies_to_tracked_tools_list() -> None:
    pending: set[str] = set()
    track(_line({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}), pending)
    track(_line({"jsonrpc": "2.0", "id": 8, "method": "resources/list"}), pending)
    reply = {"jsonrpc": "2.0", "id": 7, "result": {"tools": [_read()]}}
    other = {"jsonrpc": "2.0", "id": 8, "result": {"tools": [_read()]}}

    line, _ = rewrite(_line(other), pending, _overrides())
    assert line == _line(other)

    line, _ = rewrite(_line(reply), pending, _overrides())
    assert json.loads(line)["result"]["tools"][0]["description"] == "Read a file."
    assert pending == set()


def test_rewrite_ignores_server_requests_with_a_clashing_id() -> None:
    pending = {json.dumps(1)}
    request = _line({"jsonrpc": "2.0", "id": 1, "method": "sampling/createMessage"})

    assert rewrite(request, pending, _overrides()) == (request, [])
    assert pending == {json.dumps(1)}


def test_rewrite_handles_batches_and_non_json() -> None:
    pending: set[str] = set()
    track(_line([{"jsonrpc": "2.0", "id": "a", "method": "tools/list"}]), pending)

    assert rewrite(b"not json", pending, _overrides()) == (b"not json", [])
    line, _ = rewrite(
        _line([{"jsonrpc": "2.0", "id": "a", "result": {"tools": [_read()]}}]),
        pending,
        _overrides(),
    )
    assert json.loads(line)[0]["result"]["tools"][0]["description"] == "Read a file."


def _proxied(home: Path, name: str = "bloated") -> StdioServerParameters:
    cli = "from slimproof.cli import app; app()"
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", cli, "proxy", name, "--", sys.executable, str(FIXTURE)],
        env={"HOME": str(home), "USERPROFILE": str(home)},  # Path.home() on POSIX / Windows
    )


@pytest.mark.anyio
async def test_proxy_serves_slim_tools_and_passes_calls_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    originals = await list_tools(StdioServerParameters(command=sys.executable, args=[str(FIXTURE)]))
    search = next(t for t in originals if t.name == "search")
    save_overrides("bloated", originals, [search.model_copy(update={"description": "Search."})])

    async with Client(_proxied(tmp_path)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        result = await client.call_tool("search", {"query": "hi"})

    assert tools["search"].description == "Search."
    assert tools["ping"].description == "Reply with pong."
    assert result.content[0].text == "hi"  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_proxy_without_overrides_serves_the_originals(tmp_path: Path) -> None:
    async with Client(_proxied(tmp_path)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert tools["search"].description and tools["search"].description.startswith(
        "Search the files."
    )
    assert len(tools["search"].description) > 100
