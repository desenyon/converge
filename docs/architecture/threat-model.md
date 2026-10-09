# Threat model

Converge analyzes repository evidence and executes installed uv. Supported plans may install dependencies and import curated third-party modules. Both dependency build hooks and imports can execute arbitrary code with the current user's privileges. Use trusted projects or run Converge within an external container/VM.

Implemented controls:

- Explicit target resolution and copied-source fingerprint validation.
- Typed root manifest/lock edits; no free-form shell repair scripts.
- Symlink rejection during copy, transaction-path validation, and database-file checks.
- One cooperative writer lock through host mutation, checks, and audit persistence.
- Unique snapshots, a pending recovery journal, and explicit rollback errors.
- Source-change detection before apply and before undo of new committed snapshots.
- uv `--offline` for network-deny policy, bounded per-command time, bounded concurrent output capture, and null stdin.
- Forced absolute target `.venv`, removal of inherited virtual-environment/Python path overrides, and no automatic Python downloads.
- Basic secret-key line redaction in captured validation output.

Limits:

- Filesystem-copy validation separates candidate files; it is not OS isolation. Build hooks/imports can access files and network outside the copy.
- uv's offline flag does not enforce a firewall on descendants.
- Only the direct subprocess is killed/reaped on timeout; descendants are not guaranteed to terminate.
- No disk/process quotas, comprehensive secret scanner, advisory scanner, signature verification, or SBOM backend is implemented.
- Version discovery probes use two-second deadlines and 8 KiB per-stream caps. Validation retains at most a 64 KiB prefix per stream plus a truncation marker while draining both streams.
- The lock coordinates Converge writers, not other tools or hostile filesystem races.
- Original manifest snapshots are not redacted, and basic output redaction cannot detect every secret format.
- Filesystem changes and the database have separate commit points; interrupted attempts require recovery, not an assumption that a persisted audit proves final commit.
