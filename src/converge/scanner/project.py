import tomllib
from pathlib import Path

from converge.models import GraphRelationship, Package, RelationshipType


class ProjectParser:
    """
    Scans project configuration files like pyproject.toml and requirements.txt.
    """

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def _repo_id(self) -> str:
        return f"repo:{self.root_dir.name}"

    def _package_name_from_constraint(self, constraint: str) -> str:
        candidate = constraint.split(";")[0].strip()
        for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if separator in candidate:
                candidate = candidate.split(separator)[0]
                break
        if "[" in candidate:
            candidate = candidate.split("[", maxsplit=1)[0]
        return candidate.strip()

    def _build_dependency_records(
        self, constraints: list[str], source: str
    ) -> tuple[list[Package], list[GraphRelationship]]:
        packages = []
        relationships = []

        for constraint in constraints:
            package_name = self._package_name_from_constraint(constraint)
            if not package_name:
                continue

            package_id = f"pkg:{package_name}"
            packages.append(Package(id=package_id, name=package_name, metadata={"constraint": constraint}))
            relationships.append(
                GraphRelationship(
                    source_id=self._repo_id(),
                    target_id=package_id,
                    type=RelationshipType.REQUIRES,
                    metadata={"source": source},
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
        dependencies = list(project_data.get("dependencies", []))
        optional_dependency_groups = project_data.get("optional-dependencies", {})

        for group_constraints in optional_dependency_groups.values():
            dependencies.extend(group_constraints)

        return self._build_dependency_records(dependencies, "pyproject.toml")

    def parse_requirements_txt(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parses requirements.txt returning Package entities and REQUIRES relationships."""
        requirement_files = sorted(self.root_dir.glob("requirements*.txt"))
        if not requirement_files:
            return [], []

        packages = []
        relationships = []

        for requirement_file in requirement_files:
            constraints = []
            with requirement_file.open() as handle:
                for line in handle:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith("#"):
                        continue
                    constraints.append(stripped_line)

            file_packages, file_relationships = self._build_dependency_records(
                constraints, requirement_file.name
            )
            packages.extend(file_packages)
            relationships.extend(file_relationships)

        return packages, relationships
