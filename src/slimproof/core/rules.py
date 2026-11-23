"""Deterministic bloat rules: each finds one kind of wasted tokens in a tool definition."""

from collections.abc import Callable
from dataclasses import dataclass

from mcp import types


@dataclass(frozen=True)
class Finding:
    """One rule firing on one tool."""

    rule: str
    server: str
    tool: str
    message: str


@dataclass(frozen=True)
class Rule:
    """A bloat rule: a stable ID, a short title, and a check that returns messages."""

    id: str
    title: str
    check: Callable[[types.Tool], list[str]]


FILLER = (
    "this tool allows you to",
    "this tool lets you",
    "this tool is used to",
    "this tool will",
    "use this tool to",
    "a tool that",
    "allows you to",
)


def sp001(tool: types.Tool) -> list[str]:
    """Description opens with filler like "This tool allows you to"."""

    desc = (tool.description or "").strip().lower()
    match = next((f for f in FILLER if desc.startswith(f)), None)

    return [f"opens with filler '{match}'"] if match else []


RULES = [Rule("SP001", "Filler opener", sp001)]


def check(server: str, tools: list[types.Tool]) -> list[Finding]:
    """Run every rule on every tool of `server`."""

    return [
        Finding(rule.id, server, tool.name, msg)
        for tool in tools
        for rule in RULES
        for msg in rule.check(tool)
    ]
