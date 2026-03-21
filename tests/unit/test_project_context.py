from pathlib import Path

from converge.project_context import ProjectContext


def test_project_context_scopes_artifacts_to_target_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    context = ProjectContext.from_target(repo)

    assert context.root_dir == repo.resolve()
    assert context.graph_db_path == repo / ".converge" / "graph.db"
    assert context.default_env_path == repo / ".venv"
    assert context.export_dir == repo / ".converge" / "exports"
    assert context.audit_log_path == repo / ".converge" / "audit.log"
    assert context.scan_state_path == repo / ".converge" / "scan_state.json"
