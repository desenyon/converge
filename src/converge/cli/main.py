import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from converge.cli.explain import ExplainabilityEngine
from converge.env_manager import EnvironmentManager
from converge.exporter import ExportError, GraphExporter
from converge.graph.store import GraphStore
from converge.project_context import ProjectContext
from converge.repair.manifest import apply_plan_to_pyproject
from converge.scanner.scanner import Scanner
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


def _print_repo_header(title: str, context: ProjectContext) -> None:
    console.print(
        Panel.fit(
            f"[bold]{title}[/bold]\n[dim]{context.root_dir}[/dim]",
            border_style="blue",
        )
    )


def _activation_command(venv_path: Path) -> str:
    return f"source {venv_path}/bin/activate"


@app.command()
def scan(
    path: str = typer.Argument(".", help="Path to the repository to scan"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Perform a dry run without saving to the database"
    ),
) -> None:
    """
    [bold cyan]Scan[/bold cyan] a codebase to build a graph of repositories, packages, modules, and services.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Scan Repository", context)

    scanner = Scanner(str(context.root_dir))

    with Progress(
        SpinnerColumn(spinner_name="dots2"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Parsing ASTs and gathering dependencies...", total=None)
        entities, rels = scanner.scan_all()
        progress.update(task, completed=True)

    summary = Table(title="Scan Summary", box=None)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value")
    summary.add_row("Entities", str(len(entities)))
    summary.add_row("Relationships", str(len(rels)))
    summary.add_row("Repository", str(context.root_dir))
    console.print(summary)

    if dry_run:
        console.print(
            f"[yellow]Dry run complete.[/yellow] Graph was not written to [cyan]{context.graph_db_path}[/cyan]."
        )
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task2 = progress.add_task("[cyan]Persisting Graph to Database...", total=None)
            store = GraphStore.for_context(context)
            store.reset()
            for e in entities:
                store.add_entity(e)
            for r in rels:
                store.add_relationship(r)
            progress.update(task2, completed=True)

        console.print(f"[green]✓ Graph saved[/green] to [cyan]{context.graph_db_path}[/cyan].")


@app.command()
def create(
    path: str = typer.Argument(".", help="Path to the repository"),
    provider: str = typer.Option("uv", "--provider", help="Package manager to use (uv or pip)"),
    python: str = typer.Option(None, "--python", help="Python version to initialize"),
) -> None:
    """
    [bold magenta]Create[/bold magenta] an optimized virtual environment precisely matching the graph requirements.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header(f"Create Environment ({provider})", context)

    # Extract known packages from DB
    store = GraphStore.for_context(context)
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(
            f"[red]Cannot create an environment without a graph.[/red] Run `converge scan {context.root_dir}` first. ({e})"
        )
        return

    env_mgr = EnvironmentManager(context)
    packages = env_mgr.plan_packages(G)
    if not packages:
        console.print(
            "[yellow]No required packages found in the graph. Creating empty environment.[/yellow]"
        )

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
            console.print(f"[green]✓ Created Sandbox at {env_mgr.venv_path}[/green]")
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]Environment Failure /[/bold red] {e}")
            return

        if packages:
            task_install = progress.add_task(
                f"[cyan]Resolving {len(packages)} dependencies...", total=None
            )
            try:
                env_mgr.install_packages(provider, packages)
                progress.update(task_install, completed=True)
                console.print(
                    f"[green]✓ Installed[/green] {len(packages)} package(s) into [cyan]{env_mgr.venv_path}[/cyan]."
                )
            except Exception as e:
                progress.stop()
                console.print(f"[bold red]Resolution Failure /[/bold red] {e}")
                return

    console.print(
        Panel(
            f"[bold green]Environment ready.[/bold green]\n"
            f"Path: [cyan]{env_mgr.venv_path}[/cyan]\n"
            f"Activate: [cyan]{_activation_command(env_mgr.venv_path)}[/cyan]"
        )
    )


def _run_validation(
    path: str, conflicts: list[Conflict], plans: list[RepairPlan], console: Console
) -> RepairPlan | None:
    console.print("\n[bold blue]Validating repair plans in an isolated sandbox...[/bold blue]")
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
        console.print(
            Panel(
                f"[bold green]Validation passed.[/bold green]\n"
                f"Selected plan: [cyan]{best_plan.id}[/cyan]\n"
                "[dim]This plan satisfied the configured smoke-import checks.[/dim]",
                title="Validation Result",
                border_style="green",
            )
        )
        return best_plan
    else:
        console.print(
            Panel(
                "[bold red]Validation failed for every candidate plan.[/bold red]",
                border_style="red",
            )
        )
        return None


