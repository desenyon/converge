"""Per-package declared / locked / imported summary for doctor JSON."""

from __future__ import annotations

from typing import Any

import networkx as nx

from converge.models import EntityType, RelationshipType
from converge.versioning.constraints import normalize_package_name


def build_package_summary(G: nx.DiGraph[Any]) -> dict[str, dict[str, Any]]:  # noqa: C901
    """Return {package_name: {declared, locked, imported}} for Python packages."""
    declared: dict[str, str | None] = {}
    locked: dict[str, str | None] = {}
    imported: set[str] = set()

    for _u, v, data in G.edges(data=True):
        edge_type = data.get("type")
        if edge_type in (RelationshipType.REQUIRES, RelationshipType.REQUIRES.value):
            if G.nodes.get(v, {}).get("type") not in (
                EntityType.PACKAGE,
                EntityType.PACKAGE.value,
            ):
                continue
            pkg_name = normalize_package_name(str(G.nodes[v].get("name", v.replace("pkg:", ""))))
            md = data.get("metadata")
            constraint = None
            group = "main"
            if isinstance(md, dict):
                constraint = md.get("constraint")
                group = str(md.get("dependency_group", "main"))
            if group not in ("main", "requirements"):
                continue
            if constraint:
                declared[pkg_name] = str(constraint)
            else:
                declared.setdefault(pkg_name, None)
        elif edge_type in (RelationshipType.RESOLVES_TO, RelationshipType.RESOLVES_TO.value):
            pkg_name = normalize_package_name(v.replace("pkg:", ""))
            md = data.get("metadata")
            version = md.get("version") if isinstance(md, dict) else None
            if version:
                locked[pkg_name] = str(version)
        elif edge_type in (RelationshipType.IMPORTS, RelationshipType.IMPORTS.value):
            imported.add(normalize_package_name(v.replace("pkg:", "")))

    all_names = set(declared) | set(locked) | imported
    summary: dict[str, dict[str, Any]] = {}
    for name in sorted(all_names):
        summary[name] = {
            "declared": declared.get(name),
            "locked": locked.get(name),
            "imported": name in imported,
        }
    return summary
