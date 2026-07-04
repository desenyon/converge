from typing import Any

import networkx as nx

from converge.models import EntityType, RelationshipType
from converge.solver.package_summary import build_package_summary


def test_package_summary_declared_locked_imported() -> None:
    g: nx.DiGraph[Any] = nx.DiGraph()
    g.add_node("pkg:requests", type=EntityType.PACKAGE, name="requests")
    g.add_node("mod:main.py", type=EntityType.MODULE, name="main.py")
    g.add_edge(
        "repo:demo",
        "pkg:requests",
        type=RelationshipType.REQUIRES,
        metadata={"constraint": "requests>=2.31", "dependency_group": "main"},
    )
    g.add_edge(
        "lockfile:uv.lock",
        "pkg:requests",
        type=RelationshipType.RESOLVES_TO,
        metadata={"version": "2.32.0"},
    )
    g.add_edge("mod:main.py", "pkg:requests", type=RelationshipType.IMPORTS)

    summary = build_package_summary(g)
    assert summary["requests"]["declared"] == "requests>=2.31"
    assert summary["requests"]["locked"] == "2.32.0"
    assert summary["requests"]["imported"] is True