@app.command()
def fix(
    path: str = typer.Argument(".", help="Path to the repository to fix"),
    apply: bool = typer.Option(False, "--apply", help="Apply the fix plan after validation"),
) -> None:
    """
    [bold red]Repair[/bold red] conflicts by generating plans and proving them in hidden sandboxes.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Repair Dependency Issues", context)

    store = GraphStore.for_context(context)
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})")
        return

    with Progress(
        SpinnerColumn(), TextColumn("[cyan]Detecting logical conflicts..."), console=console
    ) as progress:
        progress.add_task("", total=None)
        detector = ConflictDetector(G)
        conflicts = list(detector.detect_all())
        progress.stop()

    if not conflicts:
        console.print(
            Panel(
                "[bold green]No dependency issues detected.[/bold green]",
                border_style="green",
            )
        )
        return

    console.print(f"[yellow]Found {len(conflicts)} issue(s) that may require changes.[/yellow]")

    with Progress(
        SpinnerColumn(), TextColumn("[cyan]Synthesizing repair algorithms..."), console=console
    ) as progress:
        progress.add_task("", total=None)
        planner = RepairPlanner(conflicts)
        plans = planner.generate_plans()
        progress.stop()

    for plan in plans:
        table = Table(
            title=f"Plan Specification: {plan.id}", title_justify="left", border_style="cyan"
        )
        table.add_column("Action", style="magenta")
        table.add_column("Target", style="green")
        table.add_column("Rationale")

        for action in plan.actions:
            table.add_row(action.action_type, action.target_package, action.description)
        console.print(table)

    if not apply:
        console.print(
            "\n[yellow]Dry run only.[/yellow] No files were changed. Re-run with [cyan]--apply[/cyan] to validate and write the selected plan."
        )
    else:
        best_plan = _run_validation(path, conflicts, plans, console)
        if best_plan is None:
            return

        pyproject_path = context.root_dir / "pyproject.toml"
        if not pyproject_path.exists():
            console.print("[red]Cannot apply fix: pyproject.toml not found.[/red]")
            return

        apply_plan_to_pyproject(pyproject_path, best_plan)
        console.print(
            f"[green]✓ Applied validated changes[/green] to [cyan]{pyproject_path}[/cyan]."
        )


@app.command()
def doctor(path: str = typer.Argument(".", help="Path to the repository to inspect")) -> None:
    """
    [bold yellow]Diagnose[/bold yellow] structural anomalies across the AST dependency mappings.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Doctor", context)

    store = GraphStore.for_context(context)
    try:
        G = store.load_networkx()
    except Exception:
        console.print(
            f"[red]No graph found for [cyan]{context.root_dir}[/cyan].[/red] Run `converge scan {context.root_dir}` first."
        )
        return

    detector = ConflictDetector(G)
    conflicts = list(detector.detect_all())

    if not conflicts:
        console.print(
            Panel(
                "[bold green]No dependency issues found.[/bold green]\nThe scanned graph is internally consistent for the current checks.",
                border_style="green",
            )
        )
        return

    console.print(f"\n[bold red]Detected {len(conflicts)} issue(s).[/bold red]")

    table = Table(show_header=True, header_style="bold magenta", border_style="red")
    table.add_column("Conflict ID", style="cyan")
    table.add_column("Classification", style="red")
    table.add_column("Description")

    for c in conflicts:
        table.add_row(c.id, c.type.upper(), c.description)

    console.print(table)
    console.print(
        f"\n[dim]Next: run `converge explain <CONFLICT_ID> {context.root_dir}` for a detailed explanation.[/dim]"
    )


@app.command()
def explain(
    target: str = typer.Argument(..., help="Entity or conflict ID to explain"),
    path: str = typer.Argument(".", help="Path to the repository to inspect"),
) -> None:
    """
    [bold green]Explain[/bold green] graph geometry or debug explicit constraint violations.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Explain", context)
    store = GraphStore.for_context(context)
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})")
        return

    engine = ExplainabilityEngine(G, console)
    if "conflict:" in target:
        engine.explain_conflict(target)
    else:
        engine.render_dependency_tree(target)


@app.command()
def export(
    path: str = typer.Argument(".", help="Path to the repository to export"),
    format: str = typer.Option("json", "--format", help="Export format (json|csv)"),
) -> None:
    """
    Export structural datasets for auditing.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Export", context)
    store = GraphStore.for_context(context)
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]No graph found for this repository.[/red] Run `converge scan` first. ({e})")
        return
    try:
        exporter = GraphExporter(context)
        output_paths = exporter.export(G, format)
    except ExportError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from e

    console.print(
        Panel(
            f"[bold green]Export complete.[/bold green]\n"
            f"Format: [cyan]{format}[/cyan]\n"
            f"Artifacts: [cyan]{', '.join(str(output_path) for output_path in output_paths)}[/cyan]",
            title="Export Result",
            border_style="green",
        )
    )


@app.command()
def clean(path: str = typer.Argument(".", help="Path to the repository to clean")) -> None:
    """
    Eradicate database state and cached execution sandboxes.
    """
    context = ProjectContext.from_target(path)
    _print_repo_header("Clean", context)
    removed = []

    if context.export_dir.exists():
        shutil.rmtree(context.export_dir)
        removed.append(context.export_dir.name)

    if context.graph_db_path.exists():
        context.graph_db_path.unlink()
        removed.append(context.graph_db_path.name)

    if context.artifact_dir.exists() and not any(context.artifact_dir.iterdir()):
        context.artifact_dir.rmdir()

    sandbox_dir = context.root_dir / ".venv-converge-test"
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
        removed.append(sandbox_dir.name)

    if removed:
        console.print(
            f"[green]✓ Removed[/green] {', '.join(removed)} from [cyan]{context.root_dir}[/cyan]."
        )
    else:
        console.print("[yellow]Nothing to remove.[/yellow]")


if __name__ == "__main__":
    app()
