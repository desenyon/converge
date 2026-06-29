import logging
import shutil
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from converge.audit import append_audit_event, read_audit_events
from converge.cli.explain import ExplainabilityEngine
from converge.cli.init_template import INIT_TEMPLATE
from converge.cli.jsonutil import print_json
from converge.cli.packages_report import summarize_packages
from converge.cli.repo_guard import ensure_target_directory, load_graph_or_exit
from converge.env_manager import EnvironmentManager
from converge.exit_codes import ExitCode
from converge.exporter import ExportError, GraphExporter
from converge.graph.store import GraphStore
from converge.lockfile import summarize_lockfiles
from converge.logging_config import configure_cli_logging
from converge.models import GraphEntity, GraphRelationship
from converge.project_context import ProjectContext
from converge.repair.manifest import apply_plan_to_pyproject
from converge.repair.requirements import apply_plan_to_requirements
from converge.scanner.incremental import is_tree_unchanged, load_scan_state, write_scan_state
from converge.scanner.paths import iter_python_files
from converge.scanner.scanner import Scanner
from converge.settings import load_converge_settings
from converge.solver.conflict import Conflict, ConflictDetector, ConflictType
from converge.solver.planner import RepairPlan, RepairPlanner
from converge.validation.sandbox import UVSandbox
from converge.validation.smoke import ValidationRunner
from converge.version_info import package_version

