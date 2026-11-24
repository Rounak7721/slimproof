"""Lossless guard: a slim rewrite may change wording, never structure."""

from dataclasses import dataclass
from typing import Any

from mcp import types

from slimproof.core.tokens import DEFAULT_RATIO, count_tokens

WORDING = {"description", "title"}
NAME_MAPS = {"properties", "patternProperties", "$defs", "definitions"}
DATA = {"default", "enum", "const", "examples"}


@dataclass(frozen=True)
class ToolChange:
    """Token cost before and after slimming one tool, and anything the guard rejected."""

    tool: str
    before: int
    after: int
    problems: list[str]


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


def without_wording(tool: types.Tool) -> types.Tool:
    """`tool` with every description and title removed: the part slimming can't change."""
    return types.Tool.model_validate(_structure(tool.model_dump(by_alias=True, exclude_none=True)))


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


def compare(
    original: list[types.Tool],
    slim: list[types.Tool],
    exact: bool = False,
    ratio: float = DEFAULT_RATIO,
) -> list[ToolChange]:
    """Pair tools by name; report token savings and guard problems for each."""
    counts = count_tokens(original + slim, exact, ratio)  # one batch shares the API baseline
    before = dict(zip((t.name for t in original), counts[: len(original)], strict=True))
    after = dict(zip((t.name for t in slim), counts[len(original) :], strict=True))
    slim_by_name = {t.name: t for t in slim}
    changes = []
    for tool in original:
        new = slim_by_name.pop(tool.name, None)
        if new is None:
            changes.append(
                ToolChange(tool.name, before[tool.name], 0, ["missing from the slim version"])
            )
        else:
            changes.append(
                ToolChange(tool.name, before[tool.name], after[tool.name], guard(tool, new))
            )
    for name in slim_by_name:
        changes.append(ToolChange(name, 0, after[name], ["not in the original"]))
    return changes
