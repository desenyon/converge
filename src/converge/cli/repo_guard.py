"""Shared validation for CLI commands that touch repository state."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from converge.cli.jsonutil import print_json
from converge.exit_codes import ExitCode
from converge.graph.store import GraphStore
from converge.project_context import ProjectContext


def ensure_target_directory(context: ProjectContext, *, command: str, json_mode: bool) -> None:
    if context.root_dir.is_dir():
        return
    message = f"Repository path does not exist: {context.root_dir}"
    if json_mode:
        print_json({"command": command, "status": "invalid_path", "error": message})
    else:
        Console().print(f"[red]{message}[/red]")
    raise typer.Exit(ExitCode.ERROR)


def load_graph_or_exit(
    context: ProjectContext,
    *,
    command: str,
    json_mode: bool,
    console: Console | None = None,
) -> GraphStore:
    """Open an existing scanned graph or exit with a stable no-graph error."""
    if not context.graph_db_path.is_file():
        _exit_no_graph(context, command=command, json_mode=json_mode, console=console)
    store = GraphStore.for_context(context, create_dirs=False)
    if not store.list_entities():
        store.close()
        _exit_no_graph(context, command=command, json_mode=json_mode, console=console)
    return store


def _exit_no_graph(
    context: ProjectContext,
    *,
    command: str,
    json_mode: bool,
    console: Console | None,
) -> None:
    message = f"No graph found for {context.root_dir}. Run `converge scan {context.root_dir}` first."
    if json_mode:
        print_json({"command": command, "status": "no_graph", "repository": str(context.root_dir)})
    elif console is not None:
        console.print(f"[red]{message}[/red]")
    else:
        Console().print(f"[red]{message}[/red]")
    raise typer.Exit(ExitCode.ERROR)


def resolve_target(path: str) -> ProjectContext:
    return ProjectContext.from_target(Path(path))
