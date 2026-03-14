import tomllib
from pathlib import Path

from converge.models import GraphRelationship, Package, RelationshipType


class ProjectParser:
    """
    Scans project configuration files like pyproject.toml and requirements.txt.
    """
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

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

        packages = []
        relationships = []

        # Extract dependencies
        deps = data.get("project", {}).get("dependencies", [])
        for dep in deps:
            # Very basic parsing, a real implementation would use packaging.requirements
            pkg_name = dep.split(">=")[0].split("==")[0].split("<=")[0].split("~=")[0].strip()
            pkg_id = f"pkg:{pkg_name}"

            pkg = Package(
                id=pkg_id,
                name=pkg_name,
                metadata={"constraint": dep}
            )
            packages.append(pkg)

            # The repository requires this package
            rel = GraphRelationship(
                source_id=f"repo:{self.root_dir.name}",
                target_id=pkg_id,
                type=RelationshipType.REQUIRES,
                metadata={"source": "pyproject.toml"}
            )
            relationships.append(rel)

        return packages, relationships

    def parse_requirements_txt(self) -> tuple[list[Package], list[GraphRelationship]]:
        """Parses requirements.txt returning Package entities and REQUIRES relationships."""
        req_path = self.root_dir / "requirements.txt"
        if not req_path.exists():
            return [], []

        packages = []
        relationships = []

        with open(req_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Same naive split
                pkg_name = line.split(">=")[0].split("==")[0].split("<=")[0].split("~=")[0].strip()
                pkg_id = f"pkg:{pkg_name}"

                pkg = Package(
                    id=pkg_id,
                    name=pkg_name,
                    metadata={"constraint": line}
                )
                packages.append(pkg)

                rel = GraphRelationship(
                    source_id=f"repo:{self.root_dir.name}",
                    target_id=pkg_id,
                    type=RelationshipType.REQUIRES,
                    metadata={"source": "requirements.txt"}
                )
                relationships.append(rel)

        return packages, relationships
