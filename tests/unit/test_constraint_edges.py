from pathlib import Path

from converge.models import RelationshipType
from converge.scanner.constraint_edges import build_constraint_conflict_edges
from converge.scanner.project import ProjectParser


def test_conflicting_constraints_emit_conflicts_with(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["requests>=2.32"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("requests<2.0\n", encoding="utf-8")

    parser = ProjectParser(str(tmp_path))
    _pkgs, rels = parser.parse_pyproject()
    _pkgs2, rels2 = parser.parse_requirements_txt()
    all_rels = rels + rels2
    conflicts = build_constraint_conflict_edges(all_rels)

    assert any(r.type == RelationshipType.CONFLICTS_WITH for r in conflicts)
    assert any(r.target_id == "pkg:requests" for r in conflicts)
