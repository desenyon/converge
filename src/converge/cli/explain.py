from __future__ import annotations

from typing import Any

import networkx as nx
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from converge.cli.conflict_parse import parse_conflict_id
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
                    f"[yellow]{root_id} looks like a repair plan.[/yellow] Plans are generated during `converge fix` and are not stored in the graph."
                )
            else:
                self.console.print(f"[red]Entity not found:[/red] [cyan]{root_id}[/cyan]")
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
        """Explain a conflict using structured parsing (regex-backed)."""
        parsed = parse_conflict_id(conflict_id)
        self.console.print(f"[bold red]Conflict[/bold red] [cyan]{conflict_id}[/cyan]")

        if parsed["kind"] == "unresolved_import":
            self.console.print(
                Panel(
                    f"Module: [cyan]{parsed.get('module', '')}[/cyan]\n"
                    f"Import target: [magenta]{parsed.get('import_target', '')}[/magenta]\n\n"
                    f"The package is imported in code but not declared in the repository manifest.\n"
                    f"Add it to `pyproject.toml` or `requirements*.txt`, then rescan the repository.",
                    title="Unresolved Import",
                    border_style="red",
                )
            )
            return

        if parsed["kind"] == "unused_dependency":
            pkg = parsed.get("package_ref", "")
            self.console.print(
                Panel(
                    f"Package: [magenta]{pkg}[/magenta]\n\n"
                    f"The package is declared in the manifest but no scanned Python module imports it.\n"
                    f"Remove it if it is truly unused, or keep it only if it is required indirectly at runtime.",
                    title="Unused Dependency",
                    border_style="yellow",
                )
            )
            return

        if parsed["kind"] == "version_clash":
            self.console.print(
                Panel(
                    f"Entities involved: [cyan]{parsed.get('raw', '')}[/cyan]\n\n"
                    f"Two or more declared constraints disagree on a compatible version.",
                    title="Version clash",
                    border_style="red",
                )
            )
            return

        if parsed["kind"] == "invalid":
            self.console.print(f"[red]Invalid conflict format: {conflict_id}[/red]")
            return

        self.console.print(
            Panel(
                f"[white]{parsed.get('raw', conflict_id)}[/white]",
                title="Conflict Detail",
            )
        )

    def explain_as_dict(self, target: str) -> dict[str, Any]:
        """Structured explanation for --json output."""
        if "conflict:" in target:
            parsed = parse_conflict_id(target)
            if parsed["kind"] == "unresolved_import":
                return {
                    "parsed": parsed,
                    "guidance": "Declare the dependency in pyproject.toml or requirements*.txt, then rescan.",
                }
            if parsed["kind"] == "unused_dependency":
                return {
                    "parsed": parsed,
                    "guidance": "Declared in the manifest but not imported by scanned modules (test-only imports may still count as usage).",
                }
            if parsed["kind"] == "version_clash":
                return {
                    "parsed": parsed,
                    "guidance": "Resolve overlapping version constraints in manifests.",
                }
            if parsed["kind"] == "invalid":
                return {"kind": "invalid", "error": parsed.get("error", "not_a_conflict_id")}
            return {"parsed": parsed, "guidance": "See raw conflict id."}

        if target not in self.G:
            if target.startswith("plan:") or target.isdigit():
                return {
                    "kind": "not_in_graph",
                    "target": target,
                    "note": "Repair plans are generated during `converge fix` and are not stored in the graph.",
                }
            return {"kind": "not_found", "target": target}

        root_data = self.G.nodes[target]
        requires: list[dict[str, Any]] = []
        for succ in self.G.successors(target):
            edge_data = self.G.get_edge_data(target, succ)
            if edge_data and (
                edge_data.get("type") == str(RelationshipType.REQUIRES)
                or str(edge_data.get("type")) == str(RelationshipType.REQUIRES)
            ):
                succ_data = self.G.nodes[succ]
                requires.append({"id": succ, "name": succ_data.get("name", succ)})
        return {
            "kind": "entity",
            "entity_id": target,
            "name": root_data.get("name", target),
            "entity_type": str(root_data.get("type", "")),
            "requires": requires,
        }
