import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slimproof.cli import app
from slimproof.core import tokens as tokens_module

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bloated_server.py"


def test_audit_json_reports_broken_server(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"broken": {"command": "slimproof-no-such-cmd"}}}))

    result = CliRunner().invoke(app, ["audit", "--config", str(config), "--format", "json"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["errors"].keys() == {"broken"}


def test_server_ranks_stdio_tools() -> None:
    result = CliRunner().invoke(
        app, ["server", "--format", "json", "--", sys.executable, str(FIXTURE)]
    )

    assert result.exit_code == 0, result.output
    assert [c["tool"] for c in json.loads(result.stdout)["costs"]] == ["search", "ping"]


def test_server_json_includes_rule_findings() -> None:
    result = CliRunner().invoke(
        app, ["server", "--format", "json", "--", sys.executable, str(FIXTURE)]
    )

    findings = json.loads(result.stdout)["findings"]
    assert {(f["rule"], f["tool"]) for f in findings} == {("SP006", "search")}


def test_server_table_lists_findings() -> None:
    result = CliRunner().invoke(app, ["server", "--", sys.executable, str(FIXTURE)])

    assert "SP006" in result.stdout


def test_cli_import_keeps_logging_quiet() -> None:
    import logging

    import slimproof.cli  # noqa: F401  (importing it is the point)

    assert logging.getLogger().level >= logging.WARNING


def test_exact_without_api_key_exits_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["server", "--exact", "--", sys.executable, str(FIXTURE)])

    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output


def test_exact_uses_claude_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr(tokens_module, "count_claude_tokens", lambda tools: [7] * len(tools))

    result = CliRunner().invoke(
        app, ["server", "--exact", "--format", "json", "--", sys.executable, str(FIXTURE)]
    )

    data = json.loads(result.stdout)
    assert data["exact"] is True
    assert {c["tokens"] for c in data["costs"]} == {7}


def test_ratio_changes_the_estimate() -> None:
    def total(ratio: str) -> int:
        result = CliRunner().invoke(
            app,
            ["server", "--format", "json", "--ratio", ratio, "--", sys.executable, str(FIXTURE)],
        )
        return sum(c["tokens"] for c in json.loads(result.stdout)["costs"])

    assert total("2") > total("4")


def test_budget_exits_1_when_over() -> None:
    def run(*options: str) -> int:
        args = ["server", *options, "--", sys.executable, str(FIXTURE)]
        return CliRunner().invoke(app, args).exit_code

    assert run("--budget", "0.1") == 1
    assert run("--budget", "1") == 0
    assert run("--budget", "0.1", "--window", "1000000") == 0


def _write_tools(path: Path, description: str, param_type: str = "string") -> Path:
    schema = {"type": "object", "properties": {"path": {"type": param_type}}}
    tools = [{"name": "read", "description": description, "inputSchema": schema}]
    path.write_text(json.dumps(tools), encoding="utf-8")
    return path


def test_compare_shows_savings_and_passes_guard(tmp_path: Path) -> None:
    original = _write_tools(tmp_path / "o.json", "This tool allows you to read a file from disk.")
    slim = _write_tools(tmp_path / "s.json", "Read a file.")

    result = CliRunner().invoke(app, ["compare", str(original), str(slim), "--format", "markdown"])

    assert result.exit_code == 0, result.output
    assert "| **Total** |" in result.stdout
    assert "**all ok**" in result.stdout


def test_compare_exits_1_when_guard_fails(tmp_path: Path) -> None:
    original = _write_tools(tmp_path / "o.json", "Read a file.")
    slim = _write_tools(tmp_path / "s.json", "Read a file.", param_type="integer")

    result = CliRunner().invoke(app, ["compare", str(original), str(slim), "--format", "json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)[0]["problems"] != []


def test_compare_exits_2_on_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(app, ["compare", str(bad), str(bad)])

    assert result.exit_code == 2
    assert "JSON list of tools" in result.output


def test_audit_exits_2_on_broken_config(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(app, ["audit", "--config", str(config)])

    assert result.exit_code == 2
    assert "must hold a JSON object" in result.output
