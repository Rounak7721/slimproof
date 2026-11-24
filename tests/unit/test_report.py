import json

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.report import context_share, over_budget, to_json, to_table

COSTS = [ToolCost("github", "create_issue", 120), ToolCost("github", "ping", 10)]


def test_to_json_round_trips() -> None:
    result = AuditResult(COSTS, {"broken": "not found"}, {"remote": "http not supported"})
    data = json.loads(to_json(result))
    assert data["costs"][0] == {"server": "github", "tool": "create_issue", "tokens": 120}
    assert data["errors"] == {"broken": "not found"}
    assert data["skipped"] == {"remote": "http not supported"}


def test_to_table_has_row_per_tool_plus_total() -> None:
    assert to_table(COSTS).row_count == 3


def test_to_table_drops_tilde_when_exact() -> None:
    assert to_table(COSTS).columns[2].header == "~Tokens"
    assert to_table(COSTS, exact=True).columns[2].header == "Tokens"


def test_context_share_of_both_windows() -> None:
    assert context_share(50_000) == (
        "Uses 25.0% of a 200K context window (5.0% of 1M) in every request."
    )


def test_over_budget_only_when_share_is_above_budget() -> None:
    assert over_budget(20_000, budget=10) is None
    assert over_budget(20_001, budget=10) is not None
    assert over_budget(20_001, budget=10, window=1_000_000) is None
