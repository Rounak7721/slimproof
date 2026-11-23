from mcp import types

from slimproof.core.rules import Finding, check, sp001


def _tool(description: str) -> types.Tool:
    return types.Tool(name="read", description=description, input_schema={"type": "object"})


def test_sp001_flags_filler_opener() -> None:
    assert sp001(_tool("This tool allows you to read a file.")) == [
        "opens with filler 'this tool allows you to'"
    ]


def test_sp001_ignores_direct_description() -> None:
    assert sp001(_tool("Read a file.")) == []


def test_check_returns_findings_with_ids() -> None:
    findings = check("fs", [_tool("Use this tool to read."), _tool("Read.")])
    assert findings == [Finding("SP001", "fs", "read", "opens with filler 'use this tool to'")]
