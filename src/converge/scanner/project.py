import tomllib
from pathlib import Path

from converge.models import GraphRelationship, Package, RelationshipType
from converge.versioning.constraints import parse_requirement


class ProjectParser:
    """
    Scans project configuration files like pyproject.toml and requirements.txt.
    """

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def _repo_id(self) -> str:
        return f"repo:{self.root_dir.name}"

    def _package_name_from_constraint(self, constraint: str) -> str:
        name, _ = parse_requirement(constraint)
        return name

    def _is_skippable_directive(self, line: str) -> bool:
        stripped = line.strip()
        if stripped.startswith("--"):
            return True
        if not stripped.startswith("-"):
            return False
        return stripped.startswith(("-e", "--editable"))

    def _directive_path(self, line: str) -> str | None:
        stripped = line.strip()
        for prefix in ("-r", "--requirement", "-c", "--constraint"):
            if stripped.startswith(prefix):
                return stripped[len(prefix) :].strip()
        return None

    def _read_requirement_lines(self, path: Path) -> list[str]:
        if not path.is_file():
            return []
        lines: list[str] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if self._is_skippable_directive(stripped):
                    continue
                include = self._directive_path(stripped)
                if include:
                    nested = self.root_dir / include
                    lines.extend(self._read_requirement_lines(nested))
                    continue
                lines.append(stripped)
        return lines

    def _build_dependency_records(
        self,
        constraints: list[str],
        source: str,
        *,
        dependency_group: str = "main",
        source_kind: str = "declared",
    ) -> tuple[list[Package], list[GraphRelationship]]:
        packages: list[Package] = []
        relationships: list[GraphRelationship] = []

        for constraint in constraints:
            package_name = self._package_name_from_constraint(constraint)
            if not package_name:
                continue

            package_id = f"pkg:{package_name}"
            is_editable = constraint.strip().startswith(("-e", "--editable"))
            packages.append(
                Package(
                    id=package_id,
                    name=package_name,
                    metadata={
                        "constraint": constraint,
                        "source": source,
                        "dependency_group": dependency_group,
                        "editable": is_editable,
                        "source_kind": source_kind,
                    },
                )
            )
            relationships.append(
                GraphRelationship(
                    source_id=self._repo_id(),
                    target_id=package_id,
                    type=RelationshipType.REQUIRES,
                    metadata={
                        "source": source,
                        "constraint": constraint,
                        "dependency_group": dependency_group,
                        "source_kind": source_kind,
                    },
                )
            )
            if is_editable:
                relationships.append(
                    GraphRelationship(
                        source_id=package_id,
                        target_id=self._repo_id(),
                        type=RelationshipType.CONFIGURED_BY,
                        metadata={"constraint": constraint, "editable": True},
                    )
                )

        return packages, relationships

    def parse_pyproject(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parses pyproject.toml returning Package entities and REQUIRES relationships."""
        toml_path = self.root_dir / "pyproject.toml"
        if not toml_path.exists():
            return [], []

        with open(toml_path, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError:
                return [], []

        project_data = data.get("project", {})
        packages: list[Package] = []
        relationships: list[GraphRelationship] = []

        main_deps = list(project_data.get("dependencies", []))
        pkgs, rels = self._build_dependency_records(
            main_deps, "pyproject.toml", dependency_group="main"
        )
        packages.extend(pkgs)
        relationships.extend(rels)

        optional_dependency_groups = project_data.get("optional-dependencies", {})
        if isinstance(optional_dependency_groups, dict):
            for group_name, group_constraints in optional_dependency_groups.items():
                if not isinstance(group_constraints, list):
                    continue
                pkgs, rels = self._build_dependency_records(
                    [str(c) for c in group_constraints],
                    "pyproject.toml",
                    dependency_group=str(group_name),
                )
                packages.extend(pkgs)
                relationships.extend(rels)

        tool_uv = data.get("tool", {}).get("uv", {})
        if isinstance(tool_uv, dict):
            dep_groups = tool_uv.get("dependency-groups", {})
            if isinstance(dep_groups, dict):
                for group_name, group_constraints in dep_groups.items():
                    if not isinstance(group_constraints, list):
                        continue
                    pkgs, rels = self._build_dependency_records(
                        [str(c) for c in group_constraints],
                        "pyproject.toml",
                        dependency_group=str(group_name),
                    )
                    packages.extend(pkgs)
                    relationships.extend(rels)

        return packages, relationships

    def parse_requirements_txt(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parses requirements*.txt returning Package entities and REQUIRES relationships."""
        requirement_files = sorted(self.root_dir.glob("requirements*.txt"))
        if not requirement_files:
            return [], []

        packages: list[Package] = []
        relationships: list[GraphRelationship] = []

        for requirement_file in requirement_files:
            constraints = self._read_requirement_lines(requirement_file)
            group = "main"
            stem = requirement_file.stem
            if stem != "requirements":
                group = stem.removeprefix("requirements-") or stem

            file_packages, file_relationships = self._build_dependency_records(
                constraints,
                requirement_file.name,
                dependency_group=group,
                source_kind="compiled",
            )
            packages.extend(file_packages)
            relationships.extend(file_relationships)

        return packages, relationships

    def parse_requirements_in(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parses requirements.in (pip-tools) when present."""
        packages: list[Package] = []
        relationships: list[GraphRelationship] = []
        for in_file in sorted(self.root_dir.glob("requirements*.in")):
            constraints = self._read_requirement_lines(in_file)
            group = "main"
            stem = in_file.stem
            if stem != "requirements":
                group = stem.removeprefix("requirements-") or stem
            pkgs, rels = self._build_dependency_records(
                constraints,
                in_file.name,
                dependency_group=group,
                source_kind="input",
            )
            packages.extend(pkgs)
            relationships.extend(rels)
        return packages, relationships

    def parse_constraint_files(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parse standalone constraints*.txt referenced by pip -c."""
        packages: list[Package] = []
        relationships: list[GraphRelationship] = []
        for path in sorted(self.root_dir.glob("constraints*.txt")):
            constraints = self._read_requirement_lines(path)
            pkgs, rels = self._build_dependency_records(
                constraints,
                path.name,
                dependency_group="constraints",
                source_kind="constraint",
            )
            packages.extend(pkgs)
            relationships.extend(rels)
        return packages, relationships
