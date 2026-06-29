from pathlib import Path

from converge.audit import append_audit_event, read_audit_events
from converge.cli.packages_report import summarize_packages
from converge.project_context import ProjectContext


def test_read_audit_events_returns_parsed_lines(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    context = ProjectContext.from_target(repo)
    append_audit_event(context, {"event": "fix_apply", "plan_id": "plan:001"})
    append_audit_event(context, {"event": "fix_apply", "plan_id": "plan:002"})

    events = read_audit_events(context, limit=1)

    assert len(events) == 1
    assert events[0]["plan_id"] == "plan:002"


def test_summarize_packages_counts_missing_and_unused(tmp_path: Path) -> None:
    from converge.graph.store import GraphStore
    from converge.scanner.scanner import Scanner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "repo"\ndependencies = ["unused-pkg"]\n'
    )
    (repo / "main.py").write_text("import requests\n")

    scanner = Scanner(str(repo))
    entities, rels = scanner.scan_all()
    context = ProjectContext.from_target(repo)
    with GraphStore.for_context(context) as store:
        for entity in entities:
            store.add_entity(entity)
        for rel in rels:
            store.add_relationship(rel)
        G = store.load_networkx()

    summary = summarize_packages(G)

    assert "requests" in summary["missing"]
    assert "unused-pkg" in summary["unused"]
