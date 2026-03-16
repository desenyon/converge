# Core Reliability Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild Converge so `scan`, `doctor`, `create`, `fix`, `explain`, and `clean` operate coherently for a specific repository and are verified by end-to-end tests.

**Architecture:** Introduce a single project-context layer that resolves repository-scoped artifact paths, route every CLI command through that context, and make graph persistence a repo-local derived artifact rather than global process state. Rework scanning, diagnostics, environment creation, and repair validation around deterministic repo-local inputs and prove behavior through temporary-repo integration tests.

**Tech Stack:** Python 3.12+, Typer, SQLModel/SQLite, NetworkX, pytest, uv, rich

---

### Task 1: Add repository context model

**Files:**
- Create: `src/converge/project_context.py`
- Modify: `src/converge/__init__.py`
- Test: `tests/unit/test_project_context.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from converge.project_context import ProjectContext


def test_project_context_scopes_artifacts_to_target_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    context = ProjectContext.from_target(repo)

    assert context.root_dir == repo.resolve()
    assert context.graph_db_path == repo / ".converge" / "graph.db"
    assert context.default_env_path == repo / ".venv"
```

**Step 2: Run test to verify it fails**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_project_context.py::test_project_context_scopes_artifacts_to_target_repo -v`
Expected: FAIL with `ModuleNotFoundError` or missing `ProjectContext`

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    root_dir: Path
    graph_db_path: Path
    artifact_dir: Path
    default_env_path: Path

    @classmethod
    def from_target(cls, target: Path | str) -> "ProjectContext":
        root = Path(target).resolve()
        artifact_dir = root / ".converge"
        return cls(
            root_dir=root,
            artifact_dir=artifact_dir,
            graph_db_path=artifact_dir / "graph.db",
            default_env_path=root / ".venv",
        )
```

**Step 4: Run test to verify it passes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_project_context.py::test_project_context_scopes_artifacts_to_target_repo -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_project_context.py src/converge/project_context.py src/converge/__init__.py
git commit -m "feat: add repository project context"
```

### Task 2: Make graph persistence repo-local and resettable

**Files:**
- Modify: `src/converge/graph/store.py`
- Modify: `src/converge/project_context.py`
- Test: `tests/unit/test_graph_store.py`

**Step 1: Write the failing test**

```python
from converge.graph.store import GraphStore
from converge.models import EntityType, GraphEntity
from converge.project_context import ProjectContext


