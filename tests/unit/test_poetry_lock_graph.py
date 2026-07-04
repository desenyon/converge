from pathlib import Path

from converge.lockfile import lockfile_to_graph
from converge.models import EntityType, RelationshipType


def test_poetry_lock_to_graph(tmp_path: Path) -> None:
    (tmp_path / "poetry.lock").write_text(
        """[[package]]
name = "requests"
version = "2.31.0"
""",
        encoding="utf-8",
    )
    entities, rels = lockfile_to_graph(tmp_path, "repo:demo")
    assert any(e.type == EntityType.LOCKFILE for e in entities)
    assert any(r.type == RelationshipType.RESOLVES_TO for r in rels)
    pkg = next(e for e in entities if e.id == "pkg:requests")
    assert pkg.metadata.get("locked_version") == "2.31.0"
