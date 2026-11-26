"""Save and load the slim tool overrides that the proxy serves."""

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import types

from slimproof.core.guard import guard

VERSION = 1
_NAME = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class Override:
    """A saved slim tool and the hash of the original tool it was made from."""

    original_sha256: str
    slim: types.Tool


def tool_hash(tool: types.Tool) -> str:
    """SHA-256 of `tool` as canonical JSON: the same definition always gives the same hash."""
    text = json.dumps(dump(tool), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dump(tool: types.Tool) -> dict[str, Any]:
    """`tool` as wire JSON (camelCase keys, no empty fields)."""
    return tool.model_dump(mode="json", by_alias=True, exclude_none=True)


def overrides_path(server: str) -> Path:
    """`~/.slimproof/overrides/<server>.json`; a ValueError if `server` could leave that folder."""
    if server.startswith("plugin:"):
        raise ValueError(f"'{server}' comes from a plugin; the proxy can't serve those yet.")
    if not _NAME.fullmatch(server) or set(server) == {"."}:
        raise ValueError(f"Server name '{server}' may only use letters, digits, '.', '_' and '-'.")
    return Path.home() / ".slimproof" / "overrides" / f"{server}.json"


def load_overrides(server: str) -> dict[str, Override]:
    """The saved overrides of `server` by tool name; {} if none are saved.

    A ValueError if the file is broken.
    """
    path = overrides_path(server)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON ({e})") from None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ValueError(f"{path} is not a version {VERSION} overrides file")
    try:
        return {
            name: Override(entry["original_sha256"], types.Tool.model_validate(entry["slim"]))
            for name, entry in data["tools"].items()
        }
    except (AttributeError, KeyError, TypeError, ValueError) as e:  # ValueError: bad tool
        raise ValueError(f"{path} has a broken tool entry ({e})") from None


def save_overrides(server: str, originals: list[types.Tool], slims: list[types.Tool]) -> Path:
    """Check `slims` against the live `originals` with the guard, then save them for the proxy.

    Earlier overrides for other tools are kept while their original is unchanged.
    A ValueError lists the problems if any slim tool fails; nothing is saved then.
    """
    by_name = {t.name: t for t in originals}
    problems: list[str] = []
    for slim in slims:
        original = by_name.get(slim.name)
        problems += guard(original, slim) if original else [f"{slim.name}: not a tool of {server}"]
    if problems:
        raise ValueError("Not saved. The guard found problems:\n" + "\n".join(problems))

    try:
        kept = load_overrides(server)
    except ValueError:  # a broken file is replaced
        kept = {}
    hashes = {name: tool_hash(t) for name, t in by_name.items()}
    tools = {
        name: {"original_sha256": o.original_sha256, "slim": dump(o.slim)}
        for name, o in kept.items()
        if hashes.get(name) == o.original_sha256
    }
    for slim in slims:
        tools[slim.name] = {"original_sha256": hashes[slim.name], "slim": dump(slim)}

    path = overrides_path(server)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"version": VERSION, "server": server, "tools": tools}, indent=2)
    write_atomic(path, text + "\n")
    return path


def write_atomic(path: Path, text: str) -> None:
    """Replace `path` with `text` in one step, so a reader never sees half a file.

    An existing file keeps its permissions (a config with secrets may be owner-only).
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(b"")
    if path.exists():
        shutil.copymode(path, tmp)  # before the text goes in
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
