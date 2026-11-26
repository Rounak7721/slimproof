"""Deterministic bloat rules: each finds one kind of wasted tokens in a tool definition."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

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


@dataclass(frozen=True)
class ServerRule:
    """A bloat rule that compares all tools of one server: returns (tool, message) pairs."""

    id: str
    title: str
    check: Callable[[list[types.Tool]], list[tuple[str, str]]]


FILLER = (
    "this tool allows you to",
    "this tool lets you",
    "this tool is used to",
    "this tool will",
    "use this tool to",
    "a tool that",
    "allows you to",
)

MARKUP = {
    "blank-line runs": re.compile(r"\n\s*\n\s*\n"),
    "space runs": re.compile(r"[ \t]{3,}"),
    "markdown headings": re.compile(r"^#{1,6} ", re.MULTILINE),
    "bold markers": re.compile(r"\*\*"),
    "code fences": re.compile(r"```"),
}

NOISE = {
    "a",
    "an",
    "the",
    "that",
    "is",
    "of",
    "which",
    "value",
    "parameter",
    "param",
    "string",
    "str",
    "integer",
    "int",
    "number",
    "boolean",
    "bool",
    "array",
    "list",
    "object",
}

LIST_WORDS = {"one", "or", "and", "either", "must", "be", "can", "values", "options"}


def _params(tool: types.Tool) -> dict[str, dict[str, Any]]:
    """Top-level parameters of `tool`: name -> its JSON Schema (`true`/`false` schemas skipped)."""
    properties = tool.input_schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {name: schema for name, schema in properties.items() if isinstance(schema, dict)}


def _words(text: str) -> set[str]:
    """Lowercase words in `text`, punctuation dropped."""
    return set(re.findall(r"[a-z]+", text.lower()))


def _sentences(text: str, min_chars: int = 40) -> list[str]:
    """Lowercased sentences of `text` long enough to be worth comparing."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip().lower() for p in parts if len(p.strip()) >= min_chars]


def sp001(tool: types.Tool) -> list[str]:
    """Description opens with filler like "This tool allows you to"."""
    desc = (tool.description or "").strip().lower()
    match = next((f for f in FILLER if desc.startswith(f)), None)
    return [f"opens with filler '{match}'"] if match else []


def sp002(tool: types.Tool) -> list[str]:
    """Description repeats the tool's identifier, like `read_file`."""
    camel = re.search(r"[a-z][A-Z]", tool.name)
    if not camel and not any(sep in tool.name for sep in "_-."):
        return []  # single words like "search" appear naturally in prose
    desc = (tool.description or "").lower()
    return [f"repeats the tool name '{tool.name}'"] if tool.name.lower() in desc else []


def sp003(tool: types.Tool) -> list[str]:
    """A parameter description only restates its name and type ("A string that is the path")."""
    found = []
    for name, schema in _params(tool).items():
        words = _words(schema.get("description", ""))
        if words and words <= NOISE | _words(name):
            found.append(f"'{name}' description only restates its name and type")
    return found


def sp004(tool: types.Tool, min_values: int = 3) -> list[str]:
    """A parameter description only lists its enum values ("One of: read, write, append")."""
    found = []
    for name, schema in _params(tool).items():
        values = [str(v) for v in schema.get("enum", [])]
        desc = schema.get("description", "")
        leftover = _words(desc) - _words(" ".join(values)) - NOISE - LIST_WORDS
        if len(values) >= min_values and desc and not leftover:
            found.append(f"'{name}' description only lists its {len(values)} enum values")
    return found


def sp005(tool: types.Tool) -> list[str]:
    """Description carries markdown or whitespace the model doesn't need."""
    desc = tool.description or ""
    return [f"contains {kind}" for kind, pattern in MARKUP.items() if pattern.search(desc)]


def sp006(tool: types.Tool, limit: int = 1000) -> list[str]:
    """Description is longer than `limit` characters."""
    n = len(tool.description or "")
    return [f"description is {n} chars (limit {limit})"] if n > limit else []


def sp007(tools: list[types.Tool]) -> list[tuple[str, str]]:
    """The same sentence appears in more than one tool's description."""
    first_seen: dict[str, str] = {}  # sentence -> first tool that used it
    found = []
    for tool in tools:
        for s in _sentences(tool.description or ""):
            if first_seen.get(s, tool.name) != tool.name:
                found.append(
                    (tool.name, f"repeats a sentence from '{first_seen[s]}': \"{s[:60]}\"")
                )
            first_seen.setdefault(s, tool.name)
    return found


def sp008(tools: list[types.Tool], threshold: float = 0.85) -> list[tuple[str, str]]:
    """Two tools have near-identical descriptions, so the model may pick the wrong one."""
    found = []
    for a, b in combinations(tools, 2):  # O(n^2) pairs: fine for a few hundred tools
        if not (a.description and b.description):
            continue
        ratio = SequenceMatcher(None, a.description, b.description).ratio()
        if ratio >= threshold:
            found.append((a.name, f"{ratio:.0%} similar to '{b.name}': clarify, don't shorten"))
    return found


RULES = [
    Rule("SP001", "Filler opener", sp001),
    Rule("SP002", "Repeats tool name", sp002),
    Rule("SP003", "Param restates type", sp003),
    Rule("SP004", "Enum repeated in prose", sp004),
    Rule("SP005", "Markup bloat", sp005),
    Rule("SP006", "Long description", sp006),
]

SERVER_RULES = [
    ServerRule("SP007", "Duplicated text", sp007),
    ServerRule("SP008", "Ambiguous tools", sp008),
]


def check(server: str, tools: list[types.Tool]) -> list[Finding]:
    """Run every rule on every tool of `server`."""
    per_tool = [
        Finding(rule.id, server, tool.name, msg)
        for tool in tools
        for rule in RULES
        for msg in rule.check(tool)
    ]
    cross = [Finding(r.id, server, t, msg) for r in SERVER_RULES for t, msg in r.check(tools)]
    return per_tool + cross
