from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
from pydantic import BaseModel, Field

from converge.graph.queries import GraphQueries
from converge.models import EntityType, RelationshipType
from converge.scanner.project import ProjectParser
from converge.settings import ConvergeSettings
from converge.versioning.constraints import (
    constraints_conflict,
    parse_requirement,
    version_satisfies,
)

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
    LOCKFILE_DRIFT = "lockfile_drift"
    COMPILE_DRIFT = "compile_drift"


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

    def __init__(
        self,
        G: nx.DiGraph[Any],
        settings: ConvergeSettings | None = None,
        root_dir: Path | str | None = None,
    ):
        self.G = G
        self.settings = settings or ConvergeSettings()
        self.root_dir = Path(root_dir) if root_dir is not None else None
        self.queries = GraphQueries(G)

    def _node_metadata(self, node_id: str) -> dict[str, Any]:
        data = self.G.nodes.get(node_id, {})
        md = data.get("metadata")
        return md if isinstance(md, dict) else {}

    def _edge_metadata(self, u: str, v: str) -> dict[str, Any]:
        data = self.G.get_edge_data(u, v, default={})
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

    def _package_dependency_group(self, package_id: str) -> str:
        for _u, v, data in self.G.edges(data=True):
            if v != package_id:
                continue
            if data.get("type") not in (
                RelationshipType.REQUIRES,
                RelationshipType.REQUIRES.value,
            ):
                continue
            md = data.get("metadata")
            if isinstance(md, dict) and md.get("dependency_group"):
                return str(md["dependency_group"])
        md = self._node_metadata(package_id)
        return str(md.get("dependency_group", "main"))

    def _locked_version(self, package_id: str) -> str | None:
        for _u, v, data in self.G.edges(data=True):
            if v != package_id:
                continue
            if data.get("type") not in (
                RelationshipType.RESOLVES_TO,
                RelationshipType.RESOLVES_TO.value,
            ):
                continue
            md = data.get("metadata")
            if isinstance(md, dict) and md.get("version"):
                return str(md["version"])
        md = self._node_metadata(package_id)
        locked = md.get("locked_version")
        return str(locked) if locked else None

    def detect_all(self) -> list[Conflict]:
        conflicts: list[Conflict] = []
        conflicts.extend(self._detect_unresolved_imports())
        conflicts.extend(self._detect_version_clashes())
        conflicts.extend(self._detect_declared_constraint_conflicts())
        conflicts.extend(self._detect_lockfile_drift())
        conflicts.extend(self._detect_compile_drift())
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
                imported_name = v.replace("pkg:", "", 1)
                has_requires = any(
                    imported_name in self._package_import_names(package_id)
                    for package_id in declared_package_ids
                )

                if not has_requires:
                    scan_kind = self._node_metadata(u).get("scan_kind", "source")
                    c = Conflict(
                        id=f"conflict:unresolved_{u}_{v}",
                        type=ConflictType.UNRESOLVED_IMPORT,
                        description=f"Module '{u.replace('mod:', '')}' imports '{v.replace('pkg:', '')}', but it is undeclared in dependencies.",
                        involved_entities=[u, v],
                        metadata={"import_data": data, "scan_kind": scan_kind},
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

    def _detect_declared_constraint_conflicts(self) -> list[Conflict]:
        """Find packages declared with incompatible version constraints."""
        by_pkg: dict[str, list[str]] = {}
        for _u, v, data in self.G.edges(data=True):
            if data.get("type") not in (
                RelationshipType.REQUIRES,
                RelationshipType.REQUIRES.value,
            ):
                continue
            md = data.get("metadata")
            constraint = None
            if isinstance(md, dict):
                constraint = md.get("constraint")
            if constraint:
                by_pkg.setdefault(v, []).append(str(constraint))

        conflicts: list[Conflict] = []
        for pkg_id, constraints in by_pkg.items():
            for i, c_a in enumerate(constraints):
                for c_b in constraints[i + 1 :]:
                    _, spec_a = parse_requirement(c_a)
                    _, spec_b = parse_requirement(c_b)
                    if constraints_conflict(spec_a, spec_b):
                        conflicts.append(
                            Conflict(
                                id=f"conflict:constraint_{pkg_id}_{i}",
                                type=ConflictType.VERSION_CLASH,
                                description=(
                                    f"Package '{pkg_id.replace('pkg:', '')}' has incompatible "
                                    f"declared constraints: {c_a!r} vs {c_b!r}."
                                ),
                                involved_entities=[pkg_id],
                                metadata={"constraints": [c_a, c_b]},
                            )
                        )
        return conflicts

    def _detect_lockfile_drift(self) -> list[Conflict]:
        """Manifest constraints disagree with uv.lock resolved versions."""
        conflicts: list[Conflict] = []
        declared = self._declared_package_ids()
        for pkg_id in declared:
            locked = self._locked_version(pkg_id)
            if not locked:
                continue
            constraints: list[str] = []
            for _u, v, data in self.G.edges(data=True):
                if v != pkg_id:
                    continue
                if data.get("type") not in (
                    RelationshipType.REQUIRES,
                    RelationshipType.REQUIRES.value,
                ):
                    continue
                md = data.get("metadata")
                if isinstance(md, dict) and md.get("constraint"):
                    constraints.append(str(md["constraint"]))
            for constraint in constraints:
                _, spec = parse_requirement(constraint)
                if spec and not version_satisfies(locked, spec):
                    pkg_name = pkg_id.replace("pkg:", "")
                    conflicts.append(
                        Conflict(
                            id=f"conflict:lock_drift_{pkg_id}",
                            type=ConflictType.LOCKFILE_DRIFT,
                            description=(
                                f"Lockfile resolves {pkg_name} to {locked}, "
                                f"which does not satisfy declared {constraint!r}."
                            ),
                            involved_entities=[pkg_id],
                            metadata={
                                "locked_version": locked,
                                "constraint": constraint,
                            },
                        )
                    )
                    break
        return conflicts

    def _detect_compile_drift(self) -> list[Conflict]:  # noqa: C901
        """pip-tools: requirements.in constraints disagree with compiled requirements.txt pins."""
        if self.root_dir is None:
            return []
        parser = ProjectParser(str(self.root_dir))
        _in_pkgs, in_rels = parser.parse_requirements_in()
        _txt_pkgs, txt_rels = parser.parse_requirements_txt()

        inputs: dict[str, list[str]] = {}
        for rel in in_rels:
            constraint = rel.metadata.get("constraint")
            if constraint:
                inputs.setdefault(rel.target_id, []).append(str(constraint))

        compiled: dict[str, list[str]] = {}
        for rel in txt_rels:
            constraint = rel.metadata.get("constraint")
            if constraint:
                compiled.setdefault(rel.target_id, []).append(str(constraint))

        conflicts: list[Conflict] = []
        for pkg_id, input_constraints in inputs.items():
            compiled_constraints = compiled.get(pkg_id)
            if not compiled_constraints:
                continue
            for input_constraint in input_constraints:
                _, input_spec = parse_requirement(input_constraint)
                for compiled_constraint in compiled_constraints:
                    _name, compiled_spec = parse_requirement(compiled_constraint)
                    pinned = None
                    if compiled_spec and compiled_spec.startswith("=="):
                        pinned = compiled_spec.removeprefix("==").strip()
                    if pinned and input_spec and not version_satisfies(pinned, input_spec):
                        pkg_name = pkg_id.replace("pkg:", "")
                        conflicts.append(
                            Conflict(
                                id=f"conflict:compile_drift_{pkg_id}",
                                type=ConflictType.COMPILE_DRIFT,
                                description=(
                                    f"Compiled {pkg_name} is pinned to {pinned}, "
                                    f"which does not satisfy input {input_constraint!r}."
                                ),
                                involved_entities=[pkg_id],
                                metadata={
                                    "input_constraint": input_constraint,
                                    "compiled_constraint": compiled_constraint,
                                },
                            )
                        )
                        break
                if any(c.id == f"conflict:compile_drift_{pkg_id}" for c in conflicts):
                    break
        return conflicts

    def _package_import_usage(self, pkg: str) -> tuple[bool, bool]:
        """Return (has_any_import, has_non_test_import) for a declared package."""
        import_target_ids = {f"pkg:{name}" for name in self._package_import_names(pkg)}
        has_import = False
        has_non_test_import = False
        for u, v, data in self.G.edges(data=True):
            if v not in import_target_ids:
                continue
            if data.get("type") not in (
                RelationshipType.IMPORTS,
                RelationshipType.IMPORTS.value,
            ):
                continue
            has_import = True
            if not self._is_test_module(u):
                has_non_test_import = True
        return has_import, has_non_test_import

    def _detect_unused_dependencies(self) -> list[Conflict]:
        """
        Garbage Collection: Finds packages defined in REQUIRES that no module IMPORTS.
        Skips optional/dev dependency groups (not expected in application code).
        """
        conflicts: list[Conflict] = []
        declared_packages = [
            package_id
            for package_id in self._declared_package_ids()
            if self.G.nodes[package_id].get("type")
            in (EntityType.PACKAGE, EntityType.PACKAGE.value)
        ]

        for pkg in set(declared_packages):
            group = self._package_dependency_group(pkg)
            if group not in ("main", "requirements"):
                continue

            has_import, has_non_test_import = self._package_import_usage(pkg)
            if has_import and not has_non_test_import:
                continue

            if not has_import:
                conflicts.append(
                    Conflict(
                        id=f"conflict:unused_{pkg}",
                        type=ConflictType.UNUSED_DEPENDENCY,
                        description=(
                            f"Package '{pkg.replace('pkg:', '')}' is declared but never "
                            "imported in scanned modules."
                        ),
                        involved_entities=[pkg],
                    )
                )

        return conflicts
