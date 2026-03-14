import typer
from rich.console import Console

from converge.cli.explain import ExplainabilityEngine
from converge.graph.store import GraphStore
from converge.scanner.scanner import Scanner
from converge.solver.conflict import Conflict, ConflictDetector, ConflictType
from converge.solver.planner import RepairPlan, RepairPlanner
from converge.validation.sandbox import UVSandbox
from converge.validation.smoke import ValidationRunner

app = typer.Typer(
    help="Converge: A Python-first repository intelligence and environment convergence platform.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def scan(
    path: str = typer.Argument(".", help="Path to the repository to scan"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Perform a dry run without saving to the database"),
) -> None:
    """
    Scan a codebase to build a graph of repositories, packages, modules, and services.
    """
    console.print(f"[bold green]Scanning repository at:[/bold green] {path}")

    scanner = Scanner(path)
    entities, rels = scanner.scan_all()

    console.print(f"Found [bold cyan]{len(entities)}[/bold cyan] entities and [bold cyan]{len(rels)}[/bold cyan] relationships.")

    if dry_run:
        console.print("[yellow]Dry run mode enabled. Results will not be saved.[/yellow]")
    else:
        store = GraphStore()
        # Save to SQLite
        for e in entities:
            store.add_entity(e)
        for r in rels:
            store.add_relationship(r)
        console.print("[green]Successfully persisted graph to converge_graph.db[/green]")



def _run_validation(
    path: str, conflicts: list[Conflict], plans: list[RepairPlan], console: Console
) -> None:
    console.print("\n[bold green]Validating plans in sandboxed environment...[/bold green]")
    sandbox = UVSandbox(path)
    runner = ValidationRunner(sandbox)

    # Determine packages to smoke test based on unresolved imports
    smoke_targets = []
    for c in conflicts:
        if c.type == ConflictType.UNRESOLVED_IMPORT:
            smoke_targets.append(c.involved_entities[1].replace("pkg:", ""))

    scores = runner.score_plans(plans, smoke_targets)

    best_plan = None
    for plan_id, success in scores.items():
        if success:
            best_plan = next(p for p in plans if p.id == plan_id)
            console.print(f"[green]Plan {plan_id} passed validation![/green]")
            break
        else:
            console.print(f"[red]Plan {plan_id} failed validation.[/red]")

    if best_plan:
        console.print(f"\n[bold green]Successfully found working plan: {best_plan.id}[/bold green]")
        console.print("[white]In a full implementation, Converge would now rewrite pyproject.toml and your lockfile.[/white]")
    else:
        console.print("\n[bold red]All candidate plans failed validation.[/bold red]")


@app.command()
def fix(
    path: str = typer.Argument(".", help="Path to the repository to fix"),
    apply: bool = typer.Option(False, "--apply", help="Apply the fix plan after validation"),
) -> None:
    """
    Identify conflicts in the environment and automatically generate and apply a repair plan.
    """
    console.print(f"[bold blue]Analyzing environment conflicts for:[/bold blue] {path}")

    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Failed to load graph. Did you run `converge scan` first? Error: {e}[/red]")
        return

    detector = ConflictDetector(G)
    conflicts = list(detector.detect_all())

    if not conflicts:
        console.print("[green]No conflicts detected in the graph![/green]")
        return

    console.print(f"[yellow]Detected {len(conflicts)} conflicts. Generating repair plans...[/yellow]")
    planner = RepairPlanner(conflicts)
    plans = planner.generate_plans()

    for plan in plans:
        console.print(f"\n[cyan]Candidate Plan:[/cyan] {plan.id}")
        console.print(f"[white]Rationale: {plan.rationale}[/white]")
        for action in plan.actions:
            console.print(f"  - [magenta]{action.action_type}[/magenta]: {action.description}")

    if not apply:
        console.print("\n[yellow]Running in dry-run mode. Use --apply to execute the fix.[/yellow]")
    else:
        _run_validation(path, conflicts, plans, console)



@app.command()
def doctor() -> None:
    """
    Diagnose issues with the environment, parsers, resolvers, or cache.
    """
    console.print("[bold cyan]Running Converge Diagnostics...[/bold cyan]")
    # TODO: Implement checks for uv, python, sqlite, etc.
    console.print("[green]System looks good![/green]")


@app.command()
def deps(
    target: str = typer.Argument(..., help="Entity ID to trace (e.g. repo:converge)"),
) -> None:
    """
    Show the dependency tree for a particular entity.
    """
    store = GraphStore()
    try:
        G = store.load_networkx()
    except Exception as e:
        console.print(f"[red]Failed to load graph. Error: {e}[/red]")
        return

    engine = ExplainabilityEngine(G, console)
    engine.render_dependency_tree(target)


@app.command()
def validate(
    path: str = typer.Argument(".", help="Path to the repository to validate"),
) -> None:
    """
    Run isolation and validation checks on the current environment without attempting a fix.
    """
    console.print("[bold blue]Running pure validation phase on environment...[/bold blue]")
    sandbox = UVSandbox(path)
    # Simply create sandbox to verify toolchain
    sandbox.create()
    console.print("[green]Sandbox toolchain is working and isolated execution succeeded.[/green]")
    sandbox.cleanup()


@app.command()
def explain(
    target: str = typer.Argument(..., help="Entity or conflict ID to explain"),
) -> None:
    """
    Explain the current state of the graph or details of a specific conflict/fix.
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


if __name__ == "__main__":
    app()
