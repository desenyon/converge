# Repair, sandbox, and rollback

A repair is a `RepairPlan` containing ordered typed `RepairAction` values. Free-form shell text is never a repair action.

Validation copies the repository to a temporary directory, applies format-preserving TOML edits, invokes uv directly, checks the lock, and performs a frozen synchronization dry run. The exact validated files are retained until application finishes.

Application rechecks the source fingerprint, snapshots every affected file, writes through a cross-platform atomic replacement primitive, creates a fresh frozen environment, appends audit state, and records `.converge/last_applied`. A prior `.venv` is moved into the snapshot and restored by `converge undo`.
