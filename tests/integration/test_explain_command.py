from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_explain_reports_repo_local_conflict_details(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    scan_result = runner.invoke(app, ["scan", str(repo)])
    explain_result = runner.invoke(
        app,
        ["explain", "conflict:unresolved_mod:main.py_pkg:requests", str(repo)],
    )

    assert scan_result.exit_code == 0
    assert explain_result.exit_code == 0
    assert "Conflict" in explain_result.stdout
    assert "Unresolved Import" in explain_result.stdout
    assert "requests" in explain_result.stdout
    assert "main.py" in explain_result.stdout
