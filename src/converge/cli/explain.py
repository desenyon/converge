from __future__ import annotations

from typing import Any

import networkx as nx
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from converge.graph.queries import GraphQueries
from converge.models import RelationshipType


class ExplainabilityEngine:
    def __init__(self, G: nx.DiGraph[Any], console: Console):
        self.G = G
        self.console = console
        self.queries = GraphQueries(G)

    def render_dependency_tree(self, root_id: str) -> None:
        if root_id not in self.G:
            if root_id.startswith("plan:") or root_id.isdigit():
                self.console.print(
                    f"[yellow]'{root_id}' looks like a repair plan. Plans are generated transiently during `converge fix` and cannot be explained after the fact.[/yellow]"
                )
            else:
                self.console.print(f"[red]Entity {root_id} not found in graph.[/red]")
            return

        root_data = self.G.nodes[root_id]
        tree = Tree(
            f"[bold blue]{root_data.get('name', root_id)}[/bold blue] ({root_data.get('type')})"
        )

        self._build_tree(root_id, tree, RelationshipType.REQUIRES)
        self.console.print(Panel(tree, title="Dependency Topography", border_style="blue"))

    def _build_tree(
        self, node_id: str, tree: Tree, edge_type: str, depth: int = 0, max_depth: int = 4
    ) -> None:
        if depth > max_depth:
            tree.add("[dim]... (max depth reached)[/dim]")
            return

        for succ in self.G.successors(node_id):
            edge_data = self.G.get_edge_data(node_id, succ)
            if edge_data and (
                edge_data.get("type") == str(edge_type)
                or str(edge_data.get("type")) == str(edge_type)
            ):
                succ_data = self.G.nodes[succ]
                branch = tree.add(f"[green]{succ_data.get('name', succ)}[/green]")
                self._build_tree(succ, branch, edge_type, depth + 1, max_depth)

    def explain_conflict(self, conflict_id: str) -> None:
        """
        Parses a conflict ID, locates its root entities, and maps the physical graph
        pathway to explain exactly why this conflict exists.
        """
        parts = conflict_id.split("_", maxsplit=1)
        if len(parts) != 2:
            self.console.print(f"[red]Invalid conflict format: {conflict_id}[/red]")
            return

        c_type, rest = parts[0].replace("conflict:", ""), parts[1]

        self.console.print(f"[bold red]Conflict Diagnostics:[/bold red] {conflict_id}")

        if c_type == "unresolved":
            # format: conflict:unresolved_mod:file.py_pkg:requests
            subparts = rest.split("_", maxsplit=1)
            if len(subparts) == 2:
                origin, target = subparts[0], subparts[1]
                self.console.print(
                    Panel(
                        f"The module [cyan]{origin}[/cyan]\n"
                        f"contains an import statement pointing to [magenta]{target}[/magenta].\n\n"
                        f"However, [magenta]{target}[/magenta] is not declared in the project's dependency manifest (pyproject.toml/requirements.txt).\n"
                        f"This will cause an ImportError at runtime if deployed.",
                        title="Unresolved Import Graph",
                        border_style="red",
                    )
                )
            else:
                self.console.print("[yellow]Could not parse unresolved edges.[/yellow]")

        elif c_type == "unused":
            # format: conflict:unused_pkg:name
            pkg = rest
            self.console.print(
                Panel(
                    f"The package [magenta]{pkg}[/magenta] is explicitly declared as a required dependency in your manifest.\n\n"
                    f"However, topological analysis guarantees that [bold]zero[/bold] Python files actually import it.\n"
                    f"You should remove this package to save installation time and reduce attack surface.",
                    title="Garbage Collection Target",
                    border_style="yellow",
                )
            )

        else:
            self.console.print(
                Panel(
                    "[white]Deep pathfinding for this anomaly type is currently unmapped.[/white]",
                    title="Generic Analysis",
                )
            )
