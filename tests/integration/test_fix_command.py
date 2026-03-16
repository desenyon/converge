from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app
from converge.validation.smoke import ValidationRunner

runner = CliRunner()


def test_fix_apply_updates_repo_after_validation(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")

    monkeypatch.setattr(ValidationRunner, "validate_plan", lambda self, plan, smoke_imports: True)

    scan_result = runner.invoke(app, ["scan", str(repo)])
    fix_result = runner.invoke(app, ["fix", str(repo), "--apply"])

    assert scan_result.exit_code == 0
    assert fix_result.exit_code == 0
    assert "Validation passed" in fix_result.stdout
    assert "Applied validated changes" in fix_result.stdout
    assert '"requests"' in (repo / "pyproject.toml").read_text()
