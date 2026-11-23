from mcp import types

from slimproof.core.rules import Finding, check, sp001, sp002, sp006, sp007


def _tool(description: str) -> types.Tool:
    return types.Tool(name="read", description=description, input_schema={"type": "object"})


def _named(name: str, description: str) -> types.Tool:
    return types.Tool(name=name, description=description, input_schema={"type": "object"})


def test_sp001_flags_filler_opener() -> None:
    assert sp001(_tool("This tool allows you to read a file.")) == [
        "opens with filler 'this tool allows you to'"
    ]


def test_sp001_ignores_direct_description() -> None:
    assert sp001(_tool("Read a file.")) == []


def test_sp002_flags_identifier_name_only() -> None:
    assert sp002(_named("read_file", "read_file: reads a file.")) != []
    assert sp002(_named("read_file", "Read file contents.")) == []
    assert sp002(_named("search", "Search the files.")) == []


def test_sp007_flags_only_long_descriptions() -> None:
    assert sp007(_tool("x" * 1001)) == ["description is 1001 chars (limit 1000)"]
    assert sp007(_tool("x" * 1000)) == []


def test_sp006_flags_each_markup_kind() -> None:
    assert sp006(_tool("## Usage\n\n\n**Read** a file.")) == [
        "contains blank-line runs",
        "contains markdown headings",
        "contains bold markers",
    ]
    assert sp006(_tool("Example:\n```json\n{}\n```")) == ["contains code fences"]


def test_sp006_allows_plain_paragraphs() -> None:
    assert sp006(_tool("Read a file.\n\nReturns its text.")) == []


def test_check_returns_findings_with_ids() -> None:
    findings = check("fs", [_tool("Use this tool to read."), _tool("Read.")])
    assert findings == [Finding("SP001", "fs", "read", "opens with filler 'use this tool to'")]
