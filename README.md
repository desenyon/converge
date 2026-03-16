# Converge

Converge is a Python CLI for scanning a repository, building a local dependency graph, diagnosing dependency problems, creating a repository-scoped virtual environment, and applying validated manifest repairs.

It is designed for one core workflow:

1. Point Converge at a repository
2. Scan the repository into a local graph
3. Diagnose problems from that graph
4. Create or repair the environment using repository-scoped artifacts

Converge stores its own derived data inside the target repository, not in a global shared cache.

## What Converge Does

- Scans `pyproject.toml` and `requirements*.txt`
- Parses Python imports from the repository source tree
- Stores a repository-local graph at `.converge/graph.db`
- Detects unresolved imports and unused declared dependencies
- Creates a `.venv` inside the target repository
- Exports graph data to JSON or CSV artifacts
- Applies validated dependency additions to `pyproject.toml`

## Repository-Scoped Artifacts

When you run Converge against a repository, it writes derived artifacts inside that repository:

- Graph database: `.converge/graph.db`
- Exports: `.converge/exports/`
- Default environment: `.venv`
- Validation sandbox: `.venv-converge-test`

This makes command behavior predictable and keeps multiple repositories isolated from each other.

## Installation

### With `uv`

```bash
uv tool install converge-cli
```

### With `pipx`

```bash
pipx install converge-cli
```

### For local development

```bash
git clone <your-repo-url>
cd converge
uv sync --dev
```

If you are working from source in this repository, the test commands below assume:

```bash
PYTHONPATH=src
```

## Core Workflow

### 1. Scan a repository

```bash
converge scan /path/to/repo
```

What it does:

- Parses declared dependencies from manifests
- Scans Python files for imports
- Writes the graph to `/path/to/repo/.converge/graph.db`

Useful variant:

```bash
converge scan /path/to/repo --dry-run
```

Use `--dry-run` when you want to inspect the scan result without writing the graph database.

### 2. Diagnose dependency issues

```bash
converge doctor /path/to/repo
```

What it reports today:

- Unresolved imports: a package is imported in code but missing from manifests
- Unused dependencies: a package is declared but never imported in scanned modules
- Version clashes if they exist in the graph

If the repository has not been scanned yet, `doctor` tells you to run `scan` first.

### 3. Explain a conflict or entity

```bash
converge explain conflict:unresolved_mod:main.py_pkg:requests /path/to/repo
```

You can also explain an entity already present in the graph:

```bash
converge explain pkg:requests /path/to/repo
```

Use `explain` when `doctor` finds an issue and you want clearer context for what Converge saw.

### 4. Create a repository-scoped environment

```bash
converge create /path/to/repo --provider uv
```

What it does:

- Loads the repository graph
- Collects package nodes from that graph
- Creates `/path/to/repo/.venv`
- Installs the resolved package set into that environment

By default, Converge creates `.venv` inside the target repository and prints the activation command after creation.

Optional Python version:

```bash
converge create /path/to/repo --provider uv --python 3.12
```

### 5. Generate or apply a repair

Dry run:

```bash
converge fix /path/to/repo
```

Apply a validated repair:

```bash
converge fix /path/to/repo --apply
```

Current behavior:

- Detects unresolved imports from the graph
- Generates candidate repair plans
- Validates plans in an isolated sandbox
- Applies the selected validated change to `pyproject.toml`

Today, the repair flow is conservative and focused on dependency additions for unresolved imports.

### 6. Export the graph

Export to JSON:

```bash
converge export /path/to/repo --format json
```

Export to CSV:

```bash
converge export /path/to/repo --format csv
```

Generated artifacts:

- JSON: `.converge/exports/graph.json`
- CSV: `.converge/exports/nodes.csv` and `.converge/exports/edges.csv`

### 7. Clean derived artifacts

```bash
converge clean /path/to/repo
```

This removes Converge-generated artifacts such as:

- `.converge/graph.db`
- `.converge/exports/`
- `.venv-converge-test`

## Command Reference

### `scan`

```bash
converge scan PATH [--dry-run]
```

- `PATH`: target repository
- `--dry-run`: do not persist the graph

### `doctor`

```bash
converge doctor PATH
```

- `PATH`: target repository that has already been scanned

### `explain`

```bash
converge explain TARGET PATH
```

- `TARGET`: entity ID or conflict ID
- `PATH`: target repository

### `create`

```bash
converge create PATH [--provider uv|pip] [--python VERSION]
```

- `PATH`: target repository
- `--provider`: environment provisioning backend
- `--python`: interpreter version if supported by the selected provider

### `fix`

```bash
converge fix PATH [--apply]
```

- `PATH`: target repository
- `--apply`: validate and write the selected repair

### `export`

```bash
converge export PATH [--format json|csv]
```

- `PATH`: target repository
- `--format`: output format

### `clean`

```bash
converge clean PATH
```

- `PATH`: target repository

## Example Session

Given a repository with this problem:

```python
import requests
```

but this manifest:

```toml
[project]
name = "demo"
dependencies = []
```

You can run:

```bash
converge scan .
converge doctor .
converge fix .
converge fix . --apply
```

After `fix --apply`, Converge updates `pyproject.toml` with the validated missing dependency and keeps the graph and environment operations scoped to that repository.

## Output Philosophy

Converge aims for output that is:

- Repository-scoped
- Specific about what changed
- Honest about what was simulated versus applied
- Actionable for developers

If a command succeeds, it should tell you where artifacts were written. If it fails, it should tell you what prerequisite is missing or what next command to run.

## Development

### Run tests

```bash
TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit tests/integration -v -s
```

### Run a targeted test

```bash
TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/test_fix_command.py -v -s
```

### Lint and type check

If you have the tools installed in the local environment:

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
```

## Current Limits

Converge is useful today, but it is not pretending to do more than the current implementation proves.

Examples of current limits:

- Repair planning is still focused on dependency additions, not broad manifest surgery
- Validation is smoke-test based, not a full application test harness
- Import classification is Python-focused and intentionally conservative
- Export formats are intentionally simple and designed for debugging and inspection

## Troubleshooting

### `doctor` says the graph is missing

Run:

```bash
converge scan /path/to/repo
```

### `create` says it cannot load a graph

You need to scan the target repository first:

```bash
converge scan /path/to/repo
converge create /path/to/repo
```

### `fix --apply` does not change anything

Possible reasons:

- No issues were found
- Validation failed for all candidate plans
- `pyproject.toml` is missing from the target repository

### `export` produced no files

You likely have not scanned the repository yet:

```bash
converge scan /path/to/repo
converge export /path/to/repo --format json
```

## Architecture Pointers

Key files:

- `src/converge/project_context.py`
- `src/converge/graph/store.py`
- `src/converge/scanner/project.py`
- `src/converge/scanner/ast_parser.py`
- `src/converge/env_manager.py`
- `src/converge/repair/manifest.py`
- `src/converge/cli/main.py`

For repository-specific contributor guidance, see `AGENTS.md`.

## License

MIT
