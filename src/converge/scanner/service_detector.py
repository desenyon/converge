import ast
from pathlib import Path

from converge.models import GraphRelationship, RelationshipType, Route


class ServiceDetector(ast.NodeVisitor):
    """
    Heuristic AST visitor to detect FastAPI/Flask routes and services.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.routes: list[Route] = []
        self.relationships: list[GraphRelationship] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Looks for decorators like @app.get('/path') to infer routes.
        """
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func = decorator.func

                # Check for forms like app.get(...) or router.post(...)
                if isinstance(func, ast.Attribute):
                    method_name = func.attr.upper()

                    if method_name in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                        # Try to extract the path from the first argument
                        if decorator.args and isinstance(decorator.args[0], ast.Constant):
                            route_path = decorator.args[0].value

                            # Ensure route_path is a string
                            if isinstance(route_path, bytes):
                                route_path = route_path.decode("utf-8")
                            elif not isinstance(route_path, str):
                                route_path = str(route_path)

                            route_id = f"route:{method_name}:{route_path}"
                            route = Route(
                                id=route_id,
                                name=f"{method_name} {route_path}",
                                method=method_name,
                                path=route_path,
                                metadata={"file": str(self.file_path), "line": node.lineno},
                            )
                            self.routes.append(route)

                            # The module exposes this route
                            mod_id = f"mod:{self.file_path}"
                            rel = GraphRelationship(
                                source_id=mod_id, target_id=route_id, type=RelationshipType.EXPOSES
                            )
                            self.relationships.append(rel)

        self.generic_visit(node)

    @classmethod
    def scan_file(cls, path: Path) -> tuple[list[Route], list[GraphRelationship]]:
        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(path))
            detector = cls(path)
            detector.visit(tree)
            return detector.routes, detector.relationships
        except (SyntaxError, UnicodeDecodeError):
            return [], []
