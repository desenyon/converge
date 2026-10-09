# Changelog

## Unreleased

- Rebuilt the project from first principles as a Rust 2024 workspace.

## Unreleased — transactional workflow hardening

- Apply now holds one repository lock through file changes, host environment checks and audit persistence, with unique attempt snapshots and recoverable pending journals.
- Real uv installation/runtime validation replaces dry-run/empty success; missing locks and host environment synchronization are explicit plan actions.
- Network/timeout/automatic-application configuration is effective and malformed settings fail early; execution policy participates in plan IDs.
- Scope diagnostics to projects and refuse unsupported backend/mixed/workspace mutation.
- Bound subprocess output, add timeout and environment-path protection, preserve earlier receipts, and refuse undo over later source edits.
- Add offline/failure-injection regression coverage, separate registry acceptance, and document setup, migration and limitations.
