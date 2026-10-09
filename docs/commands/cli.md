# CLI reference

Run `converge --help` and `converge COMMAND --help` for the exact parser contract. The [README command table](../../README.md#cli-and-output) lists all implemented commands and stable exit codes.

Common flows:

```bash
converge discover . --json
converge check . --sarif
converge plan . --offline --timeout 60 --json
converge solve . --dry-run --json
converge verify . --offline --timeout 60 --json
converge solve . --yes --offline
converge apply . PLAN_ID --yes --offline --timeout 60
converge audit . --json
converge undo . --json
converge config explain . --json
```

`--offline` and `--timeout` are global. `--frozen` belongs to solve and rejects any lock generation/refresh action. `--yes` belongs to solve/apply; it overrides `autoApply` for execution consent. Configuration applies to planning and execution, so plan/apply must use the same network/timeout policy to obtain the same ID.

`verify` validates the proposed repair in a temporary copy, including actual installation and curated import checks; it does not synchronize the host environment. An empty contract or unsupported backend is a validation failure. Dry runs perform no verification and are not proof of a working environment.

`--json` emits one versioned document on stdout. `--sarif` is only supported for check/diagnose. The audit command reads existing state without creating a database. Tools/doctor currently report uv capability only. No env, lock, export or MCP command is implemented.
