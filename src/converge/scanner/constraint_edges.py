"""Emit CONFLICTS_WITH edges when declared constraints are incompatible."""

from __future__ import annotations

from converge.models import GraphRelationship, RelationshipType
from converge.versioning.constraints import constraints_conflict, parse_requirement


def build_constraint_conflict_edges(
    relationships: list[GraphRelationship],
) -> list[GraphRelationship]:
    """Add CONFLICTS_WITH edges for packages with incompatible REQUIRES constraints."""
    by_target: dict[str, list[tuple[str, str]]] = {}
    for rel in relationships:
        if rel.type != RelationshipType.REQUIRES:
            continue
        constraint = rel.metadata.get("constraint")
        if not constraint:
            continue
        by_target.setdefault(rel.target_id, []).append((rel.source_id, str(constraint)))

    conflicts: list[GraphRelationship] = []
    for target_id, entries in by_target.items():
        for i, (_source_a, constraint_a) in enumerate(entries):
            _, spec_a = parse_requirement(constraint_a)
            for _source_b, constraint_b in entries[i + 1 :]:
                _, spec_b = parse_requirement(constraint_b)
                if constraints_conflict(spec_a, spec_b):
                    conflicts.append(
                        GraphRelationship(
                            source_id=target_id,
                            target_id=target_id,
                            type=RelationshipType.CONFLICTS_WITH,
                            metadata={
                                "constraints": [constraint_a, constraint_b],
                                "package_id": target_id,
                            },
                        )
                    )
                    break
            if any(c.target_id == target_id for c in conflicts):
                break
    return conflicts
