# AGENTS Guide

## Project Overview
- Converge is a Python CLI that scans a target repository, stores a repo-local dependency graph, diagnoses dependency issues, creates environments, and proposes manifest repairs.
- All command behavior must be scoped to the user-provided repository path, not the current shell working directory.

## Core Invariants
- Use `ProjectContext.from_target(...)` for any command or service that touches repository state.
- Repository artifacts live under `.converge/` inside the target repo.
- The graph database path is `.converge/graph.db` inside the target repo.
- Incremental scan state and fix audit log: `.converge/scan_state.json`, `.converge/audit.log` (when used).
- The default environment path is `.venv` inside the target repo.
- `fix --apply` must not mutate the repo unless validation succeeds first.

## Important Modules
- `src/converge/project_context.py` resolves repo-local paths.
- `src/converge/graph/store.py` manages repo-local graph persistence.
- `src/converge/scanner/` contains manifest parsing, AST import scanning, and service detection.
- `src/converge/cli/main.py` owns command wiring and must stay path-coherent.
- `src/converge/repair/manifest.py` applies manifest edits for validated repair plans.

## Development Workflow
- Follow TDD for behavioral changes: write the failing test first, verify it fails, then implement the minimal fix.
- Prefer integration tests for CLI behavior and unit tests for parsing, graph, and manifest logic.
- Before claiming a task is complete, rerun the exact tests that prove the claim.

## Verification Commands
- Targeted unit tests: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/<file>.py -v -s`
- Targeted integration tests: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/<file>.py -v -s`
- Broader suite: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit tests/integration -v`
- Coverage (optional): `PYTHONPATH=src .venv/bin/pytest tests --cov=converge --cov-report=term-missing` (fails under 60% line coverage per `pyproject.toml`)
- Typecheck: `mypy src/converge` (matches CI)

## CLI conventions
- Exit codes: `0` success, `1` issues found (`doctor` / `fix` dry-run), `2` error — see `converge/exit_codes.py`.
- Repo config: `[tool.converge]` in `pyproject.toml` and optional `.converge.toml` — see `converge/settings.py`.

## Notes
- Keep docs aligned with real behavior. Do not describe validation or repair features more strongly than the code proves.
- Keep `.gitignore` current for repo-local artifacts such as `.converge/` and validation sandboxes.
