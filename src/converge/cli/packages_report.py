"""Package inventory derived from the dependency graph."""

from __future__ import annotations

from typing import Any

import networkx as nx

from converge.models import EntityType, RelationshipType
from converge.settings import ConvergeSettings
from converge.solver.conflict import ConflictDetector, ConflictType


def _strip_pkg(node_id: str) -> str:
    return node_id.replace("pkg:", "", 1)


def summarize_packages(G: nx.DiGraph[Any], settings: ConvergeSettings | None = None) -> dict[str, Any]:
    """Build declared/imported/missing/unused package lists from graph state."""
    settings = settings or ConvergeSettings()
    detector = ConflictDetector(G, settings=settings)
    conflicts = detector.detect_all()

    declared: set[str] = set()
    for _source, target, data in G.edges(data=True):
        if data.get("type") in (RelationshipType.REQUIRES, RelationshipType.REQUIRES.value):
            if target.startswith("pkg:"):
                declared.add(_strip_pkg(target))

    imported: set[str] = set()
    for _source, target, data in G.edges(data=True):
        if data.get("type") in (RelationshipType.IMPORTS, RelationshipType.IMPORTS.value):
            if target.startswith("pkg:"):
                imported.add(_strip_pkg(target))

    missing = sorted(
        {
            _strip_pkg(c.involved_entities[1])
            for c in conflicts
            if c.type == ConflictType.UNRESOLVED_IMPORT and len(c.involved_entities) > 1
        }
    )
    unused = sorted(
        {
            _strip_pkg(c.involved_entities[0])
            for c in conflicts
            if c.type == ConflictType.UNUSED_DEPENDENCY and c.involved_entities
        }
    )

    module_count = sum(
        1
        for _node_id, data in G.nodes(data=True)
        if data.get("type") in (EntityType.MODULE, EntityType.MODULE.value)
    )

    return {
        "declared": sorted(declared),
        "imported": sorted(imported),
        "missing": missing,
        "unused": unused,
        "declared_count": len(declared),
        "imported_count": len(imported),
        "missing_count": len(missing),
        "unused_count": len(unused),
        "module_count": module_count,
    }
