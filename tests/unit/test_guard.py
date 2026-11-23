from typing import Any

from mcp import types

from slimproof.core.guard import compare, guard

PATH = {"path": {"type": "string", "description": "Path of the file to read, relative to root."}}


def _tool(description: str, properties: dict[str, Any]) -> types.Tool:
    schema = {"type": "object", "properties": properties, "required": ["path"]}
    return types.Tool(name="read", description=description, input_schema=schema)


def _named(name: str, description: str) -> types.Tool:
    return types.Tool(name=name, description=description, input_schema={"type": "object"})


def test_wording_only_changes_pass() -> None:
    slim = _tool("Read a file.", {"path": {"type": "string", "description": "File path."}})
    assert guard(_tool("This tool reads a file.", PATH), slim) == []


def test_type_change_fails_with_exact_path() -> None:
    slim = _tool("x", {"path": {"type": "integer"}})
    assert guard(_tool("x", PATH), slim) == [
        "read.inputSchema.properties.path.type: 'string' -> 'integer'"
    ]


def test_param_named_title_is_structure_not_wording() -> None:
    titled = {"title": {"type": "string", "description": "Note title."}}
    assert guard(_tool("x", titled), _tool("x", {})) == [
        "read.inputSchema.properties.title: removed"
    ]


def test_default_values_are_data() -> None:
    before = {"o": {"type": "object", "default": {"description": "keep"}}}
    after = {"o": {"type": "object", "default": {"description": "changed"}}}
    assert guard(_tool("x", before), _tool("x", after)) != []


def test_compare_reports_savings_and_unpaired_tools() -> None:
    original = [
        _named("read", "This tool allows you to read a file from disk."),
        _named("ping", "Pong."),
    ]
    slim = [_named("read", "Read a file."), _named("pong", "Pong.")]

    changes = compare(original, slim)

    assert [c.problems for c in changes] == [
        [],
        ["missing from the slim version"],
        ["not in the original"],
    ]
    assert changes[0].after < changes[0].before
