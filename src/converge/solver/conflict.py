from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel, Field

from converge.graph.queries import GraphQueries
from converge.models import EntityType, RelationshipType
from converge.settings import ConvergeSettings

PACKAGE_IMPORT_ALIASES = {
    "beautifulsoup4": {"bs4"},
    "opencv-python": {"cv2"},
    "pillow": {"PIL"},
    "python-dateutil": {"dateutil"},
    "python-dotenv": {"dotenv"},
    "pyyaml": {"yaml"},
    "scikit-learn": {"sklearn"},
}


class ConflictType(str):
    MISSING_PACKAGE = "missing_package"
    VERSION_CLASH = "version_clash"
    UNRESOLVED_IMPORT = "unresolved_import"
    UNUSED_DEPENDENCY = "unused_dependency"


class Conflict(BaseModel):
    id: str
    type: str  # ConflictType
    description: str
    involved_entities: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConflictDetector:
    """
    Analyzes the graph to find broken relationships or unmet constraints.
    """

    def __init__(self, G: nx.DiGraph[Any], settings: ConvergeSettings | None = None):
        self.G = G
        self.settings = settings or ConvergeSettings()
        self.queries = GraphQueries(G)

    def _node_metadata(self, node_id: str) -> dict[str, Any]:
        data = self.G.nodes.get(node_id, {})
        md = data.get("metadata")
        return md if isinstance(md, dict) else {}

    def _is_test_module(self, mod_id: str) -> bool:
        return self._node_metadata(mod_id).get("scan_kind") == "test"

    def _package_import_names(self, package_id: str) -> set[str]:
        package_name = package_id.replace("pkg:", "", 1)
        return {package_name, *PACKAGE_IMPORT_ALIASES.get(package_name.lower(), set())}

    def _declared_package_ids(self) -> set[str]:
        declared = set()
        for _u, v, data in self.G.edges(data=True):
            if (
                data.get("type") == RelationshipType.REQUIRES
                or data.get("type") == RelationshipType.REQUIRES.value
            ):
                declared.add(v)
        return declared

    def detect_all(self) -> list[Conflict]:
        conflicts = []
        conflicts.extend(self._detect_unresolved_imports())
        conflicts.extend(self._detect_version_clashes())
        conflicts.extend(self._detect_unused_dependencies())
        return conflicts

    def _detect_unresolved_imports(self) -> list[Conflict]:
        """
        Finds IMPORTS edges that do not point to a known installed package or internal module.
        """
        conflicts = []
        declared_package_ids = self._declared_package_ids()
        for u, v, data in self.G.edges(data=True):
            if (
                data.get("type") == RelationshipType.IMPORTS
                or data.get("type") == RelationshipType.IMPORTS.value
            ):
                # An import is valid if the target package has been declared via REQUIRES from a repo/project
                imported_name = v.replace("pkg:", "", 1)
                has_requires = any(
                    imported_name in self._package_import_names(package_id)
                    for package_id in declared_package_ids
                )

                if not has_requires:
                    # We might have imported a third-party package without adding to pyproject.toml
                    c = Conflict(
                        id=f"conflict:unresolved_{u}_{v}",
                        type=ConflictType.UNRESOLVED_IMPORT,
                        description=f"Module '{u.replace('mod:', '')}' imports '{v.replace('pkg:', '')}', but it is undeclared in dependencies.",
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
                description=f"Irreconcilable version conflict spanning '{u}' and '{v}'.",
                involved_entities=[u, v],
            )
            conflicts.append(c)
        return conflicts

    def _detect_unused_dependencies(self) -> list[Conflict]:
        """
        Garbage Collection: Finds packages defined in REQUIRES that no module IMPORTS.
        """
        conflicts = []
        # Find all packages declared in the project
        declared_packages = []
        for package_id in self._declared_package_ids():
            if (
                self.G.nodes[package_id].get("type") == EntityType.PACKAGE
                or self.G.nodes[package_id].get("type") == EntityType.PACKAGE.value
            ):
                declared_packages.append(package_id)

        for pkg in set(declared_packages):
            import_target_ids = {f"pkg:{name}" for name in self._package_import_names(pkg)}
            has_import = False
            has_non_test_import = False
            for _u, v, data in self.G.edges(data=True):
                if v not in import_target_ids:
                    continue
                if (
                    data.get("type") == RelationshipType.IMPORTS
                    or data.get("type") == RelationshipType.IMPORTS.value
                ):
                    has_import = True
                    if not self._is_test_module(_u):
                        has_non_test_import = True

            if has_import and not has_non_test_import:
                continue

            if not has_import:
                c = Conflict(
                    id=f"conflict:unused_{pkg}",
                    type=ConflictType.UNUSED_DEPENDENCY,
                    description=f"Package '{pkg.replace('pkg:', '')}' is declared but never imported in scanned modules.",
                    involved_entities=[pkg],
                )
                conflicts.append(c)

        return conflicts
