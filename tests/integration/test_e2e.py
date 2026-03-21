from typing import Any

from typer.testing import CliRunner

from converge.cli.main import app

runner = CliRunner()


def test_e2e_scan_and_dry_run_fix(tmp_path: Any) -> None:
    # Setup a dummy broken repo
    repo_dir = tmp_path / "broken_repo"
    repo_dir.mkdir()

    # Missing dependency in pyproject.toml
    (repo_dir / "pyproject.toml").write_text("""
[project]
name = "broken_repo"
dependencies = []
    """)

    # Source file that imports something not in pyproject.toml
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("""
import requests
import colorama
    """)

    # Run scan
    result = runner.invoke(app, ["scan", str(repo_dir)])
    assert result.exit_code == 0
    assert "Scan Summary" in result.stdout
    assert "Graph saved" in result.stdout
    normalized_output = result.stdout.replace("\n", "")
    assert ".converge" in normalized_output
    assert "graph.db" in normalized_output

    # Run fix dry-run
    # First we need to chdir to the repo so the DB is created there or pass it correctly.
    # Actually store is global for now, so it will read what was just populated!

    fix_result = runner.invoke(app, ["fix", str(repo_dir)])
    # We should see conflicts for requests and colorama
    assert fix_result.exit_code == 1  # ExitCode.ISSUES_FOUND: dry-run with open conflicts
    assert "Dry run only" in fix_result.stdout
    assert "requests" in fix_result.stdout
    assert "colorama" in fix_result.stdout

    # Note: we don't run --apply in automated tests yet without a real uv installation sandbox guard.
    # The UVSandbox validation logic needs internet and is heavy, so dry run E2E is sufficient for CI.
