# Handoff

## Session

Transactional Python/uv hardening on `improvement/transactional-workflows`, based on main commit `b57be4a`. Work is isolated in this task's clone; no other repository was edited.

## Important paths

- `crates/converge-executor/src/transaction.rs`: ApplicationTransaction, locks, unique attempts, journal and rollback/undo.
- `crates/converge-executor/src/lib.rs`: bounded async uv execution, environment scoping and timeouts.
- `crates/converge-sandbox/src/lib.rs`: real required/advisory verification, copy fingerprint checks.
- `crates/converge-planner/src/lib.rs`: project diagnostics, supported-target gating and policy-bound plans.
- `crates/converge-core/src/config.rs`: strict typed configuration validation.
- `crates/converge-cli/src/main.rs`: policy-aware plan/verify/solve/apply workflow and audit payloads.
- `crates/converge-store/src/lib.rs`: one SQLite graph/application-audit transaction.
- New hardening/process/offline/transaction tests and README/design documentation.

## Validation procedure

Run formatting, workspace Clippy with warnings denied, all default workspace tests, the ignored public-registry acceptance test, a release build, rustdoc with warnings denied, and installer syntax/acceptance checks. Use two Cargo jobs. Hosted CI additionally owns nextest, audit, deny, machete, coverage and cross-platform checks.

The default suite is offline with respect to package indexes. It still requires uv and a locally installed compatible Python. The ignored network acceptance is explicitly run in CI and uses a temporary uv cache. Public output schemas and SQLite tables are unchanged.

## Remaining product limitations

The README, threat model and limitations document explain supported execution scope, incomplete OS isolation, separate filesystem/database commit points, lack of undo audit/graph refresh, basic redaction, and retained snapshots. No merge, release, deployment or security-setting change is part of this branch.

## Next work

1. Review the exact pushed branch and its CI results.
2. Add auditable recovery lifecycle and stronger crash-commit recovery.
3. Expand authoritative dependency/source fixtures before enabling alternate backends.

## Verified local evidence

- Default workspace suite: 55 passed, 0 failed; the one network acceptance test is intentionally separate.
- Explicit public-registry acceptance: 1 passed, repairing/installing/importing httpx and rich, auditing and undoing.
- `cargo fmt`, all-target/all-feature Clippy with warnings denied, release build, and rustdoc with warnings denied: passed.
- Bash installer syntax and hermetic installer acceptance: passed.
- Release-binary offline smoke: plan → apply exact plan ID → verify → undo, with no host environment/lock left afterward: passed.
- Modified Markdown local-link check, diff whitespace check and targeted accidental credential/host-path scan: passed.

Local tools were Rust/Cargo 1.99.0 and uv 0.11.6; the workflow independently pins Rust 1.96.0 and uv 0.11.28. Hosted CI status is reported with the pushed commit/PR rather than inferred here.
