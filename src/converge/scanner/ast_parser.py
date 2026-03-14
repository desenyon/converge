import ast
from pathlib import Path

from converge.models import GraphRelationship, Module, RelationshipType


class PythonASTParser:
    """
    Parses Python files to extract imports and module relationships.
    """
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def scan_directory(self) -> tuple[list[Module], list[GraphRelationship]]:
        """Walks the directory and parses all Python files."""
        modules = []
        relationships = []

        for p in self.root_dir.rglob("*.py"):
            # Skip hidden dirs or common virtualenvs
            if any(part.startswith(".") or part in ("venv", "env", "node_modules") for part in p.parts):
                continue

            mod_id = f"mod:{p.relative_to(self.root_dir)}"
            mod = Module(
                id=mod_id,
                name=p.name,
                file_path=str(p)
            )
            modules.append(mod)

            try:
                content = p.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(p))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            target_pkg = name.name.split('.')[0] # Heuristic: top level package
                            relationships.append(
                                GraphRelationship(
                                    source_id=mod_id,
                                    target_id=f"pkg:{target_pkg}",
                                    type=RelationshipType.IMPORTS,
                                    metadata={"full_import": name.name, "line": node.lineno}
                                )
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            target_pkg = node.module.split('.')[0]
                            relationships.append(
                                GraphRelationship(
                                    source_id=mod_id,
                                    target_id=f"pkg:{target_pkg}",
                                    type=RelationshipType.IMPORTS,
                                    metadata={"full_import": node.module, "line": node.lineno}
                                )
                            )
            except (SyntaxError, UnicodeDecodeError):
                # We skip files we can't parse safely
                continue

        return modules, relationships
