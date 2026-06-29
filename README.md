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
init -> check -> packages -> fix --apply -> audit
         |                         |
         v                         v
   .converge/graph.db         .converge/audit.log
```

## What It Does Today

| Capability | What happens |
| --- | --- |
| `init` | Scaffolds a repository-local `.converge.toml`. |
| `scan` | Parses manifests and Python imports into `.converge/graph.db`. |
| `check` | Runs `scan` + `doctor` in one step (ideal for CI and local QA). |
| `doctor` | Reports unresolved imports, unused dependencies, and version clashes. |
| `packages` | Lists declared, imported, missing, and unused packages. |
| `explain` | Shows why an entity or conflict exists in the graph. |
| `create` | Builds a repository-local `.venv` from graph package nodes. |
| `fix` | Generates repair plans and applies validated dependency additions. |
| `audit` | Shows the append-only repair log from `fix --apply`. |
| `status` | Dashboard for graph state, scan fingerprints, and lockfiles. |
| `export` | Writes graph data to JSON or CSV under `.converge/exports/`. |
| `clean` | Removes Converge-generated repo-local artifacts. |

Converge is intentionally conservative: repairs are validated in isolation before host manifests are changed.

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
converge init .
converge check .
converge packages .
converge fix .
converge fix . --apply
converge audit .
```

After validation, Converge updates the target repository manifest and records the repair in `.converge/audit.log`.

## Command Guide

See the full reference in [docs/CLI.md](docs/CLI.md).

### Recommended workflow

```bash
converge check /path/to/repo          # scan + diagnose
converge check /path/to/repo --force    # full rescan when needed
converge packages /path/to/repo       # quick inventory
converge doctor /path/to/repo --type unresolved_import
converge fix /path/to/repo --apply
converge status /path/to/repo
```

### Scan

```bash
converge scan /path/to/repo
converge scan /path/to/repo --dry-run
converge scan /path/to/repo --force     # bypass incremental skip
```

Incremental scan is **on by default**. Unchanged source trees skip re-scan unless `--force` is passed.

### Doctor

```bash
converge doctor /path/to/repo
converge doctor /path/to/repo --type unused_dependency
```

Exits `0` when clean, `1` when issues are found, `2` on error (missing graph, invalid path).

### Fix

```bash
converge fix /path/to/repo
converge fix /path/to/repo --apply
```

Dry-run exits `1` when repair plans exist. `--apply` validates in an isolated sandbox before writing manifests.

### Clean

```bash
converge clean /path/to/repo
converge clean /path/to/repo --dry-run
```

Removes the entire `.converge/` directory and `.venv-converge-test` validation sandboxes.

## Repository-Local State

| Artifact | Purpose |
| --- | --- |
| `.converge/graph.db` | SQLite-backed dependency graph. |
| `.converge/scan_state.json` | Incremental scan fingerprints. |
| `.converge/exports/` | JSON and CSV graph exports. |
| `.converge/audit.log` | Append-only fix audit events. |
| `.converge.toml` | Optional repo configuration. |
| `.venv` | Default created environment. |
| `.venv-converge-test` | Temporary validation sandbox, cleaned after use. |

## JSON and Exit Codes

Global flags:

```bash
converge --version
converge --json doctor /path/to/repo
converge --quiet scan /path/to/repo
converge --verbose doctor /path/to/repo
```

`--json` payloads include:

```json
{
  "schema_version": 1,
  "tool_version": "0.2.0"
}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success, or no actionable issues. |
| `1` | Issues found by `doctor`, `fix` dry-run, or `packages`. |
| `2` | Command error, such as a missing graph or failed validation. |

## Configuration

Settings are read from optional `.converge.toml` and `[tool.converge]` in `pyproject.toml`. When both exist, `pyproject.toml` wins on conflicts.

```toml
[tool.converge]
incremental_scan = true
skip_type_checking_imports = true
repair_targets = ["pyproject", "requirements"]
extra_scan_roots = ["src"]
```

Run `converge init .` to scaffold a commented `.converge.toml`.

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

Key implementation files:

| Area | File |
| --- | --- |
| Project-scoped paths | `src/converge/project_context.py` |
| Graph persistence | `src/converge/graph/store.py` |
| CLI wiring | `src/converge/cli/main.py` |
| Terminal UI | `src/converge/cli/tui.py` |
| Manifest repair | `src/converge/repair/manifest.py` |
| Validation sandbox | `src/converge/validation/sandbox.py` |

See [docs/architecture.md](docs/architecture.md) and [docs/ROADMAP.md](docs/ROADMAP.md) for design notes.

## Current Limits

- Repair planning focuses on dependency additions, not broad manifest rewrites.
- Validation is smoke-import based, not a full application test harness.
- Import classification is Python-focused and conservative.

## License

MIT. See [LICENSE](LICENSE).
