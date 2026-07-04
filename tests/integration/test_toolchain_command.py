from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_toolchain_command_reports_uv(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    result = runner.invoke(app, ["--json", "toolchain", str(repo)])
    assert result.exit_code == 0
    assert '"toolchain": "uv"' in result.stdout


def test_doctor_json_includes_toolchain(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "r"\ndependencies = []\n')
    (repo / "main.py").write_text("import os\n")
    runner.invoke(app, ["scan", str(repo)])
    result = runner.invoke(app, ["--json", "doctor", str(repo)])
    assert result.exit_code == 0
    assert '"toolchain"' in result.stdout
    assert '"packages"' in result.stdout
