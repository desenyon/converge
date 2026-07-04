# Converge CLI Reference

Converge ships a Rich-powered terminal interface with consistent headers, progress bars, and structured tables. All commands accept a repository path as the final argument (default: `.`).

## Global flags

| Flag | Description |
| --- | --- |
| `--version` | Print `converge <version>` and exit |
| `--json` | Machine-readable JSON on stdout (includes `schema_version` and `tool_version`) |
| `--quiet`, `-q` | Suppress progress spinners and decorative output |
| `--verbose`, `-v` | Enable debug logging on stderr |

## Workflow commands

These are the commands most developers use day to day:

```bash
converge init .              # scaffold .converge.toml
converge check .             # scan + doctor in one step
converge check . --force     # full rescan before diagnose
converge packages .          # declared / imported / missing / unused
converge fix .               # dry-run repair plans
converge fix . --apply       # validate and apply manifest repair
converge audit .             # show fix --apply audit log
converge status .            # graph + scan fingerprint dashboard
```

## All commands

| Command | Purpose |
| --- | --- |
| `scan` | Build `.converge/graph.db` from manifests and imports |
| `scan --force` | Bypass incremental skip and rescan |
| `scan --dry-run` | Parse without writing the graph |
| `doctor` | Report unresolved imports, unused deps, version clashes |
| `doctor --type unresolved_import` | Filter by conflict type |
| `check` | `scan` then `doctor` with a single header |
| `packages` | Tabular package inventory from the graph |
| `explain <target>` | Explain a conflict ID or graph entity |
| `create` | Create repo-local `.venv` from graph packages |
| `fix` | Propose repairs (dry-run exits `1` when issues exist) |
| `fix --apply` | Validate in sandbox, then write manifest + audit log |
| `export --format json\|csv` | Write graph artifacts under `.converge/exports/` |
| `audit` | Read `.converge/audit.log` |
| `init` | Write `.converge.toml` (use `--force` to overwrite) |
| `status` | Artifact and incremental-scan dashboard |
| `clean` | Remove `.converge/` and validation sandboxes |
| `clean --dry-run` | Preview removals without deleting |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or no actionable issues |
| `1` | Issues found (`doctor`, `fix` dry-run, `packages` with missing imports) |
| `2` | Fatal error (missing graph, invalid path, failed validation) |

## Repository-local artifacts

| Path | Purpose |
| --- | --- |
| `.converge/graph.db` | SQLite dependency graph |
| `.converge/scan_state.json` | Incremental scan fingerprints |
| `.converge/exports/` | JSON/CSV exports |
| `.converge/audit.log` | Append-only repair audit trail |
| `.converge.toml` | Optional repo config (also `[tool.converge]` in `pyproject.toml`) |
| `.venv` | Default environment created by `create` |

## Configuration

```toml
[tool.converge]
incremental_scan = true
skip_type_checking_imports = true
repair_targets = ["pyproject", "requirements"]
extra_scan_roots = ["src"]
```

Run `converge init .` to scaffold a commented `.converge.toml`.

## JSON envelope

Every `--json` payload includes:

```json
{
  "schema_version": 1,
  "tool_version": "0.2.0"
}
```

## Terminal UI

Interactive mode (default) renders:

- Branded command headers with repository path
- Progress bars with elapsed time during scan, create, and validation
- Rounded tables for conflicts, package inventory, and audit events
- Status badges for graph presence and incremental-scan state
- Footer hints with suggested next commands

Use `--quiet` or `--json` in CI and scripts.
