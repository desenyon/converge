# Converge feature roadmap (implemented vs. stretch)

This document maps the product roadmap to what exists in the codebase today.

## CLI and automation

| Capability | Status |
|------------|--------|
| Machine-readable `--json` on commands | Implemented (global flag) |
| Stable exit codes (`ExitCode`: 0 / 1 / 2) | Implemented |
| `--quiet` / `--verbose` | Implemented (quiet suppresses most Rich output) |
| Configuration: `[tool.converge]` and `.converge.toml` | Implemented (`load_converge_settings`) |

## Scanning and graph

| Capability | Status |
|------------|--------|
| Parallel AST parsing (thread pool) | Implemented |
| Incremental scan (full-tree hash short-circuit) | Implemented (`.converge/scan_state.json`) |
| Skip imports under `if TYPE_CHECKING:` | Implemented (configurable via `skip_type_checking_imports`) |
| Test vs. source module classification | Implemented (`metadata.scan_kind` on modules) |
| Extra scan roots (multi-layout repos) | Implemented (`extra_scan_roots`) |
| Namespace / editable install nuance | Partial (same heuristics as before; no PEP 420 formalism) |

## Diagnosis and repair

| Capability | Status |
|------------|--------|
| Unused deps ignore test-only imports | Implemented |
| Optional dependency groups in `pyproject` | Already merged into declared deps for the graph |
| Lockfile hints in `doctor --json` | Implemented (presence/size of `uv.lock`, `poetry.lock`) |
| Repair `requirements*.txt` | Implemented (`repair_targets` includes `requirements`) |
| Append-only audit log for `fix --apply` | Implemented (`.converge/audit.log`) |

## Tooling and CI

| Capability | Status |
|------------|--------|
| Coverage reporting (`pytest-cov`, `[tool.coverage]`) | Implemented |
| Pre-commit (ruff) for this repo | Implemented (`.pre-commit-config.yaml`) |
| Example pre-commit + GitHub Actions for consumers | Implemented (`docs/examples/`) |
| PyPI release workflow | Already present (`.github/workflows/release.yml`) |

## Stretch (not fully implemented)

- Deeper `typing` / lazy import edge cases beyond module-level `TYPE_CHECKING` and simple `__import__` / `importlib.import_module` calls.
- Full lockfile-driven resolution (Poetry-style) integrated into the solver; `uv.lock` now lists resolved package names for `doctor --json`.
- Additional `create` providers beyond `uv` and stdlib `venv`+`pip` (already supported via `--provider pip`).

## Recently completed (from prior roadmap)

- Partial incremental graph merge when only some `.py` files change (`Scanner.scan_incremental`).
- JSON envelope: `schema_version` + `tool_version` on `--json` output.
- stderr logging for `--verbose`; SQLite `GraphStore` disposal via context manager / `close()`.
- CI: Python 3.12 and 3.13 matrix; coverage floor 60%; `mypy src/converge` aligned with AGENTS.
