import json

from slimproof.core.audit import ToolCost
from slimproof.core.report import to_json, to_table

COSTS = [ToolCost("github", "create_issue", 120), ToolCost("github", "ping", 10)]


def test_to_json_round_trips() -> None:
    data = json.loads(to_json(COSTS, {"broken": "not found"}))
    assert data["tools"][0] == {"server": "github", "tool": "create_issue", "tokens": 120}
    assert data["errors"] == {"broken": "not found"}


def test_to_table_has_row_per_tool_plus_total() -> None:
    assert to_table(COSTS).row_count == 3