def test_graph_store_uses_repo_local_database(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    context = ProjectContext.from_target(repo)

    store = GraphStore.for_context(context)
    store.add_entity(GraphEntity(id="pkg:requests", type=EntityType.PACKAGE, name="requests"))

    assert context.graph_db_path.exists()
```

**Step 2: Run test to verify it fails**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_graph_store.py::test_graph_store_uses_repo_local_database -v`
Expected: FAIL because `for_context` does not exist or DB path is wrong

**Step 3: Write minimal implementation**

- Add `GraphStore.for_context(context)` constructor
- Ensure parent artifact directory is created lazily
- Add `reset()` helper for full graph replacement during `scan`
- Keep load/save methods deterministic and repo-scoped

**Step 4: Run test to verify it passes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_graph_store.py::test_graph_store_uses_repo_local_database -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_graph_store.py src/converge/graph/store.py src/converge/project_context.py
git commit -m "feat: scope graph persistence per repository"
```

### Task 3: Rebuild manifest parsing and import classification

**Files:**
- Modify: `src/converge/scanner/project.py`
- Modify: `src/converge/scanner/ast_parser.py`
- Modify: `src/converge/scanner/scanner.py`
- Test: `tests/unit/test_scanner.py`
- Test: `tests/unit/test_import_classification.py`

**Step 1: Write the failing tests**

```python
def test_ast_parser_ignores_internal_src_package(tmp_path):
    src_pkg = tmp_path / "src" / "myapp"
    src_pkg.mkdir(parents=True)
    (src_pkg / "__init__.py").write_text("")
    (src_pkg / "service.py").write_text("import requests\nfrom myapp import helpers\n")
    (src_pkg / "helpers.py").write_text("\n")

    parser = PythonASTParser(str(tmp_path))
    _mods, rels = parser.scan_directory()

    assert any(r.target_id == "pkg:requests" for r in rels)
    assert not any(r.target_id == "pkg:myapp" for r in rels)
```

```python
def test_project_parser_reads_pep621_optional_and_requirements(tmp_path):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_scanner.py tests/unit/test_import_classification.py -v`
Expected: FAIL because internal imports are misclassified or manifests are incompletely parsed

**Step 3: Write minimal implementation**

- Normalize target repo root and discover internal modules from root and `src/`
- Parse `project.dependencies`, optional dependency groups, and `requirements*.txt` consistently
- Deduplicate package entities and relationship edges during scan
- Make scanner return a clean, deterministic graph snapshot

**Step 4: Run tests to verify they pass**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_scanner.py tests/unit/test_import_classification.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_scanner.py tests/unit/test_import_classification.py src/converge/scanner/project.py src/converge/scanner/ast_parser.py src/converge/scanner/scanner.py
git commit -m "fix: rebuild dependency scanning semantics"
```

### Task 4: Route CLI scan/doctor/explain/clean through project context

**Files:**
- Modify: `src/converge/cli/main.py`
- Modify: `src/converge/cli/explain.py`
- Modify: `src/converge/solver/conflict.py`
- Test: `tests/integration/test_cli_repo_scoping.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from converge.cli.main import app


def test_doctor_uses_target_repo_graph(tmp_path):
    runner = CliRunner()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "repo"\ndependencies = []\n')
    (repo / "main.py").write_text('import requests\n')

    scan_result = runner.invoke(app, ["scan", str(repo)])
    doctor_result = runner.invoke(app, ["doctor", str(repo)])

    assert scan_result.exit_code == 0
    assert doctor_result.exit_code == 0
    assert "requests" in doctor_result.stdout
```

**Step 2: Run test to verify it fails**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/test_cli_repo_scoping.py::test_doctor_uses_target_repo_graph -v`
Expected: FAIL because `doctor` currently ignores the path

**Step 3: Write minimal implementation**

- Give `doctor`, `explain`, `export`, and `clean` a target path argument where needed
- Resolve `ProjectContext` at command entry
- Use repo-local `GraphStore.for_context(context)` everywhere
- Make `clean` remove only repo-local artifacts

**Step 4: Run test to verify it passes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/test_cli_repo_scoping.py::test_doctor_uses_target_repo_graph -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/integration/test_cli_repo_scoping.py src/converge/cli/main.py src/converge/cli/explain.py src/converge/solver/conflict.py
git commit -m "fix: scope CLI commands to target repository"
```

### Task 5: Rebuild environment creation coherently

**Files:**
- Modify: `src/converge/env_manager.py`
- Modify: `src/converge/cli/main.py`
- Modify: `src/converge/project_context.py`
- Test: `tests/unit/test_env_manager.py`
- Test: `tests/integration/test_create_command.py`

**Step 1: Write the failing tests**

```python
def test_create_command_uses_repo_environment_path(tmp_path):
    ...
```

```python
def test_env_manager_plans_install_from_repo_requirements(tmp_path):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_env_manager.py tests/integration/test_create_command.py -v`
Expected: FAIL because `create` uses stale global graph state and provider semantics are weak

**Step 3: Write minimal implementation**

- Bind `EnvironmentManager` to `ProjectContext`
- Separate environment creation from dependency resolution planning
- Build install list from repo-scoped graph or manifest-derived packages deterministically
- Improve provider validation and error reporting
- Ensure activation instructions match actual environment path

**Step 4: Run tests to verify they pass**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_env_manager.py tests/integration/test_create_command.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_env_manager.py tests/integration/test_create_command.py src/converge/env_manager.py src/converge/cli/main.py src/converge/project_context.py
git commit -m "fix: rebuild environment creation workflow"
```

### Task 6: Make `fix` generate real repo manifest edits

**Files:**
- Create: `src/converge/repair/manifest.py`
- Modify: `src/converge/solver/planner.py`
- Modify: `src/converge/cli/main.py`
- Modify: `src/converge/validation/sandbox.py`
- Modify: `src/converge/validation/smoke.py`
- Test: `tests/unit/test_manifest_repairs.py`
- Test: `tests/integration/test_fix_command.py`

**Step 1: Write the failing tests**

```python
def test_fix_apply_updates_pyproject_dependencies(tmp_path):
    ...
```

```python
def test_validation_runner_checks_repaired_manifest_in_isolated_env(tmp_path):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_manifest_repairs.py tests/integration/test_fix_command.py -v`
Expected: FAIL because `fix` does not currently edit manifests or validate repo state coherently

**Step 3: Write minimal implementation**

- Represent repair actions as concrete manifest mutations
- Apply mutations to a sandbox copy of the repo for validation
- Validate using import smoke tests tied to unresolved packages
- Only write back to host repo when `--apply` is requested and validation succeeds

**Step 4: Run tests to verify they pass**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit/test_manifest_repairs.py tests/integration/test_fix_command.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_manifest_repairs.py tests/integration/test_fix_command.py src/converge/repair/manifest.py src/converge/solver/planner.py src/converge/cli/main.py src/converge/validation/sandbox.py src/converge/validation/smoke.py
git commit -m "feat: apply validated manifest repairs"
```

### Task 7: Harden explain/export and clean repo documentation

**Files:**
- Modify: `src/converge/cli/explain.py`
- Modify: `src/converge/cli/main.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Create: `AGENTS.md`
- Test: `tests/integration/test_explain_command.py`

**Step 1: Write the failing test**

```python
def test_explain_reports_repo_local_conflict_details(tmp_path):
    ...
```

**Step 2: Run test to verify it fails**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/test_explain_command.py -v`
Expected: FAIL because explain output is tied to old conflict formatting or wrong graph state

**Step 3: Write minimal implementation**

- Align explain output with new conflict IDs and repo-local graph loading
- Make export behavior real or clearly scoped if still minimal
- Rewrite architecture docs to match implemented pipeline
- Add a repo-level `AGENTS.md` with architecture, commands, invariants, and verification expectations

**Step 4: Run test to verify it passes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/integration/test_explain_command.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/integration/test_explain_command.py src/converge/cli/explain.py src/converge/cli/main.py README.md docs/architecture.md AGENTS.md
git commit -m "docs: align explain flow and project guidance"
```

### Task 8: Run full verification and polish ignores

**Files:**
- Modify: `.gitignore`
- Test: `tests/unit/test_*.py`
- Test: `tests/integration/test_*.py`

**Step 1: Write the failing test or check**

Add any final missing regression test discovered during verification before changing production code.

**Step 2: Run verification to confirm current failure before final fixes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit tests/integration -v`
Expected: Any remaining failures are real regressions to close before completion

**Step 3: Write minimal implementation**

- Fix the last verified regression only
- Ensure `.gitignore` includes repo-local artifacts such as `.converge/` and validation sandboxes if they are generated
- Keep docs and command help text consistent with final behavior

**Step 4: Run test to verify it passes**

Run: `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pytest tests/unit tests/integration -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .gitignore tests src README.md docs AGENTS.md
git commit -m "chore: finalize reliability rebuild"
```
