# Commands

Primary commands:

```text
converge solve [PATH] [--dry-run] [--yes] [--offline] [--frozen] [--json]
converge check [PATH] [--json|--sarif]
converge explain [PATH] [--json]
converge verify [PATH] [--json]
converge undo [PATH] [--json]
```

Advanced implemented commands are `discover`, `graph`, `diagnose`, `plan`, `apply`, `tools`, `doctor`, and `config explain`.

`solve` does not mutate unless `--yes` is present. `--dry-run` stops after deterministic planning. `--offline` is passed to every uv invocation. `--frozen` rejects plans that require lockfile changes.
