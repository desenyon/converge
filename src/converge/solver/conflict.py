from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel

from converge.graph.queries import GraphQueries
from converge.models import RelationshipType


class ConflictType(str):
    MISSING_PACKAGE = "missing_package"
    VERSION_CLASH = "version_clash"
    UNRESOLVED_IMPORT = "unresolved_import"


class Conflict(BaseModel):
    id: str
    type: str  # ConflictType
    description: str
    involved_entities: list[str]
    metadata: dict[str, Any] = {}


class ConflictDetector:
    """
    Analyzes the graph to find broken relationships or unmet constraints.
    """

    def __init__(self, G: nx.DiGraph[Any]):
        self.G = G
        self.queries = GraphQueries(G)

    def detect_all(self) -> list[Conflict]:
        conflicts = []
        conflicts.extend(self._detect_unresolved_imports())
        conflicts.extend(self._detect_version_clashes())
        # In a real system, we'd also check if the installed environment matches requirements
        return conflicts

    def _detect_unresolved_imports(self) -> list[Conflict]:
        """
        Finds IMPORTS edges that do not point to a known installed package or internal module.
        """
        conflicts = []
        for u, v, data in self.G.edges(data=True):
            if (
                data.get("type") == RelationshipType.IMPORTS
                or data.get("type") == RelationshipType.IMPORTS.value
            ):
                # An import is valid if the target package has been declared via REQUIRES from a repo/project
                has_requires = False
                for predecessor in self.G.predecessors(v):
                    edge_preds = self.G.get_edge_data(predecessor, v)
                    if edge_preds and (
                        edge_preds.get("type") == RelationshipType.REQUIRES
                        or edge_preds.get("type") == RelationshipType.REQUIRES.value
                    ):
                        has_requires = True
                        break

                if not has_requires:
                    # We might have imported a third-party package without adding to pyproject.toml
                    c = Conflict(
                        id=f"conflict:unresolved_{u}_{v}",
                        type=ConflictType.UNRESOLVED_IMPORT,
                        description=f"Module {u} imports {v}, but it is not declared in dependencies.",
                        involved_entities=[u, v],
                        metadata={"import_data": data},
                    )
                    conflicts.append(c)
        return conflicts

    def _detect_version_clashes(self) -> list[Conflict]:
        clashes = self.queries.get_version_conflicts()
        conflicts = []
        for u, v in clashes:
            c = Conflict(
                id=f"conflict:clash_{u}_{v}",
                type=ConflictType.VERSION_CLASH,
                description=f"Version conflict between {u} and {v}.",
                involved_entities=[u, v],
            )
            conflicts.append(c)
        return conflicts
