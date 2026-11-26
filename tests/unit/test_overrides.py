import json
from pathlib import Path

import pytest
from mcp import types

from slimproof.core.overrides import load_overrides, overrides_path, save_overrides, tool_hash


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def _tool(description: str, name: str = "read") -> types.Tool:
    return types.Tool(name=name, description=description, input_schema={"type": "object"})


def test_tool_hash_ignores_key_order_but_sees_changes() -> None:
    a = types.Tool.model_validate({"name": "read", "inputSchema": {"type": "object"}})
    b = types.Tool.model_validate({"inputSchema": {"type": "object"}, "name": "read"})
    assert tool_hash(a) == tool_hash(b)
    assert tool_hash(_tool("Read a file.")) != tool_hash(_tool("Read a file!"))


@pytest.mark.parametrize("name", ["../x", "a/b", "a\\b", "", "..", "."])
def test_overrides_path_rejects_names_that_leave_the_folder(name: str) -> None:
    with pytest.raises(ValueError):
        overrides_path(name)


def test_overrides_path_explains_plugin_servers() -> None:
    with pytest.raises(ValueError, match="comes from a plugin"):
        overrides_path("plugin:github:github")


def test_save_then_load_round_trips(home: Path) -> None:
    original = _tool("This tool allows you to read a file.")

    path = save_overrides("fs", [original], [_tool("Read a file.")])

    assert path == home / ".slimproof" / "overrides" / "fs.json"
    assert json.loads(path.read_text())["version"] == 1
    loaded = load_overrides("fs")["read"]
    assert loaded.original_sha256 == tool_hash(original)
    assert loaded.slim.description == "Read a file."


def test_save_refuses_guard_failures_and_unknown_tools() -> None:
    original = _tool("Read a file.")
    renamed = _tool("Read a file.", name="read_file")
    changed = types.Tool(name="read", input_schema={"type": "object", "required": ["path"]})

    with pytest.raises(ValueError, match="not a tool of fs"):
        save_overrides("fs", [original], [renamed])
    with pytest.raises(ValueError, match="required"):
        save_overrides("fs", [original], [changed])
    assert load_overrides("fs") == {}


def test_save_keeps_earlier_tools_only_while_unchanged() -> None:
    read, write = _tool("Read a file, long."), _tool("Write a file, long.", name="write")
    save_overrides("fs", [read, write], [_tool("Read a file."), _tool("Write.", name="write")])

    save_overrides("fs", [read, write], [_tool("Read.")])
    assert load_overrides("fs").keys() == {"read", "write"}

    new_write = _tool("Write a file, now different.", name="write")
    save_overrides("fs", [read, new_write], [_tool("Read.")])
    assert load_overrides("fs").keys() == {"read"}


def test_load_names_a_broken_file(home: Path) -> None:
    path = overrides_path("fs")
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    with pytest.raises(ValueError, match="fs.json is not valid JSON"):
        load_overrides("fs")

    path.write_text(json.dumps({"version": 2, "tools": {}}))
    with pytest.raises(ValueError, match="not a version 1"):
        load_overrides("fs")
