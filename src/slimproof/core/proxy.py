"""Stdio proxy: relay an MCP server unchanged, except that `tools/list` replies get slim tools.

Every message passes through as raw JSON-RPC lines. Only replies to the client's own
`tools/list` requests (matched by id) are rewritten, so calls, resources, prompts and
future protocol methods work as if the client talked to the server directly.
"""

import json
import os
import shutil
import sys
import threading
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

import anyio
import anyio.lowlevel
from anyio.abc import Process
from anyio.streams.memory import MemoryObjectSendStream
from mcp import types

from slimproof.core.guard import WORDING, guard
from slimproof.core.overrides import Override, dump, load_overrides, tool_hash


def slim_tools(tools: list[Any], overrides: dict[str, Override]) -> tuple[list[Any], list[str]]:
    """`tools` (raw `tools/list` JSON) with the saved slim versions swapped in, plus warnings.

    A tool keeps its original definition if it changed since its override was saved,
    or if the saved slim version fails the guard (for example after a hand edit).
    """
    out: list[Any] = []
    warnings: list[str] = []
    for raw in tools:
        name = raw.get("name") if isinstance(raw, dict) else None
        override = overrides.get(name) if isinstance(name, str) else None
        try:
            live = types.Tool.model_validate(raw) if override else None
        except ValueError:  # a malformed tool goes to the client as it is
            live = None
        if override is None or live is None:
            out.append(raw)
        elif tool_hash(live) != override.original_sha256:
            warnings.append(f"{name} changed since it was slimmed; serving the original")
            out.append(raw)
        elif problems := guard(live, override.slim):
            warnings.append(f"{name}: saved slim version fails the guard ({problems[0]})")
            out.append(raw)
        else:
            # Keep fields that the SDK's Tool model doesn't know; the slim version wins elsewhere.
            out.append({k: v for k, v in raw.items() if k not in WORDING} | dump(override.slim))
    return out, warnings


def _parse(line: bytes) -> list[Any]:
    """The JSON-RPC messages in `line` (a batch is a list); [] if it isn't JSON."""
    try:
        data = json.loads(line)
    except ValueError:
        return []
    return data if isinstance(data, list) else [data]


def track(line: bytes, pending: set[str]) -> None:
    """Add the id of every `tools/list` request in client `line` to `pending`."""
    for m in _parse(line):
        if isinstance(m, dict) and m.get("method") == "tools/list" and "id" in m:
            pending.add(json.dumps(m["id"]))


def rewrite(
    line: bytes, pending: set[str], overrides: dict[str, Override]
) -> tuple[bytes, list[str]]:
    """Server `line`, with slim tools in any reply to a `pending` `tools/list`; plus warnings."""
    if not pending:  # don't parse big resource or call results for nothing
        return line, []
    messages = _parse(line)
    warnings: list[str] = []
    changed = False
    for m in messages:
        if not isinstance(m, dict) or "method" in m or "id" not in m:
            continue  # a request or notification from the server, not a reply
        key = json.dumps(m["id"])
        if key not in pending:
            continue
        pending.discard(key)
        result = m.get("result")
        if overrides and isinstance(result, dict) and isinstance(result.get("tools"), list):
            result["tools"], new = slim_tools(result["tools"], overrides)
            warnings += new
            changed = True
    if not changed:
        return line, warnings
    data = messages if line.lstrip().startswith(b"[") else messages[0]
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.encode("utf-8") + b"\n", warnings


def _warn(message: str) -> None:
    """Log to stderr; MCP clients keep a server's stderr in their logs."""
    print(f"slimproof proxy: {message}", file=sys.stderr, flush=True)


async def run_proxy(server: str, command: list[str]) -> int:
    """Start `command` as the real MCP server and relay stdio until it exits; its exit code.

    If the overrides of `server` can't be loaded, the original tools pass through.
    """
    try:
        overrides = load_overrides(server)
    except ValueError as e:
        _warn(f"{e}; serving the original tools")
        overrides = {}
    if not overrides:
        _warn(f"no slim tools saved for '{server}'; serving the original tools")

    pending: set[str] = set()
    program = shutil.which(command[0]) or command[0]  # finds npx.cmd and the like on Windows
    # stderr=None: the server logs straight to the client. env is inherited in full,
    # unlike the SDK's stdio client, which passes only a few safe variables.
    async with await anyio.open_process([program, *command[1:]], stderr=None) as process:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_client_to_server, process, pending)
            await _server_to_client(process, pending, overrides)
            tg.cancel_scope.cancel()  # the server is gone; stop reading the client
        return await process.wait()


async def _lines(chunks: AsyncIterable[bytes]) -> AsyncIterator[bytes]:
    """Split a byte stream into lines, each with its newline (the last may lack one)."""
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        if b"\n" in chunk:
            *lines, rest = buffer.split(b"\n")
            buffer = bytearray(rest)
            for line in lines:
                yield bytes(line) + b"\n"
    if buffer:
        yield bytes(buffer)


async def _client_to_server(process: Process, pending: set[str]) -> None:
    """Copy client lines to the server; close its stdin when the client closes ours."""
    assert process.stdin
    send, receive = anyio.create_memory_object_stream[bytes]()
    token = anyio.lowlevel.current_token()
    threading.Thread(target=_read_stdin, args=(send, token), daemon=True).start()
    async with receive:
        async for line in _lines(receive):
            track(line, pending)
            try:
                await process.stdin.send(line)
            except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                return  # the server exited
    await process.stdin.aclose()


def _read_stdin(send: MemoryObjectSendStream[bytes], token: anyio.lowlevel.EventLoopToken) -> None:
    """Read stdin in a daemon thread, so a blocked read can't keep the proxy alive at exit.

    A thread works on every OS (asyncio can't read a stdin pipe on Windows). `os.read` takes
    no lock, unlike `sys.stdin.buffer`, whose lock crashes Python's exit while a read waits.
    """
    fd = sys.stdin.fileno()
    try:
        while chunk := os.read(fd, 65536):
            anyio.from_thread.run(send.send, chunk, token=token)
        anyio.from_thread.run_sync(send.close, token=token)
    except (anyio.RunFinishedError, anyio.BrokenResourceError):
        pass  # the proxy is shutting down


async def _server_to_client(
    process: Process, pending: set[str], overrides: dict[str, Override]
) -> None:
    """Copy server lines to our stdout, rewriting `tools/list` replies, until the server exits."""
    assert process.stdout
    out = sys.stdout.buffer
    try:
        async for line in _lines(process.stdout):
            line, warnings = rewrite(line, pending, overrides)
            for warning in warnings:
                _warn(warning)
            out.write(line)
            out.flush()
    except BrokenPipeError:
        pass  # the client is gone
