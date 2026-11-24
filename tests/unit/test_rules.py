from typing import Any

from mcp import types

from slimproof.core.rules import (
    Finding,
    check,
    sp001,
    sp002,
    sp003,
    sp004,
    sp005,
    sp006,
    sp007,
    sp008,
)


def _tool(description: str) -> types.Tool:
    return types.Tool(name="read", description=description, input_schema={"type": "object"})


def _named(name: str, description: str) -> types.Tool:
    return types.Tool(name=name, description=description, input_schema={"type": "object"})


def _params_tool(properties: dict[str, Any]) -> types.Tool:
    schema = {"type": "object", "properties": properties}
    return types.Tool(name="x", description="d", input_schema=schema)


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


def test_sp002_flags_camel_case_name() -> None:
    assert sp002(_named("getFileContents", "getFileContents: returns a file.")) != []
    assert sp002(_named("getFileContents", "Get the file contents.")) == []


def test_sp003_flags_restated_type_only() -> None:
    restated = {"type": "string", "description": "A string that is the path."}
    useful = {"type": "string", "description": "Absolute path inside the vault."}
    assert sp003(_params_tool({"path": restated})) != []
    assert sp003(_params_tool({"path": useful, "x": {"type": "string"}})) == []


def test_sp004_flags_pure_enum_lists_only() -> None:
    mode = {"type": "string", "enum": ["read", "write", "append"]}

    def desc(text: str) -> types.Tool:
        return _params_tool({"mode": {**mode, "description": text}})

    assert sp004(desc("One of: read, write, append."))
    assert sp004(desc("Must be `read`, `write` or `append`."))
    assert sp004(desc("read opens it, write replaces it, append adds.")) == []
    assert sp004(_params_tool({"mode": mode})) == []


def test_sp005_flags_each_markup_kind() -> None:
    assert sp005(_tool("## Usage\n\n\n**Read** a file.")) == [
        "contains blank-line runs",
        "contains markdown headings",
        "contains bold markers",
    ]
    assert sp005(_tool("Example:\n```json\n{}\n```")) == ["contains code fences"]


def test_sp005_allows_plain_paragraphs() -> None:
    assert sp005(_tool("Read a file.\n\nReturns its text.")) == []


def test_sp006_flags_only_long_descriptions() -> None:
    assert sp006(_tool("x" * 1001)) == ["description is 1001 chars (limit 1000)"]
    assert sp006(_tool("x" * 1000)) == []


def test_sp007_flags_sentence_repeated_in_another_tool() -> None:
    note = "Paths are relative to the vault root and must not start with a slash."
    tools = [_named("read", "Read a note. " + note), _named("write", "Write. " + note)]
    assert [tool for tool, _ in sp007(tools)] == ["write"]


def test_sp008_flags_near_identical_tools_only() -> None:
    a = _named("a", "Read a note from the vault.")
    b = _named("b", "Read a note from the vault!")
    c = _named("c", "Delete every file in a folder.")
    assert sp008([a, b, c]) == [("a", "96% similar to 'b': clarify, don't shorten")]


def test_check_returns_findings_with_ids() -> None:
    findings = check("fs", [_tool("Use this tool to read."), _tool("Read.")])
    assert findings == [Finding("SP001", "fs", "read", "opens with filler 'use this tool to'")]
