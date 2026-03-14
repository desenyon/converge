from __future__ import annotations

from typing import Any, cast

import networkx as nx

from converge.models import RelationshipType


class GraphQueries:
    """
    Abstractions for traversing the NetworkX graph.
    Used for inferring constraints and paths.
    """

    def __init__(self, G: nx.DiGraph[Any]):
        self.G = G

    def get_dependencies_for_package(self, package_id: str) -> list[str]:
        """Returns all packages that this package requires directly."""
        deps = []
        if package_id in self.G:
            for neighbor in self.G.successors(package_id):
                edge_data = self.G.get_edge_data(package_id, neighbor)
                if edge_data and edge_data.get("type") == RelationshipType.REQUIRES:
                    deps.append(neighbor)
        return deps

    def get_version_conflicts(self) -> list[tuple[str, str]]:
        """Returns all edges of type CONFLICTS_WITH"""
        conflicts = []
        for u, v, data in self.G.edges(data=True):
            if data.get("type") == RelationshipType.CONFLICTS_WITH:
                conflicts.append((u, v))
        return conflicts

    def find_shortest_dependency_path(self, root_id: str, target_id: str) -> list[str] | None:
        """Finds the shortest REQUIRES path from root to target."""
        try:
            # Only traverse REQUIRES edges
            requires_graph = nx.DiGraph(
                (
                    (u, v, d)
                    for u, v, d in self.G.edges(data=True)
                    if d.get("type") == RelationshipType.REQUIRES
                )
            )
            path = cast(list[str], nx.shortest_path(requires_graph, source=root_id, target=target_id))
            return path
        except nx.NetworkXNoPath:
            return None
