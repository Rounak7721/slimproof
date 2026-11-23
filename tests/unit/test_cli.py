import json
import sys
from pathlib import Path

from typer.testing import CliRunner

from slimproof.cli import app


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
