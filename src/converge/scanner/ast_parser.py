import ast
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from converge.models import GraphRelationship, Module, RelationshipType
from converge.scanner.paths import module_scan_kind
from converge.settings import ConvergeSettings

log = logging.getLogger("converge.scanner.ast")


def _is_type_checking_if(node: ast.If) -> bool:
    t = node.test
    if isinstance(t, ast.Name) and t.id == "TYPE_CHECKING":
        return True
    return isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"


def _is_local_or_stdlib(target_pkg: str, root_dir: Path) -> bool:
    if target_pkg in sys.stdlib_module_names:
        return True
    if (root_dir / target_pkg).is_dir() or (root_dir / f"{target_pkg}.py").is_file():
        return True
    if (root_dir / "src" / target_pkg).exists():
        return True
    return False


class _ImportVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        root_dir: Path,
        mod_id: str,
        skip_type_checking_imports: bool,
    ) -> None:
        self._root_dir = root_dir
        self._mod_id = mod_id
        self._skip_tc = skip_type_checking_imports
        self._tc_depth = 0
        self._rels: list[GraphRelationship] = []

    def _add_import_edge(self, target_pkg: str, *, line: int, dynamic: str) -> None:
        if _is_local_or_stdlib(target_pkg, self._root_dir):
            return
        self._rels.append(
            GraphRelationship(
                source_id=self._mod_id,
                target_id=f"pkg:{target_pkg}",
                type=RelationshipType.IMPORTS,
                metadata={"full_import": target_pkg, "line": line, "dynamic": dynamic},
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        if self._skip_tc and self._tc_depth > 0:
            self.generic_visit(node)
            return
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    target_pkg = arg0.value.split(".", maxsplit=1)[0]
                    self._add_import_edge(target_pkg, line=node.lineno, dynamic="__import__")
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib":
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        target_pkg = arg0.value.split(".", maxsplit=1)[0]
                        self._add_import_edge(
                            target_pkg, line=node.lineno, dynamic="importlib.import_module"
                        )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_if(node):
            self._tc_depth += 1
            self.generic_visit(node)
            self._tc_depth -= 1
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        if self._skip_tc and self._tc_depth > 0:
            return
        for name in node.names:
            target_pkg = name.name.split(".")[0]
            if _is_local_or_stdlib(target_pkg, self._root_dir):
                continue
            self._rels.append(
                GraphRelationship(
                    source_id=self._mod_id,
                    target_id=f"pkg:{target_pkg}",
                    type=RelationshipType.IMPORTS,
                    metadata={"full_import": name.name, "line": node.lineno},
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._skip_tc and self._tc_depth > 0:
            return
        if not node.module:
            return
        target_pkg = node.module.split(".")[0]
        if _is_local_or_stdlib(target_pkg, self._root_dir):
            return
        self._rels.append(
            GraphRelationship(
                source_id=self._mod_id,
                target_id=f"pkg:{target_pkg}",
                type=RelationshipType.IMPORTS,
                metadata={"full_import": node.module, "line": node.lineno},
            )
        )


class PythonASTParser:
    """Parses Python files to extract imports and module relationships."""

    def __init__(self, root_dir: str, settings: ConvergeSettings | None = None):
        self.root_dir = Path(root_dir)
        self.settings = settings or ConvergeSettings()

    def _parse_file(self, p: Path) -> tuple[Module, list[GraphRelationship]] | None:
        try:
            rel = p.relative_to(self.root_dir)
        except ValueError:
            return None
        mod_id = f"mod:{rel.as_posix()}"
        kind = module_scan_kind(rel, self.settings)
        mod = Module(
            id=mod_id,
            name=p.name,
            file_path=str(p),
            metadata={"scan_kind": kind},
        )
        try:
            content = p.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(p))
        except (SyntaxError, UnicodeDecodeError, OSError):
            return mod, []

        visitor = _ImportVisitor(
            root_dir=self.root_dir,
            mod_id=mod_id,
            skip_type_checking_imports=self.settings.skip_type_checking_imports,
        )
        visitor.visit(tree)
        return mod, visitor._rels

    def scan_files(self, paths: list[Path]) -> tuple[list[Module], list[GraphRelationship]]:
        modules: list[Module] = []
        relationships: list[GraphRelationship] = []

        workers = self.settings.scan_workers
        if workers is None:
            workers = min(32, (os.cpu_count() or 4) + 4)

        log.debug("parsing %d python file(s) with up to %d worker(s)", len(paths), workers)

        if workers <= 1 or len(paths) <= 1:
            for p in paths:
                parsed = self._parse_file(p)
                if parsed is None:
                    continue
                m, rels = parsed
                modules.append(m)
                relationships.extend(rels)
            return modules, relationships

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._parse_file, p): p for p in paths}
            for fut in as_completed(futures):
                parsed = fut.result()
                if parsed is None:
                    continue
                m, rels = parsed
                modules.append(m)
                relationships.extend(rels)
        return modules, relationships

    def scan_directory(self) -> tuple[list[Module], list[GraphRelationship]]:
        from converge.scanner.paths import iter_python_files

        paths = iter_python_files(self.root_dir, self.settings)
        return self.scan_files(paths)
