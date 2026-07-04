# Converge feature roadmap (implemented vs. stretch)

This document maps the product roadmap to what exists in the codebase today.

## CLI and automation

| Capability | Status |
|------------|--------|
| Machine-readable `--json` on commands | Implemented (global flag) |
| Stable exit codes (`ExitCode`: 0 / 1 / 2) | Implemented |
| `--quiet` / `--verbose` | Implemented |
| Configuration: `[tool.converge]` and `.converge.toml` | Implemented |
| `toolchain` command (detect uv / poetry / pip-tools / pip) | Implemented |
| `lock` command (`uv lock` or `pip-compile`) | Implemented |

## Scanning and graph

| Capability | Status |
|------------|--------|
| Parallel AST parsing | Implemented |
| Incremental scan + partial graph merge | Implemented |
| Skip `TYPE_CHECKING` imports | Implemented |
| Test vs. source module classification | Implemented |
| Lockfile entities (`LOCKED_BY`, `RESOLVES_TO`) for uv + poetry | Implemented |
| `CONFLICTS_WITH` edges for incompatible declared constraints | Implemented |
| uv workspace members (`BELONGS_TO`) | Implemented |
| pip-tools `requirements.in` + compiled `requirements.txt` | Implemented |
| Constraints files (`constraints*.txt`) | Implemented |
| Editable installs (`CONFIGURED_BY`) | Implemented |
| npm, Dockerfile, `apt.txt`, `Cargo.toml`, `environment.yml` | Implemented |
| `[tool.uv.sources]` in doctor JSON | Implemented |

## Diagnosis and repair

| Capability | Status |
|------------|--------|
| Unused deps ignore test-only imports and dev groups | Implemented |
| Declared constraint intersection conflicts | Implemented |
| Lockfile drift (`LOCKFILE_DRIFT`) | Implemented |
| pip-tools compile drift (`COMPILE_DRIFT`) | Implemented |
| `doctor --json` package `{declared, locked, imported}` triple | Implemented |
| Add / pin / remove repair plans | Implemented |
| Group-aware adds (test imports → dev group) | Implemented |
| Plan ranking (prefer fewer, non-destructive changes) | Implemented |
| uv-native `uv add` / `uv remove` / `uv lock` on fix | Implemented |
| Requirements and pyproject manifest repairs | Implemented |
| Audit log for `fix --apply` and `lock` | Implemented |

## Environment and toolchain

| Capability | Status |
|------------|--------|
| Unified `UvBackend` / `PipBackend` | Implemented |
| `create --provider auto` | Implemented |
| `uv sync --frozen` when `uv.lock` exists | Implemented |
| Constraint-aware install specs from graph | Implemented |
| Validation sandbox uses toolchain backends | Implemented |

## Stretch (deferred)

- Full Poetry-native repair (`poetry add` / `poetry lock`).
- pnpm / yarn lock parsing for npm.
- PEP 420 namespace package formalism.
- `converge test` hook for post-repair test suite validation.
- graphify MCP / Neo4j export (see `graphify-out/` for local architecture graphs).
