# Failure log

## 2026-07-10

- Rustup found a partially installed pinned 1.96.0 toolchain during bootstrap and repaired it automatically before compilation.
- The first cargo-deny run rejected unversioned internal path dependencies and MPL-2.0. Internal edges were pinned to `=0.1.0`; MPL-2.0 was explicitly accepted for the replaceable `version-ranges` parser dependency and documented in ADR 0001.
- The original Unix installer targeted a nonexistent Rust `v0.1.0` release under the wrong GitHub organization. The replacement bootstraps the pinned source ref and has a hermetic acceptance test so it cannot silently install the legacy Python release.

## Transactional hardening regressions

The starting workspace suite passed, but additional regression tests reproduced:

- Empty verification reports authorizing host mutation and empty contracts reporting success.
- Missing locks producing no generation action and environment checks using dry-run only.
- Unsupported Poetry/Conda/workspace evidence receiving root uv repair assumptions.
- Sibling projects sharing declaration evidence incorrectly.
- Applying after undo failing because snapshot names reused deterministic plan IDs.

Inspection also confirmed separately locked file/sync/undo stages, ignored execution configuration, unbounded subprocess collection, metadata failure paths and lost previous receipt state. The implementation now uses a single workflow guard, unique attempts, recovery journals, effective configuration and bounded processes. Regression tests cover these paths and actual offline uv workflows.

Local validation initially encountered sandbox DNS/cache restrictions. Dependency fetching and public-registry acceptance use explicitly approved network execution; offline fixtures use temporary writable caches. An added async sandbox test initially lacked its Tokio dev dependency; it was corrected before final validation. No credentials or downloaded package contents are committed.

Hosted Windows Clippy caught a test-only crate documentation warning because a crate-level `cfg(unix)` removed its lint allowance as well as the tests. Moving the conditional to an inner module keeps the test crate documented on every platform without disabling the lint. Linux/macOS platform jobs had already passed.
