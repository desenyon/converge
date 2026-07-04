from pathlib import Path

from converge.graph.store import GraphStore
from converge.project_context import ProjectContext
from converge.scanner.scanner import Scanner
from converge.solver.conflict import ConflictDetector, ConflictType


def test_compile_drift_detected(tmp_path: Path) -> None:
    (tmp_path / "requirements.in").write_text("requests>=2.32\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests==2.30.0\n", encoding="utf-8")

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
    drift = [c for c in detector.detect_all() if c.type == ConflictType.COMPILE_DRIFT]
    assert len(drift) == 1
    assert "2.30.0" in drift[0].description
