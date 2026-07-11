# Handoff

## Session summary

The disposable legacy Python implementation was replaced with a Rust 2024 workspace following `AGENTS.md`. The verified vertical slice implements discovery through solve, including authoritative uv validation, atomic host application, fresh environment synchronization, audit persistence, and undo. A single Bash installer now provisions system tools, Rust 1.96, uv, Converge, persistent PATH configuration, and final command verification on macOS and Linux.

## Publication

The Rust rebuild is published through the `codex/converge-rust-rebuild` branch. Each newly created or materially edited file has an individual commit; the intentional disposable-legacy removal is consolidated into one cleanup commit.

## Important paths

- `crates/converge-cli/src/main.rs`: CLI and solve state machine
- `crates/converge-model/src/lib.rs`: stable contracts
- `crates/converge-discovery/src/lib.rs`: Python evidence
- `crates/converge-planner/src/lib.rs`: diagnostics and plans
- `crates/converge-sandbox/src/lib.rs`: isolated candidate validation
- `crates/converge-executor/src/transaction.rs`: apply, environment, rollback, undo
- `schemas/`: machine contracts
- `fixtures/python/`: acceptance evidence
- `install.sh`: complete macOS/Linux source-bootstrap installer
- `tests/installer.bash`: hermetic installer acceptance test

## Verified results

Formatting, warning-denied clippy, all workspace tests, real uv solve/undo acceptance, RustSec audit, cargo-deny advisories/licenses/bans/sources, workspace packaging, and installer acceptance complete. The previous publication CI matrix passed on Linux, macOS, and Windows.

## Unverified assumptions

The new installer has been exercised hermetically on macOS ARM64. Its Linux package-manager branches require the pending hosted CI run; cargo-dist release generation remains unverified.

## Next three tasks

1. Add Poetry, Conda, and Python workspace fixtures and read-only discovery.
2. Add format-specific repair adapters only after authoritative uv validation succeeds.
3. Generate and verify the cargo-dist release workflow on GitHub.
