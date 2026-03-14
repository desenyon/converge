from pathlib import Path

from converge.models import GraphEntity, GraphRelationship
from converge.scanner.ast_parser import PythonASTParser
from converge.scanner.project import ProjectParser
from converge.scanner.service_detector import ServiceDetector


class Scanner:
    """
    Orchestrates the different parsers to build a comprehensive graph of the codebase.
    """

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.entities: list[GraphEntity] = []
        self.relationships: list[GraphRelationship] = []

    def scan_all(self) -> tuple[list[GraphEntity], list[GraphRelationship]]:
        # 1. Parse Project files
        project_parser = ProjectParser(str(self.root_dir))

        pkgs, rels = project_parser.parse_pyproject()
        self.entities.extend(pkgs)
        self.relationships.extend(rels)

        pkgs_req, rels_req = project_parser.parse_requirements_txt()
        self.entities.extend(pkgs_req)
        self.relationships.extend(rels_req)

        # 2. Parse Python AST for imports
        ast_parser = PythonASTParser(str(self.root_dir))
        mods, mod_rels = ast_parser.scan_directory()
        self.entities.extend(mods)
        self.relationships.extend(mod_rels)

        # 3. Detect services and routes
        for p in self.root_dir.rglob("*.py"):
            if any(
                part.startswith(".") or part in ("venv", "env", "node_modules") for part in p.parts
            ):
                continue

            # Use relative paths for IDs to match ast_parser
            rel_path = p.relative_to(self.root_dir)
            routes, route_rels = ServiceDetector.scan_file(p)

            # Map absolute path back to relative mod ID in relationships
            for r in route_rels:
                r.source_id = f"mod:{rel_path}"

            self.entities.extend(routes)
            self.relationships.extend(route_rels)

        return self.entities, self.relationships
