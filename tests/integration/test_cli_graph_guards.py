from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app
from converge.exit_codes import ExitCode

runner = CliRunner()


def test_doctor_errors_when_graph_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    result = runner.invoke(app, ["doctor", str(repo)])

    assert result.exit_code == ExitCode.ERROR
    assert "No graph found" in result.stdout


def test_doctor_errors_after_clean(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    runner.invoke(app, ["scan", str(repo)])
    runner.invoke(app, ["clean", str(repo)])
    result = runner.invoke(app, ["doctor", str(repo)])

    assert result.exit_code == ExitCode.ERROR
    assert "No graph found" in result.stdout


def test_export_errors_without_scan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')

    result = runner.invoke(app, ["export", str(repo)])

    assert result.exit_code == ExitCode.ERROR
    assert "No graph found" in result.stdout


def test_doctor_json_includes_conflict_count(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    runner.invoke(app, ["scan", str(repo)])
    result = runner.invoke(app, ["--json", "doctor", str(repo)])

    assert result.exit_code == ExitCode.ISSUES_FOUND
    assert '"conflict_count": 1' in result.stdout
    assert '"status": "issues"' in result.stdout