app = typer.Typer(
    help="Converge: A Python-first repository intelligence and environment convergence platform.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
log = logging.getLogger("converge.cli")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"converge {package_version()}")
        raise typer.Exit(ExitCode.SUCCESS)


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed Converge version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON on stdout"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal progress output"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose diagnostics"),
) -> None:
    """Global options apply to all subcommands."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    configure_cli_logging(verbose)


def _opts(ctx: typer.Context) -> dict[str, Any]:
    return ctx.obj if isinstance(ctx.obj, dict) else {}


def _out_console(ctx: typer.Context) -> Console:
    o = _opts(ctx)
    return Console(quiet=o.get("quiet", False))


def _print_repo_header(title: str, context: ProjectContext, ctx: typer.Context) -> None:
    o = _opts(ctx)
    if o.get("json") or o.get("quiet"):
        return
    console.print(
        Panel.fit(
            f"[bold]{title}[/bold]\n[dim]{context.root_dir}[/dim]",
            border_style="blue",
        )
    )


def _activation_command(venv_path: Path) -> str:
    if (venv_path / "Scripts" / "python.exe").exists():
        return rf"{venv_path}\Scripts\activate"
    return f"source {venv_path}/bin/activate"


def _filter_conflicts(conflicts: list[Conflict], conflict_type: str | None) -> list[Conflict]:
    if not conflict_type:
        return conflicts
    needle = conflict_type.strip().lower()
    aliases = {
        "unresolved": ConflictType.UNRESOLVED_IMPORT,
        "unused": ConflictType.UNUSED_DEPENDENCY,
        "clash": ConflictType.VERSION_CLASH,
        "version": ConflictType.VERSION_CLASH,
    }
    resolved = aliases.get(needle, needle)
    return [c for c in conflicts if c.type.lower() == resolved.lower()]


def _artifacts_to_remove(context: ProjectContext) -> list[str]:
    removed: list[str] = []
    if context.artifact_dir.exists():
        removed.append(".converge")
    sandbox_dir = context.root_dir / ".venv-converge-test"
    if sandbox_dir.exists():
        removed.append(sandbox_dir.name)
    return removed


@app.command()
def scan(  # noqa: C901
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to scan"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Perform a dry run without saving to the database"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Run a full scan even when incremental fingerprints are unchanged",
    ),
) -> None:
    """
    [bold cyan]Scan[/bold cyan] a codebase to build a graph of repositories, packages, modules, and services.
    """
    context = ProjectContext.from_target(path)
    ensure_target_directory(context, command="scan", json_mode=_opts(ctx).get("json", False))
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Scan Repository", context, ctx)

    py_files = iter_python_files(context.root_dir, settings)
    if (
        settings.incremental_scan
        and not dry_run
        and not force
        and is_tree_unchanged(context.scan_state_path, context.root_dir, py_files)
    ):
        payload = {
            "command": "scan",
            "status": "skipped_incremental",
            "repository": str(context.root_dir),
            "message": "Source tree unchanged; left existing graph in place.",
        }
        if _opts(ctx).get("json"):
            print_json(payload)
        else:
            oc.print(
                "[yellow]Incremental scan:[/yellow] tree unchanged; "
                f"skipping (existing graph at [cyan]{context.graph_db_path}[/cyan])."
            )
        raise typer.Exit(ExitCode.SUCCESS)

    scanner = Scanner(str(context.root_dir), settings=settings)

    merged: tuple[list[GraphEntity], list[GraphRelationship]] | None = None
    if settings.incremental_scan and not dry_run and context.graph_db_path.is_file():
        with GraphStore.for_context(context) as inc_store:
            merged = scanner.scan_incremental(inc_store, context.scan_state_path, py_files)

    use_progress = not _opts(ctx).get("json") and not _opts(ctx).get("quiet")

    if merged is not None:
        entities, rels = merged
        log.debug("scan used partial incremental merge")
    elif use_progress:
        with Progress(
            SpinnerColumn(spinner_name="dots2"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=False,
        ) as progress:
            task = progress.add_task("[cyan]Parsing ASTs and gathering dependencies...", total=None)
            entities, rels = scanner.scan_all()
            progress.update(task, completed=True)
    else:
        entities, rels = scanner.scan_all()

    summary_payload = {
        "command": "scan",
        "status": "completed",
        "entities": len(entities),
        "relationships": len(rels),
        "repository": str(context.root_dir),
        "dry_run": dry_run,
        "scan_mode": "incremental_partial" if merged is not None else "full",
    }

    if _opts(ctx).get("json"):
        if not dry_run:
            summary_payload["graph_path"] = str(context.graph_db_path)
        print_json(summary_payload)
    else:
        summary = Table(title="Scan Summary", box=None)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value")
        summary.add_row("Entities", str(len(entities)))
        summary.add_row("Relationships", str(len(rels)))
        summary.add_row("Repository", str(context.root_dir))
        oc.print(summary)

    if dry_run:
        if not _opts(ctx).get("json"):
            oc.print(
                f"[yellow]Dry run complete.[/yellow] Graph was not written to [cyan]{context.graph_db_path}[/cyan]."
            )
        raise typer.Exit(ExitCode.SUCCESS)

    def _persist_graph() -> None:
        with GraphStore.for_context(context) as store:
            store.reset()
            for e in entities:
                store.add_entity(e)
            for r in rels:
                store.add_relationship(r)

    if use_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task2 = progress.add_task("[cyan]Persisting Graph to Database...", total=None)
            _persist_graph()
            progress.update(task2, completed=True)
    else:
        _persist_graph()

    write_scan_state(context.scan_state_path, context.root_dir, py_files)

    if not _opts(ctx).get("json"):
        oc.print(f"[green]Graph saved[/green] to [cyan]{context.graph_db_path}[/cyan].")
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def create(  # noqa: C901
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository"),
    provider: str = typer.Option("uv", "--provider", help="Package manager to use (uv or pip)"),
    python: str = typer.Option(None, "--python", help="Python version to initialize"),
) -> None:
    """
    [bold magenta]Create[/bold magenta] a repository-local virtual environment from the graph requirements.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header(f"Create Environment ({provider})", context, ctx)

    with load_graph_or_exit(
        context, command="create", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()

    env_mgr = EnvironmentManager(context)
    packages = env_mgr.plan_packages(G)
    if not packages:
        oc.print(
            "[yellow]No required packages found in the graph. Creating empty environment.[/yellow]"
        )

    use_progress = not _opts(ctx).get("json") and not _opts(ctx).get("quiet")
    if use_progress:
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_create = progress.add_task(
                f"[cyan]Creating environment with {provider}...", total=None
            )
            try:
                env_mgr.create_venv(provider=provider, python_version=python)
                progress.update(task_create, completed=True)
                oc.print(f"[green]Created environment[/green] at [cyan]{env_mgr.venv_path}[/cyan]")
            except Exception as e:
                progress.stop()
                oc.print(f"[bold red]Environment Failure /[/bold red] {e}")
                raise typer.Exit(ExitCode.ERROR) from None

            if packages:
                task_install = progress.add_task(
                    f"[cyan]Resolving {len(packages)} dependencies...", total=None
                )
                try:
                    env_mgr.install_packages(provider, packages)
                    progress.update(task_install, completed=True)
                    oc.print(
                        f"[green]Installed[/green] {len(packages)} package(s) into [cyan]{env_mgr.venv_path}[/cyan]."
                    )
                except Exception as e:
                    progress.stop()
                    oc.print(f"[bold red]Resolution Failure /[/bold red] {e}")
                    raise typer.Exit(ExitCode.ERROR) from None
    else:
        try:
            env_mgr.create_venv(provider=provider, python_version=python)
            if packages:
                env_mgr.install_packages(provider, packages)
        except Exception as e:
            if _opts(ctx).get("json"):
                print_json({"command": "create", "error": str(e)})
            else:
                oc.print(f"[bold red]Environment Failure /[/bold red] {e}")
            raise typer.Exit(ExitCode.ERROR) from None

    result = {
        "command": "create",
        "status": "completed",
        "venv": str(env_mgr.venv_path),
        "provider": provider,
        "packages": len(packages),
    }
    if _opts(ctx).get("json"):
        print_json(result)
    else:
        oc.print(
            Panel(
                f"[bold green]Environment ready.[/bold green]\n"
                f"Path: [cyan]{env_mgr.venv_path}[/cyan]\n"
                f"Activate: [cyan]{_activation_command(env_mgr.venv_path)}[/cyan]"
            )
        )
    raise typer.Exit(ExitCode.SUCCESS)


def _run_validation(
    path: str, conflicts: list[Conflict], plans: list[RepairPlan], oc: Console
) -> RepairPlan | None:
    oc.print("\n[bold blue]Validating repair plans in an isolated sandbox...[/bold blue]")
    sandbox = UVSandbox(path)
    runner = ValidationRunner(sandbox)

    smoke_targets = []
    for c in conflicts:
        if c.type == ConflictType.UNRESOLVED_IMPORT:
            smoke_targets.append(c.involved_entities[1].replace("pkg:", ""))

    with Progress(
        SpinnerColumn("bouncingBar"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Validating {len(plans)} candidate plan(s)...", total=None)
        scores = runner.score_plans(plans, smoke_targets)
        progress.update(task, completed=True)

    best_plan = None
    for plan_id, success in scores.items():
        if success:
            best_plan = next(p for p in plans if p.id == plan_id)
            break

    if best_plan:
        oc.print(
            Panel(
                f"[bold green]Validation passed.[/bold green]\n"
                f"Selected plan: [cyan]{best_plan.id}[/cyan]\n"
                "[dim]This plan satisfied the configured smoke-import checks.[/dim]",
                title="Validation Result",
                border_style="green",
            )
        )
        return best_plan
    oc.print(
        Panel(
            "[bold red]Validation failed for every candidate plan.[/bold red]",
            border_style="red",
        )
    )
    return None


@app.command()
def fix(  # noqa: C901
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to fix"),
    apply: bool = typer.Option(False, "--apply", help="Apply the fix plan after validation"),
) -> None:
    """
    [bold red]Repair[/bold red] conflicts by generating plans and validating them in isolated sandboxes.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Repair Dependency Issues", context, ctx)

    with load_graph_or_exit(
        context, command="fix", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()

    detector = ConflictDetector(G, settings=settings)
    conflicts = list(detector.detect_all())

    if not conflicts:
        payload = {"command": "fix", "status": "clean", "conflicts": 0}
        if _opts(ctx).get("json"):
            print_json(payload)
        else:
            oc.print(
                Panel(
                    "[bold green]No dependency issues detected.[/bold green]",
                    border_style="green",
                )
            )
        raise typer.Exit(ExitCode.SUCCESS)

    planner = RepairPlanner(conflicts)
    plans = planner.generate_plans()

    if _opts(ctx).get("json"):
        print_json(
            {
                "command": "fix",
                "status": "dry_run",
                "apply": apply,
                "conflict_count": len(conflicts),
                "conflicts": [c.model_dump() for c in conflicts],
                "plans": [p.model_dump() for p in plans],
            }
        )
    else:
        oc.print(f"[yellow]Found {len(conflicts)} issue(s) that may require changes.[/yellow]")
        for plan in plans:
            table = Table(
                title=f"Plan Specification: {plan.id}", title_justify="left", border_style="cyan"
            )
            table.add_column("Action", style="magenta")
            table.add_column("Target", style="green")
            table.add_column("Rationale")
            for action in plan.actions:
                table.add_row(action.action_type, action.target_package, action.description)
            oc.print(table)

    if not apply:
        if not _opts(ctx).get("json"):
            oc.print(
                "\n[yellow]Dry run only.[/yellow] No files were changed. Re-run with [cyan]--apply[/cyan] to validate and write the selected plan."
            )
        raise typer.Exit(ExitCode.ISSUES_FOUND)

    best_plan = _run_validation(
        path, conflicts, plans, oc if not _opts(ctx).get("quiet") else console
    )
    if best_plan is None:
        raise typer.Exit(ExitCode.ERROR) from None

    pyproject_path = context.root_dir / "pyproject.toml"
    applied: dict[str, str | None] = {}

    if "pyproject" in settings.repair_targets and pyproject_path.exists():
        apply_plan_to_pyproject(pyproject_path, best_plan)
        applied["pyproject"] = str(pyproject_path)
    elif "pyproject" in settings.repair_targets:
        applied["pyproject"] = None

    if "requirements" in settings.repair_targets:
        req_path = apply_plan_to_requirements(
            context.root_dir, best_plan, settings.requirements_file
        )
        applied["requirements"] = str(req_path) if req_path else None

    append_audit_event(
        context,
        {
            "event": "fix_apply",
            "plan_id": best_plan.id,
            "applied": applied,
        },
    )

    if not _opts(ctx).get("json"):
        oc.print(
            f"[green]Applied validated changes[/green] (see [cyan]{context.audit_log_path}[/cyan])."
        )
    else:
        print_json(
            {
                "command": "fix",
                "status": "applied",
                "plan": best_plan.model_dump(),
                "applied": applied,
            }
        )
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def doctor(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
    conflict_type: str | None = typer.Option(
        None,
        "--type",
        help="Filter issues by type (unresolved_import, unused_dependency, version_clash)",
    ),
) -> None:
    """
    [bold yellow]Diagnose[/bold yellow] structural anomalies across the AST dependency mappings.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Doctor", context, ctx)

    with load_graph_or_exit(
        context, command="doctor", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()

    detector = ConflictDetector(G, settings=settings)
    conflicts = _filter_conflicts(list(detector.detect_all()), conflict_type)
    lock_hints = summarize_lockfiles(context.root_dir)

    if _opts(ctx).get("json"):
        print_json(
            {
                "command": "doctor",
                "status": "clean" if not conflicts else "issues",
                "conflict_count": len(conflicts),
                "filter_type": conflict_type,
                "repository": str(context.root_dir),
                "conflicts": [c.model_dump() for c in conflicts],
                "lockfiles": lock_hints,
            }
        )
        raise typer.Exit(ExitCode.SUCCESS if not conflicts else ExitCode.ISSUES_FOUND)

    if not conflicts:
        oc.print(
            Panel(
                "[bold green]No dependency issues found.[/bold green]\nThe scanned graph is internally consistent for the current checks.",
                border_style="green",
            )
        )
        raise typer.Exit(ExitCode.SUCCESS)

    oc.print(f"\n[bold red]Detected {len(conflicts)} issue(s).[/bold red]")

    table = Table(show_header=True, header_style="bold magenta", border_style="red")
    table.add_column("Conflict ID", style="cyan")
    table.add_column("Classification", style="red")
    table.add_column("Description")

    for c in conflicts:
        table.add_row(c.id, c.type.upper(), c.description)

    oc.print(table)
    lockfiles = lock_hints.get("lockfiles", [])
    if isinstance(lockfiles, list) and lockfiles:
        oc.print(
            f"\n[dim]Lockfiles detected: {len(lockfiles)} "
            f"({', '.join(str(item.get('path', '')) for item in lockfiles if isinstance(item, dict))}).[/dim]"
        )
    oc.print(
        f"\n[dim]Next: run `converge explain <CONFLICT_ID> {context.root_dir}` for a detailed explanation.[/dim]"
    )
    raise typer.Exit(ExitCode.ISSUES_FOUND)


@app.command()
def check(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to scan and diagnose"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force a full scan even when incremental fingerprints are unchanged",
    ),
    conflict_type: str | None = typer.Option(
        None,
        "--type",
        help="When diagnosing, filter issues by conflict type",
    ),
) -> None:
    """
    [bold cyan]Check[/bold cyan] a repository by scanning the graph and running doctor in one step.
    """
    try:
        ctx.invoke(scan, ctx=ctx, path=path, dry_run=False, force=force)
    except typer.Exit as exc:
        if exc.exit_code != int(ExitCode.SUCCESS):
            raise typer.Exit(exc.exit_code) from None

    try:
        ctx.invoke(doctor, ctx=ctx, path=path, conflict_type=conflict_type)
    except typer.Exit as exc:
        raise typer.Exit(exc.exit_code) from None


@app.command()
def packages(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
) -> None:
    """
    List declared, imported, missing, and unused packages from the scanned graph.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Packages", context, ctx)

    with load_graph_or_exit(
        context, command="packages", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()

    summary = summarize_packages(G, settings=settings)
    payload = {"command": "packages", "repository": str(context.root_dir), **summary}
    exit_code = ExitCode.SUCCESS if not summary["missing_count"] else ExitCode.ISSUES_FOUND

    if _opts(ctx).get("json"):
        print_json(payload)
        raise typer.Exit(exit_code)

    table = Table(title="Package Inventory", box=None)
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Packages")
    table.add_row("Declared", str(summary["declared_count"]), ", ".join(summary["declared"]) or "—")
    table.add_row("Imported", str(summary["imported_count"]), ", ".join(summary["imported"]) or "—")
    table.add_row(
        "Missing",
        str(summary["missing_count"]),
        ", ".join(summary["missing"]) or "—",
    )
    table.add_row(
        "Unused",
        str(summary["unused_count"]),
        ", ".join(summary["unused"]) or "—",
    )
    oc.print(table)
    raise typer.Exit(exit_code)


@app.command()
def audit(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
    limit: int = typer.Option(20, "--limit", help="Maximum audit events to show (0 = all)"),
) -> None:
    """
    Show the repair audit log written by ``converge fix --apply``.
    """
    context = ProjectContext.from_target(path)
    ensure_target_directory(context, command="audit", json_mode=_opts(ctx).get("json", False))
    oc = _out_console(ctx)
    _print_repo_header("Audit Log", context, ctx)

    cap = None if limit == 0 else limit
    events = read_audit_events(context, limit=cap)
    payload = {
        "command": "audit",
        "repository": str(context.root_dir),
        "path": str(context.audit_log_path),
        "event_count": len(events),
        "events": events,
    }

    if _opts(ctx).get("json"):
        print_json(payload)
        raise typer.Exit(ExitCode.SUCCESS)

    if not events:
        oc.print(
            Panel(
                "[yellow]No audit events recorded yet.[/yellow]\n"
                "Run [cyan]converge fix . --apply[/cyan] after a successful validation.",
                border_style="yellow",
            )
        )
        raise typer.Exit(ExitCode.SUCCESS)

    table = Table(title=f"Audit Events ({len(events)})", show_header=True, header_style="bold")
    table.add_column("Timestamp", style="dim")
    table.add_column("Event", style="cyan")
    table.add_column("Details")
    for event in events:
        table.add_row(
            str(event.get("ts", "")),
            str(event.get("event", "")),
            str(event.get("plan_id") or event.get("applied") or ""),
        )
    oc.print(table)
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def init(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to initialize"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing .converge.toml"),
) -> None:
    """
    Scaffold a repository-local ``.converge.toml`` configuration file.
    """
    context = ProjectContext.from_target(path)
    ensure_target_directory(context, command="init", json_mode=_opts(ctx).get("json", False))
    oc = _out_console(ctx)
    _print_repo_header("Init", context, ctx)

    config_path = context.root_dir / ".converge.toml"
    if config_path.exists() and not force:
        message = f".converge.toml already exists at {config_path}. Use --force to overwrite."
        if _opts(ctx).get("json"):
            print_json({"command": "init", "status": "exists", "path": str(config_path)})
        else:
            oc.print(f"[yellow]{message}[/yellow]")
        raise typer.Exit(ExitCode.ERROR)

    config_path.write_text(INIT_TEMPLATE, encoding="utf-8")
    payload = {"command": "init", "status": "created", "path": str(config_path)}
    if _opts(ctx).get("json"):
        print_json(payload)
    else:
        oc.print(f"[green]Created[/green] [cyan]{config_path}[/cyan]")
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def status(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
) -> None:
    """
    Show Converge artifact state for a repository (graph, scan fingerprints, lockfiles).
    """
    context = ProjectContext.from_target(path)
    ensure_target_directory(context, command="status", json_mode=_opts(ctx).get("json", False))
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Status", context, ctx)

    py_files = iter_python_files(context.root_dir, settings)
    scan_state = load_scan_state(context.scan_state_path)
    tree_unchanged = (
        settings.incremental_scan
        and bool(scan_state)
        and is_tree_unchanged(context.scan_state_path, context.root_dir, py_files)
    )

    entity_count = 0
    relationship_count = 0
    graph_present = context.graph_db_path.is_file()
    if graph_present:
        with GraphStore.for_context(context, create_dirs=False) as store:
            entity_count = len(store.list_entities())
            relationship_count = len(store.list_relationships())

    lock_hints = summarize_lockfiles(context.root_dir)
    graph_ready = graph_present and entity_count > 0
    payload = {
        "command": "status",
        "repository": str(context.root_dir),
        "graph": {
            "path": str(context.graph_db_path),
            "present": graph_ready,
            "entities": entity_count,
            "relationships": relationship_count,
        },
        "scan_state": {
            "path": str(context.scan_state_path),
            "tracked_files": len(scan_state),
            "tree_unchanged": tree_unchanged,
            "incremental_scan_enabled": settings.incremental_scan,
        },
        "lockfiles": lock_hints,
    }

    if _opts(ctx).get("json"):
        print_json(payload)
        raise typer.Exit(ExitCode.SUCCESS)

    table = Table(title="Repository Status", box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Graph", "present" if graph_ready else "missing")
    table.add_row("Entities", str(entity_count))
    table.add_row("Relationships", str(relationship_count))
    table.add_row("Tracked source files", str(len(scan_state)))
    table.add_row(
        "Incremental scan",
        "enabled" if settings.incremental_scan else "disabled",
    )
    table.add_row(
        "Tree unchanged since last scan",
        "yes" if tree_unchanged else "no",
    )
    lockfiles = lock_hints.get("lockfiles", [])
    lockfile_count = len(lockfiles) if isinstance(lockfiles, list) else 0
    table.add_row("Lockfiles", str(lockfile_count))
    oc.print(table)
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def explain(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Entity or conflict ID to explain"),
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
) -> None:
    """
    [bold green]Explain[/bold green] graph geometry or debug explicit constraint violations.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header("Explain", context, ctx)
    with load_graph_or_exit(
        context, command="explain", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()

    engine = ExplainabilityEngine(G, oc)
    if _opts(ctx).get("json"):
        detail = engine.explain_as_dict(target)
        print_json(
            {"command": "explain", "target": target, "repository": str(context.root_dir), **detail}
        )
        raise typer.Exit(ExitCode.SUCCESS)

    if "conflict:" in target:
        engine.explain_conflict(target)
    else:
        engine.render_dependency_tree(target)
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def export(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to export"),
    format: str = typer.Option("json", "--format", help="Export format (json|csv)"),
) -> None:
    """
    Export structural datasets for auditing.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header("Export", context, ctx)
    with load_graph_or_exit(
        context, command="export", json_mode=_opts(ctx).get("json", False), console=oc
    ) as store:
        G = store.load_networkx()
    try:
        exporter = GraphExporter(context)
        output_paths = exporter.export(G, format)
    except ExportError as e:
        if _opts(ctx).get("json"):
            print_json({"command": "export", "error": str(e)})
        else:
            oc.print(f"[red]{e}[/red]")
        raise typer.Exit(ExitCode.ERROR) from None

    payload = {
        "command": "export",
        "format": format,
        "artifacts": [str(p) for p in output_paths],
    }
    if _opts(ctx).get("json"):
        print_json(payload)
    else:
        oc.print(
            Panel(
                f"[bold green]Export complete.[/bold green]\n"
                f"Format: [cyan]{format}[/cyan]\n"
                f"Artifacts: [cyan]{', '.join(str(output_path) for output_path in output_paths)}[/cyan]",
                title="Export Result",
                border_style="green",
            )
        )
    raise typer.Exit(ExitCode.SUCCESS)


@app.command()
def clean(
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to clean"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be removed without deleting anything"
    ),
) -> None:
    """
    Remove Converge database state and cached validation sandboxes.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header("Clean", context, ctx)
    candidates = _artifacts_to_remove(context)

    if dry_run:
        payload = {
            "command": "clean",
            "status": "dry_run",
            "would_remove": [str(context.root_dir / name) for name in candidates],
        }
        if _opts(ctx).get("json"):
            print_json(payload)
        elif candidates:
            oc.print(
                "[yellow]Dry run:[/yellow] would remove "
                f"{', '.join(candidates)} from [cyan]{context.root_dir}[/cyan]."
            )
        else:
            oc.print("[yellow]Nothing to remove.[/yellow]")
        raise typer.Exit(ExitCode.SUCCESS)

    removed: list[str] = []
    if context.artifact_dir.exists():
        shutil.rmtree(context.artifact_dir)
        removed.append(".converge")

    sandbox_dir = context.root_dir / ".venv-converge-test"
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
        removed.append(sandbox_dir.name)

    if _opts(ctx).get("json"):
        print_json(
            {
                "command": "clean",
                "status": "completed",
                "removed": [str(context.root_dir / r) for r in removed],
            }
        )
    elif removed:
        oc.print(
            f"[green]Removed[/green] {', '.join(removed)} from [cyan]{context.root_dir}[/cyan]."
        )
    else:
        oc.print("[yellow]Nothing to remove.[/yellow]")
    raise typer.Exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    app()
