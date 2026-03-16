from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_create_command_uses_repo_environment_path(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = ["requests>=2.0"]\n')
    (repo / "main.py").write_text("import requests\n")

    created_paths: list[Path] = []
    installed_packages: list[list[str]] = []

    from converge.env_manager import EnvironmentManager

    def fake_create_venv(self: EnvironmentManager, provider: str = "uv", python_version: str | None = None) -> None:
        created_paths.append(self.venv_path)

    def fake_install_packages(self: EnvironmentManager, provider: str, packages: list[str]) -> None:
        installed_packages.append(packages)

    monkeypatch.setattr(EnvironmentManager, "create_venv", fake_create_venv)
    monkeypatch.setattr(EnvironmentManager, "install_packages", fake_install_packages)

    scan_result = runner.invoke(app, ["scan", str(repo)])
    create_result = runner.invoke(app, ["create", str(repo)])

    assert scan_result.exit_code == 0
    assert create_result.exit_code == 0
    assert created_paths == [repo / ".venv"]
    assert installed_packages == [["requests"]]
    assert "Environment ready" in create_result.stdout
    assert ".venv" in create_result.stdout
    assert "Activate" in create_result.stdout
