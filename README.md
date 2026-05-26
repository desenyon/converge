<p align="center">
  <img src="docs/assets/converge-logo.svg" alt="Converge: repository-scoped dependency intelligence for Python" width="860">
</p>

<p align="center">
  <a href="https://pypi.org/project/converge-cli/"><img alt="PyPI" src="https://img.shields.io/pypi/v/converge-cli?style=for-the-badge&label=PyPI&color=2dd4bf"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-0b1020?style=for-the-badge&logo=python&logoColor=white&labelColor=0b1020&color=8b5cf6">
  <img alt="Typed with mypy" src="https://img.shields.io/badge/typed-mypy-2dd4bf?style=for-the-badge&labelColor=0b1020">
  <img alt="Coverage floor" src="https://img.shields.io/badge/coverage-60%25%20floor-8b5cf6?style=for-the-badge&labelColor=0b1020">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-f8fafc?style=for-the-badge&labelColor=0b1020&color=64748b"></a>
</p>

<p align="center">
  <strong>Scan a Python repository, build a repo-local dependency graph, diagnose drift, create an environment, and apply validated manifest repairs.</strong>
</p>

---

## Why Converge

Dependency tools usually answer one narrow question: what is in the manifest, what is in the lockfile, or what can be installed. Converge looks at the repository as a system.

It reads manifests, parses imports, stores a graph inside the target repo, and uses that graph to explain what is missing, unused, or ready to repair. Every command is scoped to the path you pass in, so running Converge from one directory never silently writes state into another project.

```text
repo path -> scan -> .converge/graph.db -> doctor/explain/create/fix/export
```

## What It Does Today

| Capability | What happens |
| --- | --- |
| `scan` | Parses `pyproject.toml`, `requirements*.txt`, Python imports, and service routes into `.converge/graph.db`. |
| `doctor` | Reports unresolved imports, unused dependencies, version clashes, and lockfile hints. |
| `explain` | Shows why an entity or conflict exists in the graph. |
| `create` | Builds a repository-local `.venv` from graph package nodes. |
| `fix` | Generates repair plans and applies validated dependency additions. |
| `export` | Writes graph data to JSON or CSV under `.converge/exports/`. |
| `clean` | Removes Converge-generated repo-local artifacts. |

Converge is intentionally conservative: repairs are validated in isolation before host manifests are changed, and current repair planning focuses on dependency additions for unresolved imports.

## Install

```bash
uv tool install converge-cli
```

or:

```bash
pipx install converge-cli
```

For local development:

```bash
git clone <your-repo-url>
cd converge
uv sync --dev
```

## Quick Start

Given a repository with:

```python
import requests
```

and a manifest that does not declare `requests`:

```toml
[project]
name = "demo"
dependencies = []
```

Run:

```bash
converge scan .
converge doctor .
converge fix .
converge fix . --apply
```

After validation, Converge updates the target repository manifest and records the repair in `.converge/audit.log`.

## Command Guide

### Scan

```bash
converge scan /path/to/repo
converge scan /path/to/repo --dry-run
```

`scan` builds the graph from declared dependencies, imports, and detected services. Without `--dry-run`, the graph is persisted to `/path/to/repo/.converge/graph.db`.

### Doctor

```bash
converge doctor /path/to/repo
```

`doctor` exits `0` when no actionable issues are found and `1` when dependency issues are detected. If no graph exists, it exits with an error and tells you to run `scan`.

### Explain

```bash
converge explain conflict:unresolved_mod:main.py_pkg:requests /path/to/repo
converge explain pkg:requests /path/to/repo
```

Use `explain` when you want the graph context behind a conflict or entity.

### Create

```bash
converge create /path/to/repo --provider uv
converge create /path/to/repo --provider uv --python 3.12
```

`create` loads the repository graph, creates `/path/to/repo/.venv`, installs graph package nodes, and prints the activation command.

### Fix

```bash
converge fix /path/to/repo
converge fix /path/to/repo --apply
```

Dry-run mode prints candidate plans and changes nothing. `--apply` validates a plan in an isolated sandbox, writes the selected manifest repair, and appends an audit event.

### Export

```bash
converge export /path/to/repo --format json
converge export /path/to/repo --format csv
```

JSON export writes `.converge/exports/graph.json`. CSV export writes `.converge/exports/nodes.csv` and `.converge/exports/edges.csv`.

### Clean

```bash
converge clean /path/to/repo
```

Removes generated artifacts such as `.converge/graph.db`, `.converge/exports/`, `.converge/scan_state.json`, `.converge/audit.log`, and `.venv-converge-test`.

## Repository-Local State

Converge writes derived state inside the target repository:

| Artifact | Purpose |
| --- | --- |
| `.converge/graph.db` | SQLite-backed dependency graph. |
| `.converge/scan_state.json` | Incremental scan fingerprints. |
| `.converge/exports/` | JSON and CSV graph exports. |
| `.converge/audit.log` | Append-only fix audit events. |
| `.venv` | Default created environment. |
| `.venv-converge-test` | Temporary validation sandbox name, cleaned after use. |

## JSON and Exit Codes

Global flags:

```bash
converge --json doctor /path/to/repo
converge --quiet scan /path/to/repo
converge --verbose doctor /path/to/repo
```

`--json` payloads include:

```json
{
  "schema_version": 1,
  "tool_version": "0.1.7"
}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success, or no actionable issues. |
| `1` | Issues found by `doctor` or `fix` dry-run. |
| `2` | Command error, such as a missing graph or failed export. |

## Configuration

Settings are read from optional `.converge.toml` and `[tool.converge]` in `pyproject.toml`. When both exist, `pyproject.toml` wins on conflicts.

Useful keys include:

```toml
[tool.converge]
incremental_scan = true
skip_type_checking_imports = true
repair_targets = ["pyproject", "requirements"]
extra_scan_roots = ["src"]
```

See [docs/ROADMAP.md](docs/ROADMAP.md) for the current implementation map and remaining stretch work.

## Development

Run the full verified suite:

```bash
TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit tests/integration -v
```

Lint and type check:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/converge
```

Coverage:

```bash
PYTHONPATH=src .venv/bin/pytest tests --cov=converge --cov-report=term-missing
```

Key implementation files:

| Area | File |
| --- | --- |
| Project-scoped paths | `src/converge/project_context.py` |
| Graph persistence | `src/converge/graph/store.py` |
| Manifest scanning | `src/converge/scanner/project.py` |
| AST import scanning | `src/converge/scanner/ast_parser.py` |
| CLI wiring | `src/converge/cli/main.py` |
| Manifest repair | `src/converge/repair/manifest.py` |
| Validation sandbox | `src/converge/validation/sandbox.py` |

## Current Limits

Converge is useful now, but it does not overstate what the implementation proves.

- Repair planning is focused on dependency additions, not broad manifest rewrites.
- Validation is smoke-import based, not a full application test harness.
- Import classification is Python-focused and conservative.
- Export formats are designed for inspection and automation, not analytics warehousing.

## License

MIT. See [LICENSE](LICENSE).
