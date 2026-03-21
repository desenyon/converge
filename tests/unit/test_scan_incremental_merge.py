"""Incremental scan merges unchanged modules when only some files change."""

from pathlib import Path

from converge.graph.store import GraphStore
from converge.project_context import ProjectContext
from converge.scanner.incremental import write_scan_state
from converge.scanner.paths import iter_python_files
from converge.scanner.scanner import Scanner
from converge.settings import ConvergeSettings


def test_scan_incremental_merges_when_one_file_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "r"\ndependencies = ["requests"]\n',
        encoding="utf-8",
    )
    (repo / "a.py").write_text("import requests\n", encoding="utf-8")
    (repo / "b.py").write_text("x = 1\n", encoding="utf-8")

    settings = ConvergeSettings(incremental_scan=True)
    scanner = Scanner(str(repo), settings=settings)
    entities, rels = scanner.scan_all()

    context = ProjectContext.from_target(repo)
    store = GraphStore.for_context(context)
    try:
        store.reset()
        for e in entities:
            store.add_entity(e)
        for r in rels:
            store.add_relationship(r)

        py_files = iter_python_files(repo, settings)
        write_scan_state(context.scan_state_path, repo, py_files)

        (repo / "b.py").write_text("x = 2\n", encoding="utf-8")
        py_files2 = iter_python_files(repo, settings)
        merged = scanner.scan_incremental(store, context.scan_state_path, py_files2)
        assert merged is not None
        ent2, _rel2 = merged
        assert any(e.id == "mod:a.py" for e in ent2)
        assert any(e.id == "mod:b.py" for e in ent2)
    finally:
        store.close()
