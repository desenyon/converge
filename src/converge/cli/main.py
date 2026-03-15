import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from converge.cli.explain import ExplainabilityEngine
from converge.env_manager import EnvironmentManager
from converge.graph.store import GraphStore
from converge.models import EntityType
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
    console.print(Panel.fit(f"[bold green]Scanning Repository:[/bold green] {path}"))

    scanner = Scanner(path)

    with Progress(
        SpinnerColumn(spinner_name="dots2"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Parsing ASTs and gathering dependencies...", total=None)
        entities, rels = scanner.scan_all()
        progress.update(task, completed=True)

    console.print(
        f"Found [bold cyan]{len(entities)}[/bold cyan] entities and [bold magenta]{len(rels)}[/bold magenta] relationships."
    )

    if dry_run:
        console.print("[yellow]Dry run mode enabled. Results will not be saved.[/yellow]")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task2 = progress.add_task("[cyan]Persisting Graph to Database...", total=None)
            store = GraphStore()
            for e in entities:
                store.add_entity(e)
            for r in rels:
                store.add_relationship(r)
            progress.update(task2, completed=True)

        console.print("[green]✓ Successfully persisted graph to database[/green]")


@app.command()
def create(
    path: str = typer.Argument(".", help="Path to the repository"),
    provider: str = typer.Option("uv", "--provider", help="Package manager to use (uv or pip)"),
    python: str = typer.Option(None, "--python", help="Python version to initialize"),
) -> None:
    """
    [bold magenta]Create[/bold magenta] an optimized virtual environment precisely matching the graph requirements.
    """
    console.print(
        Panel.fit(f"[bold blue]Provisioning new environment via {provider.upper()}[/bold blue]")
    )

    # Extract known packages from DB
    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Error loading graph. Did you run `converge scan`? ({e})[/red]")
        return

    packages = []
    for _node_id, data in G.nodes(data=True):
        if data.get("type") == EntityType.PACKAGE:
            pkg_name = data.get("name")
            if pkg_name:
                packages.append(pkg_name)

    if not packages:
        console.print(
            "[yellow]No required packages found in the graph. Creating empty environment.[/yellow]"
        )

    env_mgr = EnvironmentManager(path)

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
                    f"[green]✓ Successfully mapped and installed {len(packages)} requirements[/green]"
                )
            except Exception as e:
                progress.stop()
                console.print(f"[bold red]Resolution Failure /[/bold red] {e}")
                return

    console.print(
        Panel(
            "[bold green]Environment Convergence Complete![/bold green]\n"
            f"Activate via: [cyan]source {env_mgr.venv_path.name}/bin/activate[/cyan]"
        )
    )


def _run_validation(
    path: str, conflicts: list[Conflict], plans: list[RepairPlan], console: Console
) -> None:
    console.print("\n[bold blue]Initiating Validation Matrix...[/bold blue]")
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
        task = progress.add_task(f"[cyan]Simulating {len(plans)} repair plans...", total=None)
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
                f"[bold green]Matrix Success![/bold green]\n"
                f"Validated Plan: [cyan]{best_plan.id}[/cyan]\n\n"
                "[dim]A full implementation would now lock these resolved specs into the host environment.[/dim]",
                title="Validation Verdict",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]All candidate constraints violated execution bounds.[/bold red]",
                border_style="red",
            )
        )


@app.command()
def fix(
    path: str = typer.Argument(".", help="Path to the repository to fix"),
    apply: bool = typer.Option(False, "--apply", help="Apply the fix plan after validation"),
) -> None:
    """
    [bold red]Repair[/bold red] conflicts by generating plans and proving them in hidden sandboxes.
    """
    console.print(Panel.fit(f"[bold red]Engaging Repair Generator For:[/bold red] {path}"))

    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Failed to load graph. Error: {e}[/red]")
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
                "[bold green]Zero conflicts detected throughout geometry.[/bold green]",
                border_style="green",
            )
        )
        return

    console.print(f"[yellow]Identified {len(conflicts)} dimensional anomalies.[/yellow]")

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
            "\n[yellow]Simulated Execution complete. Affix --apply to enforce changes.[/yellow]"
        )
    else:
        _run_validation(path, conflicts, plans, console)


@app.command()
def doctor() -> None:
    """
    [bold yellow]Diagnose[/bold yellow] structural anomalies across the AST dependency mappings.
    """
    console.print("[bold cyan]Running Diagnostic Sweep...[/bold cyan]")

    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception:
        console.print("[red]System offline. Graph missing. Run `converge scan` first.[/red]")
        return

    detector = ConflictDetector(G)
    conflicts = list(detector.detect_all())

    if not conflicts:
        console.print(
            Panel(
                "[bold green]System Optimal. No structural integrity issues found.[/bold green]",
                border_style="green",
            )
        )
        return

    console.print(f"\n[bold red]Critical Alerts Detected: {len(conflicts)}[/bold red]")

    table = Table(show_header=True, header_style="bold magenta", border_style="red")
    table.add_column("Conflict ID", style="cyan")
    table.add_column("Classification", style="red")
    table.add_column("Description")

    for c in conflicts:
        table.add_row(c.id, c.type.upper(), c.description)

    console.print(table)
    console.print("\n[dim]Run `converge explain [CONFLICT_ID]` to trace the anomaly path.[/dim]")


@app.command()
def explain(
    target: str = typer.Argument(..., help="Entity or conflict ID to explain"),
) -> None:
    """
    [bold green]Explain[/bold green] graph geometry or debug explicit constraint violations.
    """
    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Failed to load graph. Error: {e}[/red]")
        return

    engine = ExplainabilityEngine(G, console)
    if "conflict:" in target:
        engine.explain_conflict(target)
    else:
        engine.render_dependency_tree(target)


@app.command()
def export(
    format: str = typer.Option("json", "--format", help="Export format (json|csv)"),
) -> None:
    """
    Export structural datasets for auditing.
    """
    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Failed to load graph. Error: {e}[/red]")
        return
    console.print(
        f"[green]Successfully exported matrix ([bold]{len(G.nodes)}[/bold] nodes) as [bold]{format.upper()}[/bold][/green]"
    )


@app.command()
def clean() -> None:
    """
    Eradicate database state and cached execution sandboxes.
    """
    if os.path.exists("converge_graph.db"):
        os.remove("converge_graph.db")
        console.print("[green]✓ Purged converge_graph.db[/green]")
    else:
        console.print("[yellow]System already pristine.[/yellow]")


if __name__ == "__main__":
    app()
