import json
from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app
from converge.exit_codes import ExitCode

runner = CliRunner()


def test_status_reports_graph_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = ["requests"]\n')
    (repo / "main.py").write_text("import requests\n")

    runner.invoke(app, ["scan", str(repo)])
    result = runner.invoke(app, ["--json", "status", str(repo)])

    assert result.exit_code == ExitCode.SUCCESS
    payload = json.loads(result.stdout)
    assert payload["graph"]["present"] is True
    assert payload["graph"]["entities"] >= 1
    assert payload["scan_state"]["tracked_files"] >= 1


def test_status_before_scan_shows_missing_graph(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')

    result = runner.invoke(app, ["status", str(repo)])

    assert result.exit_code == ExitCode.SUCCESS
    assert "missing" in result.stdout.lower()


def test_incremental_scan_skips_unchanged_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("x = 1\n")

    first = runner.invoke(app, ["scan", str(repo)])
    second = runner.invoke(app, ["--json", "scan", str(repo)])

    assert first.exit_code == ExitCode.SUCCESS
    assert second.exit_code == ExitCode.SUCCESS
    payload = json.loads(second.stdout)
    assert payload.get("status") == "skipped_incremental"
