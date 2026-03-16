import json
from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_export_command_writes_json_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "repo"\ndependencies = ["requests>=2.0"]\n'
    )
    (repo / "main.py").write_text("import requests\n")

    scan_result = runner.invoke(app, ["scan", str(repo)])
    export_result = runner.invoke(app, ["export", str(repo), "--format", "json"])

    export_path = repo / ".converge" / "exports" / "graph.json"

    assert scan_result.exit_code == 0
    assert export_result.exit_code == 0
    assert "Export complete" in export_result.stdout
    assert ".converge/exports/graph.json" in export_result.stdout
    assert export_path.exists()

    payload = json.loads(export_path.read_text())
    assert payload["repository"] == str(repo.resolve())
    assert any(node["id"] == "pkg:requests" for node in payload["nodes"])


def test_clean_removes_export_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    exports_dir = repo / ".converge" / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / "graph.json").write_text("{}")

    clean_result = runner.invoke(app, ["clean", str(repo)])

    assert clean_result.exit_code == 0
    assert "Removed" in clean_result.stdout
    assert not exports_dir.exists()
