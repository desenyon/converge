"""Rich terminal UI helpers for a consistent Converge CLI experience."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from converge.project_context import ProjectContext
from converge.solver.conflict import Conflict, ConflictType
from converge.version_info import package_version

BRAND = "#2dd4bf"
ACCENT = "#8b5cf6"
MUTED = "bright_black"

COMMAND_LABELS: dict[str, str] = {
    "scan": "Scan",
    "doctor": "Doctor",
    "fix": "Fix",
    "create": "Create",
    "check": "Check",
    "packages": "Packages",
    "audit": "Audit",
    "init": "Init",
    "status": "Status",
    "explain": "Explain",
    "export": "Export",
    "clean": "Clean",
}


def command_header(
    command: str,
    title: str,
    context: ProjectContext,
    *,
    subtitle: str | None = None,
) -> Panel:
    """Branded header panel shown at the start of interactive commands."""
    label = COMMAND_LABELS.get(command, title)
    lines = [
        Text.assemble(
            (label.upper(), f"bold {BRAND}"),
            ("  ", ""),
            (title, "bold white"),
        ),
        Text(str(context.root_dir), style=MUTED),
    ]
    if subtitle:
        lines.append(Text(subtitle, style="dim italic"))
    return Panel(
        Group(*lines),
        border_style=BRAND,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def print_header(console: Console, command: str, title: str, context: ProjectContext, **kw: Any) -> None:
    console.print(command_header(command, title, context, **kw))


def footer_hint(console: Console, message: str) -> None:
    console.print()
    console.print(Rule(style=MUTED))
    console.print(Text(message, style="dim italic"))


def success_panel(title: str, body: str, *, border_style: str = "green") -> Panel:
    return Panel(
        body,
        title=f"[bold]{title}[/bold]",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def warning_panel(title: str, body: str) -> Panel:
    return Panel(
        body,
        title=f"[bold]{title}[/bold]",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def error_panel(title: str, body: str) -> Panel:
    return Panel(
        body,
        title=f"[bold]{title}[/bold]",
        border_style="red",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def status_badge(ok: bool, yes: str = "ready", no: str = "missing") -> Text:
    if ok:
        return Text(f" {yes} ", style="bold white on dark_green")
    return Text(f" {no} ", style="bold white on dark_red")


def conflict_style(conflict_type: str) -> str:
    mapping = {
        ConflictType.UNRESOLVED_IMPORT: "bold red",
        ConflictType.UNUSED_DEPENDENCY: "bold yellow",
        ConflictType.VERSION_CLASH: "bold magenta",
        ConflictType.MISSING_PACKAGE: "bold orange3",
    }
    return mapping.get(conflict_type, "bold white")


def metrics_table(
    title: str,
    rows: list[tuple[str, str]],
    *,
    highlight_last: bool = False,
) -> Table:
    table = Table(
        title=title,
        title_style=f"bold {BRAND}",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=f"bold {ACCENT}",
        border_style=MUTED,
        pad_edge=False,
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", overflow="fold")
    for idx, (metric, value) in enumerate(rows):
        style = "bold green" if highlight_last and idx == len(rows) - 1 else None
        table.add_row(metric, value, style=style)
    return table


def conflict_table(conflicts: list[Conflict]) -> Table:
    count = len(conflicts)
    issue_word = "issue" if count == 1 else "issues"
    table = Table(
        title=f"Detected {count} {issue_word}",
        title_style="bold red",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {ACCENT}",
        border_style="red",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("ID", style="cyan", no_wrap=True, max_width=28, overflow="ellipsis")
    table.add_column("Type", no_wrap=True)
    table.add_column("Description", ratio=2, overflow="fold")

    for conflict in conflicts:
        short_id = conflict.id if len(conflict.id) <= 28 else conflict.id[:25] + "..."
        table.add_row(
            short_id,
            Text(conflict.type.replace("_", " ").upper(), style=conflict_style(conflict.type)),
            conflict.description,
        )
    return table


def package_inventory_table(summary: dict[str, Any]) -> Table:
    table = Table(
        title="Package Inventory",
        title_style=f"bold {BRAND}",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {ACCENT}",
        border_style=MUTED,
        expand=True,
    )
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", no_wrap=True)
    table.add_column("Packages", overflow="fold")

    categories = [
        ("Declared", summary["declared_count"], summary["declared"], None),
        ("Imported", summary["imported_count"], summary["imported"], None),
        ("Missing", summary["missing_count"], summary["missing"], "red"),
        ("Unused", summary["unused_count"], summary["unused"], "yellow"),
    ]
    for name, count, items, color in categories:
        packages = ", ".join(items) if items else "—"
        style = f"bold {color}" if color and count else None
        table.add_row(name, str(count), packages, style=style)
    return table


def status_dashboard(
    *,
    graph_ready: bool,
    entity_count: int,
    relationship_count: int,
    tracked_files: int,
    incremental_enabled: bool,
    tree_unchanged: bool,
    lockfile_count: int,
    tool_version: str | None = None,
) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="cyan", no_wrap=True)
    grid.add_column(no_wrap=True)
    grid.add_column(style="cyan", no_wrap=True)
    grid.add_column(no_wrap=True)

    grid.add_row(
        "Graph",
        status_badge(graph_ready, "present", "missing"),
        "Entities",
        str(entity_count),
    )
    grid.add_row(
        "Relationships",
        str(relationship_count),
        "Tracked files",
        str(tracked_files),
    )
    grid.add_row(
        "Incremental",
        status_badge(incremental_enabled, "on", "off"),
        "Tree unchanged",
        status_badge(tree_unchanged, "yes", "no"),
    )
    grid.add_row(
        "Lockfiles",
        str(lockfile_count),
        "Converge",
        tool_version or package_version(),
    )

    return Panel(
        grid,
        title="[bold]Repository Status[/bold]",
        border_style=BRAND,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def audit_table(events: list[dict[str, Any]]) -> Table:
    table = Table(
        title=f"Audit Log ({len(events)} events)",
        title_style=f"bold {BRAND}",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {ACCENT}",
        border_style=MUTED,
        expand=True,
    )
    table.add_column("Timestamp", style="dim", no_wrap=True)
    table.add_column("Event", style="cyan", no_wrap=True)
    table.add_column("Details", overflow="fold")
    for event in events:
        table.add_row(
            str(event.get("ts", "")),
            str(event.get("event", "")),
            str(event.get("plan_id") or event.get("applied") or ""),
        )
    return table


def repair_plan_table(plan_id: str, actions: list[Any]) -> Table:
    table = Table(
        title=f"Repair Plan · {plan_id}",
        title_style=f"bold {ACCENT}",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {BRAND}",
        border_style=ACCENT,
        expand=True,
    )
    table.add_column("Action", style="magenta", no_wrap=True)
    table.add_column("Target", style="green", no_wrap=True)
    table.add_column("Rationale", overflow="fold")
    for action in actions:
        table.add_row(action.action_type, action.target_package, action.description)
    return table


def make_progress(console: Console, *, transient: bool = True) -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots12", style=BRAND),
        TextColumn("[progress.description]{task.description}", style="cyan"),
        BarColumn(bar_width=32, style=ACCENT, complete_style=BRAND),
        TimeElapsedColumn(),
        console=console,
        transient=transient,
    )


def scan_complete_panel(graph_path: Path, entities: int, relationships: int, mode: str) -> Panel:
    body = (
        f"[bold green]Graph persisted[/bold green]\n"
        f"[dim]Path[/dim]  [cyan]{str(graph_path)}[/cyan]\n"
        f"[dim]Mode[/dim]  {mode}\n"
        f"[dim]Size[/dim]  {entities} entities · {relationships} relationships"
    )
    return success_panel("Scan Complete", body, border_style=BRAND)


def activation_panel(venv_path: Path, activate_cmd: str) -> Panel:
    body = (
        f"[bold green]Environment ready[/bold green]\n\n"
        f"[dim]Path[/dim]     [cyan]{venv_path}[/cyan]\n"
        f"[dim]Activate[/dim]  [cyan]{activate_cmd}[/cyan]"
    )
    return Panel(body, border_style="green", box=box.ROUNDED, padding=(0, 1))


def export_result_panel(format_name: str, artifacts: Sequence[Path | str]) -> Panel:
    joined = ", ".join(str(path) for path in artifacts)
    body = (
        f"[bold green]Export complete[/bold green]\n\n"
        f"[dim]Format[/dim]    {format_name}\n"
        f"[dim]Artifacts[/dim]  [cyan]{joined}[/cyan]"
    )
    return success_panel("Export", body.strip(), border_style=BRAND)
