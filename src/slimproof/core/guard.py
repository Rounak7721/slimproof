"""Lossless guard: a slim rewrite may change wording, never structure."""

from typing import Any

from mcp import types

WORDING = {"description", "title"}
NAME_MAPS = {"properties", "patternProperties", "$defs", "definitions"}
DATA = {"default", "enum", "const", "examples"}


def _structure(node: Any) -> Any:
    """`node` with every wording field removed, so only structure is left."""
    if isinstance(node, list):
        return [_structure(n) for n in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in WORDING:
            continue
        if key in DATA:
            out[key] = value  # data, not schema: compare exactly
        elif key in NAME_MAPS and isinstance(value, dict):
            out[key] = {name: _structure(s) for name, s in value.items()}  # keys are names
        else:
            out[key] = _structure(value)
    return out


def _diff(a: Any, b: Any, path: str) -> list[str]:
    """Every place where `a` and `b` differ, as 'path: old -> new' lines."""
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return [] if a == b else [f"{path}: {a!r} -> {b!r}"]
    out: list[str] = []
    for key in sorted(a.keys() | b.keys()):
        if key not in b:
            out.append(f"{path}.{key}: removed")
        elif key not in a:
            out.append(f"{path}.{key}: added")
        else:
            out.extend(_diff(a[key], b[key], f"{path}.{key}"))
    return out


def guard(original: types.Tool, slim: types.Tool) -> list[str]:
    """Structural changes from `original` to `slim`; an empty list means only wording changed."""
    before = _structure(original.model_dump(by_alias=True, exclude_none=True))
    after = _structure(slim.model_dump(by_alias=True, exclude_none=True))
    return _diff(before, after, original.name)
