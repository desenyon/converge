from pathlib import Path

from converge.graph.store import GraphStore
from converge.lockfile import lockfile_to_graph
from converge.models import EntityType, RelationshipType
from converge.project_context import ProjectContext
from converge.scanner.scanner import Scanner
from converge.solver.conflict import ConflictDetector, ConflictType


def test_lockfile_to_graph_creates_resolves_edges(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(
        """version = 1
[[package]]
name = "requests"
version = "2.32.0"
""",
        encoding="utf-8",
    )
    entities, rels = lockfile_to_graph(tmp_path, f"repo:{tmp_path.name}")
    lock_ids = [e.id for e in entities if e.type == EntityType.LOCKFILE]
    assert lock_ids
    assert any(r.type == RelationshipType.RESOLVES_TO for r in rels)
    pkg = next(e for e in entities if e.id == "pkg:requests")
    assert pkg.metadata.get("locked_version") == "2.32.0"


def test_scan_includes_lockfile_in_graph(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["requests>=2.31"]\n',
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """version = 1
[[package]]
name = "requests"
version = "2.30.0"
""",
        encoding="utf-8",
    )
    context = ProjectContext.from_target(tmp_path)
    scanner = Scanner(str(tmp_path))
    entities, rels = scanner.scan_all()
    with GraphStore.for_context(context) as store:
        store.reset()
        for e in entities:
            store.add_entity(e)
        for r in rels:
            store.add_relationship(r)
        g = store.load_networkx()

    detector = ConflictDetector(g, root_dir=tmp_path)
    drift = [c for c in detector.detect_all() if c.type == ConflictType.LOCKFILE_DRIFT]
    assert len(drift) == 1
    assert "2.30.0" in drift[0].description
