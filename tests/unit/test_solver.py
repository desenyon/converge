from __future__ import annotations

from typing import Any

import networkx as nx

from converge.models import RelationshipType
from converge.solver.conflict import ConflictDetector, ConflictType


def test_unresolved_import_conflict() -> None:
    G: nx.DiGraph[Any] = nx.DiGraph()
    # Mod exists
    G.add_node("mod:a.py", type="module", name="a.py")
    # Pkg does NOT exist
    G.add_edge("mod:a.py", "pkg:missing", type=RelationshipType.IMPORTS)

    detector = ConflictDetector(G)
    conflicts = detector._detect_unresolved_imports()

    assert len(conflicts) == 1
    assert conflicts[0].type == ConflictType.UNRESOLVED_IMPORT
    assert conflicts[0].involved_entities == ["mod:a.py", "pkg:missing"]

def test_version_clash_conflict() -> None:
    G: nx.DiGraph[Any] = nx.DiGraph()
    G.add_edge("pkg:A", "pkg:B", type=RelationshipType.CONFLICTS_WITH)

    detector = ConflictDetector(G)
    conflicts = detector._detect_version_clashes()

    assert len(conflicts) == 1
    assert conflicts[0].type == ConflictType.VERSION_CLASH
    assert conflicts[0].involved_entities == ["pkg:A", "pkg:B"]
