import json
from pathlib import Path

from typer.testing import CliRunner

from slimproof.cli import app


def test_audit_json_reports_broken_server(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"broken": {"command": "slimproof-no-such-cmd"}}}))

    result = CliRunner().invoke(app, ["audit", "--config", str(config), "--format", "json"])

    assert result.exit_code == 2
    assert json.loads(result.stdout)["errors"].keys() == {"broken"}
