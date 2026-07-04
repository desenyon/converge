from pathlib import Path

from converge.models import RelationshipType
from converge.scanner.workspace import scan_uv_workspace


def test_scan_uv_workspace_links_members(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
        [tool.uv.workspace]
        members = ["packages/*"]

        [project]
        name = "root"
        dependencies = []
        """.strip(),
        encoding="utf-8",
    )
    member = tmp_path / "packages" / "child"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(
        '[project]\nname = "child"\ndependencies = ["httpx"]\n',
        encoding="utf-8",
    )

    entities, rels = scan_uv_workspace(tmp_path)
    member_ids = [e.id for e in entities if e.metadata.get("workspace_member")]
    assert member_ids
    assert any(r.type == RelationshipType.BELONGS_TO for r in rels)
    assert any(r.target_id == "pkg:httpx" for r in rels)
