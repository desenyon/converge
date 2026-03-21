import logging
from pathlib import Path

from converge.graph.store import GraphStore
from converge.models import EntityType, GraphEntity, GraphRelationship, RelationshipType
from converge.scanner.ast_parser import PythonASTParser
from converge.scanner.incremental import (
    classify_file_changes,
    fingerprint_files,
    load_scan_state,
)
from converge.scanner.paths import iter_python_files
from converge.scanner.project import ProjectParser
from converge.scanner.service_detector import ServiceDetector
from converge.settings import ConvergeSettings

log = logging.getLogger("converge.scanner")


class Scanner:
    """Orchestrates parsers to build a graph of the codebase."""

    def __init__(self, root_dir: str, settings: ConvergeSettings | None = None):
        self.root_dir = Path(root_dir)
        self.settings = settings or ConvergeSettings()

    def scan_incremental(
        self, store: GraphStore, scan_state_path: Path, py_files: list[Path]
    ) -> tuple[list[GraphEntity], list[GraphRelationship]] | None:
        """
        Merge prior graph with AST/service data for changed files only.

        Returns None to signal caller should run a full scan_all().
        """
        if not self.settings.incremental_scan:
            return None
        prev = load_scan_state(scan_state_path)
        cur_fp = fingerprint_files(self.root_dir, py_files)
        if not prev:
            return None
        to_reparse, removed, unchanged_paths = classify_file_changes(prev, cur_fp)
        if not to_reparse and not removed:
            return None
        if len(to_reparse) == len(cur_fp):
            log.debug("incremental: all files changed; using full scan")
            return None

        old_entities = store.list_entities()
        old_rels = store.list_relationships()

        unchanged_mod_ids = {f"mod:{rel}" for rel in unchanged_paths}

        modules_kept = [
            e for e in old_entities if e.type == EntityType.MODULE and e.id in unchanged_mod_ids
        ]
        rels_kept = [
            r
            for r in old_rels
            if r.source_id in unchanged_mod_ids
            and r.type in (RelationshipType.IMPORTS, RelationshipType.EXPOSES)
        ]
        route_ids_kept = {r.target_id for r in rels_kept if r.type == RelationshipType.EXPOSES}
        routes_kept = [
            e for e in old_entities if e.type == EntityType.ROUTE and e.id in route_ids_kept
        ]

        project_parser = ProjectParser(str(self.root_dir))
        pkgs, rels = project_parser.parse_pyproject()
        pkgs_req, rels_req = project_parser.parse_requirements_txt()

        paths_to_parse = sorted(self.root_dir / rel for rel in to_reparse)
        ast_parser = PythonASTParser(str(self.root_dir), settings=self.settings)
        log.debug(
            "incremental scan: reparse %d file(s), removed %d path(s), keep %d module(s)",
            len(to_reparse),
            len(removed),
            len(modules_kept),
        )
        new_mods, new_ast_rels = ast_parser.scan_files(paths_to_parse)

        new_routes: list[GraphEntity] = []
        new_route_rels: list[GraphRelationship] = []
        for p in paths_to_parse:
            rel_path = p.relative_to(self.root_dir)
            routes, route_rels = ServiceDetector.scan_file(p)
            for r in route_rels:
                r.source_id = f"mod:{rel_path.as_posix()}"
            new_routes.extend(routes)
            new_route_rels.extend(route_rels)

        entities: list[GraphEntity] = (
            list(pkgs) + list(pkgs_req) + modules_kept + routes_kept + new_mods + new_routes
        )
        relationships: list[GraphRelationship] = (
            list(rels) + list(rels_req) + rels_kept + new_ast_rels + new_route_rels
        )
        return entities, relationships

    def scan_all(self) -> tuple[list[GraphEntity], list[GraphRelationship]]:
        project_parser = ProjectParser(str(self.root_dir))

        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []

        pkgs, rels = project_parser.parse_pyproject()
        entities.extend(pkgs)
        relationships.extend(rels)

        pkgs_req, rels_req = project_parser.parse_requirements_txt()
        entities.extend(pkgs_req)
        relationships.extend(rels_req)

        ast_parser = PythonASTParser(str(self.root_dir), settings=self.settings)
        mods, mod_rels = ast_parser.scan_directory()
        entities.extend(mods)
        relationships.extend(mod_rels)

        for p in iter_python_files(self.root_dir, self.settings):
            rel_path = p.relative_to(self.root_dir)
            routes, route_rels = ServiceDetector.scan_file(p)

            for r in route_rels:
                r.source_id = f"mod:{rel_path.as_posix()}"

            entities.extend(routes)
            relationships.extend(route_rels)

        return entities, relationships
