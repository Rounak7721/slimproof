import json

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.report import to_json, to_table

COSTS = [ToolCost("github", "create_issue", 120), ToolCost("github", "ping", 10)]


def test_to_json_round_trips() -> None:
    result = AuditResult(COSTS, {"broken": "not found"}, {"remote": "http not supported"})
    data = json.loads(to_json(result))
    assert data["costs"][0] == {"server": "github", "tool": "create_issue", "tokens": 120}
    assert data["errors"] == {"broken": "not found"}
    assert data["skipped"] == {"remote": "http not supported"}


def test_to_table_has_row_per_tool_plus_total() -> None:
    assert to_table(COSTS).row_count == 3
