import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slimproof.cli import app
from slimproof.core import audit as audit_module


def test_audit_json_reports_broken_server(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"broken": {"command": "slimproof-no-such-cmd"}}}))

    result = CliRunner().invoke(app, ["audit", "--config", str(config), "--format", "json"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["errors"].keys() == {"broken"}


FIXTURE = Path(__file__).parent.parent / "fixtures" / "bloated_server.py"


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
    monkeypatch.setattr(audit_module, "count_claude_tokens", lambda tools: [7] * len(tools))

    result = CliRunner().invoke(
        app, ["server", "--exact", "--format", "json", "--", sys.executable, str(FIXTURE)]
    )

    data = json.loads(result.stdout)
    assert data["exact"] is True
    assert {c["tokens"] for c in data["costs"]} == {7}
