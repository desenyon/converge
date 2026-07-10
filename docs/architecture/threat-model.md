# Threat model

Repository files, manifests, lockfiles, source code, dependency metadata, subprocess output, and network responses are untrusted.

Controls currently enforced:

1. Explicit canonical target directories.
2. Read-only discovery and planning.
3. Tree-sitter and structured format parsers rather than shell parsing.
4. No shell interpolation for external tools.
5. An allowlisted uv process adapter with timeouts and bounded captured output.
6. Temporary-copy validation before host mutation.
7. Source fingerprint recheck while holding a repository state lock.
8. Repository-relative path validation.
9. Atomic file replacement and recoverable snapshots.
10. Failure-injection rollback tests at every transaction phase.
11. Local-only logs and telemetry disabled by default.
12. Basic secret redaction before tool output persistence.

The filesystem-copy sandbox is isolation from host mutation, not a hostile-code security boundary. Converge 0.1 does not execute project test code automatically.
