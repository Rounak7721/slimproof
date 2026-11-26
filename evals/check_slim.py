"""Check every slim tool list against its snapshot with the lossless guard."""

import json
import sys
from pathlib import Path

from mcp import types

from slimproof.core.guard import compare

EVALS = Path(__file__).parent


def load(path: Path) -> list[types.Tool]:
    """Tools from a JSON file written by snapshot.py or the skill."""
    return [types.Tool.model_validate(t) for t in json.loads(path.read_text(encoding="utf-8"))]


def main() -> int:
    failed = False
    for slim in sorted((EVALS / "slim").glob("*.json")):
        changes = compare(load(EVALS / "snapshots" / slim.name), load(slim))
        problems = [p for c in changes for p in c.problems]
        before, after = sum(c.before for c in changes), sum(c.after for c in changes)
        print(f"{slim.stem}: {before} -> {after} tokens, {len(problems)} problems")
        for p in problems:
            print(f"  {p}")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
