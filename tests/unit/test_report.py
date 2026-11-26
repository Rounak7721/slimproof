import json

from slimproof.core.audit import AuditResult, ToolCost
from slimproof.core.report import (
    context_share,
    over_budget,
    summary,
    to_json,
    to_markdown,
    to_table,
)
from slimproof.core.rules import Finding

COSTS = [ToolCost("github", "create_issue", 120, 80), ToolCost("github", "ping", 10, 4)]


def test_to_json_round_trips() -> None:
    result = AuditResult(COSTS, {"broken": "not found"}, {"remote": "http not supported"})
    data = json.loads(to_json(result))
    assert data["costs"][0] == {
        "server": "github",
        "tool": "create_issue",
        "tokens": 120,
        "description_tokens": 80,
    }
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


def test_to_markdown_has_table_total_and_sections() -> None:
    findings = [Finding("SP006", "github", "create_issue", "description is 1500 chars")]
    result = AuditResult(COSTS, {"broken": "not found"}, {}, findings)

    md = to_markdown(result)

    assert "| github | create_issue | 120 | 80 (67%) |" in md
    assert "| | **Total** | **130** | **84 (65%)** |" in md
    assert "- `SP006` github/create_issue: description is 1500 chars" in md
    assert "### Failed\n\n- **broken**: not found" in md
    assert "### Skipped" not in md


def test_to_markdown_escapes_pipes_in_cells() -> None:
    result = AuditResult([ToolCost("a|b", "t", 1, 0)], {}, {})
    assert "| a\\|b | t |" in to_markdown(result)


def test_to_table_top_squeezes_the_rest_into_one_row() -> None:
    table = to_table(COSTS, top=1)

    assert table.row_count == 3  # heaviest tool, "… 1 more tools", total
    assert "1 more tools" in str(list(table.columns[1].cells)[1])


def test_to_markdown_top_keeps_full_total_and_counts_hidden_findings() -> None:
    findings = [Finding("SP001", c.server, c.tool, "filler") for c in COSTS]
    result = AuditResult(costs=COSTS, errors={}, skipped={}, findings=findings)
    total = sum(c.tokens for c in COSTS)

    md = to_markdown(result, top=1)

    assert f"**{total:,}**" in md
    assert "1 more tools" in md
    assert md.count("`SP001`") == 1
    assert "+ 1 more finding(s)" in md


def test_summary_repeats_totals_and_suggests_top_for_long_output() -> None:
    many = [Finding("SP001", "github", "ping", "filler")] * 21
    result = AuditResult(costs=COSTS, errors={}, skipped={}, findings=many)

    line = summary(result, top=None)

    assert line.startswith("Total: 2 tools, ~130 tokens (65% in descriptions)")
    assert "21 finding(s)" in line
    assert line.endswith("Add --top 10 for a short view.")
    assert "--top" not in summary(result, top=10)
