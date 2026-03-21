from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_doctor_uses_target_repo_graph(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    scan_result = runner.invoke(app, ["scan", str(repo)])
    doctor_result = runner.invoke(app, ["doctor", str(repo)])

    assert scan_result.exit_code == 0
    assert doctor_result.exit_code == 1  # ExitCode.ISSUES_FOUND when conflicts exist
    assert "Doctor" in doctor_result.stdout
    assert "Detected" in doctor_result.stdout
    assert "issue" in doctor_result.stdout
    assert "requests" in doctor_result.stdout
