from __future__ import annotations

from typing import Any

import networkx as nx
from rich.console import Console
from rich.tree import Tree

from converge.models import RelationshipType


class ExplainabilityEngine:
    def __init__(self, G: nx.DiGraph[Any], console: Console):
        self.G = G
        self.console = console

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
        self.console.print(tree)

    def _build_tree(
        self, node_id: str, tree: Tree, edge_type: str, depth: int = 0, max_depth: int = 3
    ) -> None:
        if depth > max_depth:
            tree.add("[dim]... (max depth reached)[/dim]")
            return

        for succ in self.G.successors(node_id):
            edge_data = self.G.get_edge_data(node_id, succ)
            if edge_data and edge_data.get("type") == edge_type:
                succ_data = self.G.nodes[succ]
                branch = tree.add(f"[green]{succ_data.get('name', succ)}[/green]")
                self._build_tree(succ, branch, edge_type, depth + 1, max_depth)

    def explain_conflict(self, conflict_id: str) -> None:
        self.console.print(f"[bold red]Conflict Analysis:[/bold red] {conflict_id}")
        # In a real system we would extract this directly from the DB
        self.console.print("[white]Detailed path reasoning would be rendered here.[/white]")
