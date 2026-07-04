"""Detect uv workspaces and link member projects to the root repository."""

from __future__ import annotations

import tomllib
from pathlib import Path

from converge.models import EntityType, GraphEntity, GraphRelationship, RelationshipType
from converge.scanner.project import ProjectParser


def _repo_id(root: Path) -> str:
    return f"repo:{root.name}"


def scan_uv_workspace(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:  # noqa: C901
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return entities, relationships

    with pyproject.open("rb") as handle:
        try:
            data = tomllib.load(handle)
        except tomllib.TOMLDecodeError:
            return entities, relationships

    tool_uv = data.get("tool", {}).get("uv", {})
    if not isinstance(tool_uv, dict):
        return entities, relationships

    workspace = tool_uv.get("workspace", {})
    if not isinstance(workspace, dict):
        return entities, relationships

    members = workspace.get("members", [])
    if not isinstance(members, list):
        return entities, relationships

    root_id = _repo_id(root)
    for member in members:
        if not isinstance(member, str):
            continue
        member_paths: list[Path] = []
        if any(ch in member for ch in "*?[]"):
            member_paths = [p for p in root.glob(member) if p.is_dir()]
        else:
            candidate = root / member
            if candidate.is_dir():
                member_paths = [candidate]
        for member_path in member_paths:
            member_id = f"repo:{member_path.name}"
            rel_member = str(member_path.relative_to(root))
            entities.append(
                GraphEntity(
                    id=member_id,
                    type=EntityType.REPOSITORY,
                    name=member_path.name,
                    metadata={"path": rel_member, "workspace_member": True},
                )
            )
            relationships.append(
                GraphRelationship(
                    source_id=member_id,
                    target_id=root_id,
                    type=RelationshipType.BELONGS_TO,
                    metadata={"workspace_root": str(root)},
                )
            )
            parser = ProjectParser(str(member_path))
            pkgs, rels = parser.parse_pyproject()
            entities.extend(pkgs)
            for rel in rels:
                relationships.append(
                    GraphRelationship(
                        source_id=member_id,
                        target_id=rel.target_id,
                        type=rel.type,
                        metadata={**rel.metadata, "workspace_member": rel_member},
                    )
                )
    return entities, relationships


def read_uv_sources(root: Path) -> dict[str, dict[str, str]]:
    """Return [tool.uv.sources] mapping for install hints."""
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    with pyproject.open("rb") as handle:
        try:
            data = tomllib.load(handle)
        except tomllib.TOMLDecodeError:
            return {}
    tool_uv = data.get("tool", {}).get("uv", {})
    if not isinstance(tool_uv, dict):
        return {}
    sources = tool_uv.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for name, spec in sources.items():
        if isinstance(name, str) and isinstance(spec, dict):
            out[name] = {str(k): str(v) for k, v in spec.items()}
    return out
