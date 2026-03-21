import logging
import shutil
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from converge.audit import append_audit_event
from converge.cli.explain import ExplainabilityEngine
from converge.cli.jsonutil import print_json
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
from converge.scanner.incremental import is_tree_unchanged, write_scan_state
from converge.scanner.paths import iter_python_files
from converge.scanner.scanner import Scanner
from converge.settings import load_converge_settings
from converge.solver.conflict import Conflict, ConflictDetector, ConflictType
from converge.solver.planner import RepairPlan, RepairPlanner
from converge.validation.sandbox import UVSandbox
from converge.validation.smoke import ValidationRunner

app = typer.Typer(
    help="Converge: A Python-first repository intelligence and environment convergence platform.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
log = logging.getLogger("converge.cli")


@app.callback()
def main(
    ctx: typer.Context,
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


@app.command()
def scan(  # noqa: C901
    ctx: typer.Context,
    path: str = typer.Argument(".", help="Path to the repository to scan"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Perform a dry run without saving to the database"
    ),
) -> None:
    """
    [bold cyan]Scan[/bold cyan] a codebase to build a graph of repositories, packages, modules, and services.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Scan Repository", context, ctx)

    py_files = iter_python_files(context.root_dir, settings)
    if (
        settings.incremental_scan
        and not dry_run
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
    [bold magenta]Create[/bold magenta] an optimized virtual environment precisely matching the graph requirements.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header(f"Create Environment ({provider})", context, ctx)

    try:
        with GraphStore.for_context(context) as store:
            G = store.load_networkx()
    except Exception as e:
        if _opts(ctx).get("json"):
            print_json({"command": "create", "error": str(e), "status": "no_graph"})
        else:
            oc.print(
                f"[red]Cannot create an environment without a graph.[/red] Run `converge scan {context.root_dir}` first. ({e})"
            )
        raise typer.Exit(ExitCode.ERROR) from None

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
                f"[cyan]Initializing Sandbox with {provider}...", total=None
            )
            try:
                env_mgr.create_venv(provider=provider, python_version=python)
                progress.update(task_create, completed=True)
                oc.print(f"[green]Created Sandbox at {env_mgr.venv_path}[/green]")
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
    [bold red]Repair[/bold red] conflicts by generating plans and proving them in hidden sandboxes.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Repair Dependency Issues", context, ctx)

    try:
        with GraphStore.for_context(context) as store:
            G = store.load_networkx()
    except Exception as e:
        if _opts(ctx).get("json"):
            print_json({"command": "fix", "error": str(e), "status": "no_graph"})
        else:
            oc.print(
                f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})"
            )
        raise typer.Exit(ExitCode.ERROR) from None

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
                "apply": apply,
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
) -> None:
    """
    [bold yellow]Diagnose[/bold yellow] structural anomalies across the AST dependency mappings.
    """
    context = ProjectContext.from_target(path)
    settings = load_converge_settings(context.root_dir)
    oc = _out_console(ctx)
    _print_repo_header("Doctor", context, ctx)

    try:
        with GraphStore.for_context(context) as store:
            G = store.load_networkx()
    except Exception:
        if _opts(ctx).get("json"):
            print_json(
                {"command": "doctor", "status": "no_graph", "repository": str(context.root_dir)}
            )
        else:
            oc.print(
                f"[red]No graph found for [cyan]{context.root_dir}[/cyan].[/red] Run `converge scan {context.root_dir}` first."
            )
        raise typer.Exit(ExitCode.ERROR) from None

    detector = ConflictDetector(G, settings=settings)
    conflicts = list(detector.detect_all())
    lock_hints = summarize_lockfiles(context.root_dir)

    if _opts(ctx).get("json"):
        print_json(
            {
                "command": "doctor",
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
    oc.print(
        f"\n[dim]Next: run `converge explain <CONFLICT_ID> {context.root_dir}` for a detailed explanation.[/dim]"
    )
    raise typer.Exit(ExitCode.ISSUES_FOUND)


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
    try:
        with GraphStore.for_context(context) as store:
            G = store.load_networkx()
    except Exception as e:
        if _opts(ctx).get("json"):
            print_json({"command": "explain", "error": str(e)})
        else:
            oc.print(
                f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})"
            )
        raise typer.Exit(ExitCode.ERROR) from None

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
    try:
        with GraphStore.for_context(context) as store:
            G = store.load_networkx()
    except Exception as e:
        if _opts(ctx).get("json"):
            print_json({"command": "export", "error": str(e)})
        else:
            oc.print(
                f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})"
            )
        raise typer.Exit(ExitCode.ERROR) from None
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
) -> None:
    """
    Eradicate database state and cached execution sandboxes.
    """
    context = ProjectContext.from_target(path)
    oc = _out_console(ctx)
    _print_repo_header("Clean", context, ctx)
    removed = []

    if context.export_dir.exists():
        shutil.rmtree(context.export_dir)
        removed.append(context.export_dir.name)

    if context.graph_db_path.exists():
        context.graph_db_path.unlink()
        removed.append(context.graph_db_path.name)

    if context.scan_state_path.exists():
        context.scan_state_path.unlink()
        removed.append(context.scan_state_path.name)

    if context.audit_log_path.exists():
        context.audit_log_path.unlink()
        removed.append(context.audit_log_path.name)

    if context.artifact_dir.exists() and not any(context.artifact_dir.iterdir()):
        context.artifact_dir.rmdir()

    sandbox_dir = context.root_dir / ".venv-converge-test"
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
        removed.append(sandbox_dir.name)

    if _opts(ctx).get("json"):
        print_json({"command": "clean", "removed": [str(context.root_dir / r) for r in removed]})
    elif removed:
        oc.print(
            f"[green]Removed[/green] {', '.join(removed)} from [cyan]{context.root_dir}[/cyan]."
        )
    else:
        oc.print("[yellow]Nothing to remove.[/yellow]")
    raise typer.Exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    app()
