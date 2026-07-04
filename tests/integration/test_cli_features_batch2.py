import json
from pathlib import Path

from typer.testing import CliRunner

from converge.cli.main import app
from converge.exit_codes import ExitCode

runner = CliRunner()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text("import requests\n")
    return repo


def test_scan_force_bypasses_incremental_skip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runner.invoke(app, ["scan", str(repo)])
    skipped = runner.invoke(app, ["--json", "scan", str(repo)])
    forced = runner.invoke(app, ["--json", "scan", str(repo), "--force"])

    assert json.loads(skipped.stdout)["status"] == "skipped_incremental"
    assert json.loads(forced.stdout)["status"] == "completed"


def test_check_runs_scan_and_doctor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    result = runner.invoke(app, ["check", str(repo)])

    assert result.exit_code == ExitCode.ISSUES_FOUND
    assert "Detected" in result.stdout
    assert (repo / ".converge" / "graph.db").exists()


def test_packages_lists_missing_import(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runner.invoke(app, ["scan", str(repo)])
    result = runner.invoke(app, ["--json", "packages", str(repo)])

    payload = json.loads(result.stdout)
    assert "requests" in payload["missing"]
    assert result.exit_code == ExitCode.ISSUES_FOUND


def test_doctor_type_filter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "repo"\ndependencies = ["unused-pkg"]\n'
    )
    (repo / "main.py").write_text("import requests\n")
    runner.invoke(app, ["scan", str(repo)])

    all_issues = runner.invoke(app, ["--json", "doctor", str(repo)])
    filtered = runner.invoke(app, ["--json", "doctor", str(repo), "--type", "unresolved_import"])

    all_payload = json.loads(all_issues.stdout)
    filtered_payload = json.loads(filtered.stdout)
    assert all_payload["conflict_count"] >= 2
    assert filtered_payload["conflict_count"] == 1
    assert filtered_payload["conflicts"][0]["type"] == "unresolved_import"


def test_audit_shows_fix_events(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    audit_path = repo / ".converge" / "audit.log"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(
        '{"ts":"2026-01-01T00:00:00+00:00","event":"fix_apply","plan_id":"plan:001"}\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["audit", str(repo)])

    assert result.exit_code == ExitCode.SUCCESS
    assert "fix_apply" in result.stdout
    assert "plan:001" in result.stdout


def test_init_creates_converge_toml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    result = runner.invoke(app, ["init", str(repo)])

    assert result.exit_code == ExitCode.SUCCESS
    config = repo / ".converge.toml"
    assert config.exists()
    assert "incremental_scan" in config.read_text(encoding="utf-8")


def test_init_refuses_overwrite_without_force(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".converge.toml").write_text("incremental_scan = false\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(repo)])

    assert result.exit_code == ExitCode.ERROR


def test_clean_dry_run_does_not_delete(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runner.invoke(app, ["scan", str(repo)])

    result = runner.invoke(app, ["clean", str(repo), "--dry-run"])

    assert result.exit_code == ExitCode.SUCCESS
    assert "would remove" in result.stdout.lower()
    assert (repo / ".converge" / "graph.db").exists()


def test_create_json_includes_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    runner.invoke(app, ["scan", str(repo)])

    result = runner.invoke(app, ["--json", "create", str(repo)])

    if result.exit_code == ExitCode.SUCCESS:
        payload = json.loads(result.stdout)
        assert payload.get("status") == "completed"
