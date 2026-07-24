# Current state

- Active phase: first-release hardening after Phase 6
- Active invariant: no host mutation before the exact plan passes isolated uv validation
- Completed work: Rust workspace, versioned contracts, configuration provenance, SQLite migrations, Python PEP 621/uv discovery, Poetry/Conda/uv-workspace read-only discovery, Tree-sitter imports, typed graph with workspace nodes, diagnostics, deterministic plans, SARIF, sandbox validation, atomic apply, host environment synchronization, audit persistence, undo, one-command solve, and a one-command macOS/Linux bootstrap installer
- Tests passing: workspace unit/integration/acceptance suite; Poetry, Conda, and uv workspace discovery fixtures; failure injection at every transaction phase; hermetic installer installation, PATH, verification, and idempotency acceptance
- Known failures: none in the verified PEP 621 plus uv path; Poetry/Conda remain discovery-only
- Architectural decisions: Rust 2024; rusqlite with bundled SQLite; uv process adapter; Tree-sitter Python; yaml-rust2 for Conda environment files; atomic-write-file; cargo-dist release metadata
- Changed schemas: discovery snapshot now includes `workspaces` and project `backend`; output schema family remains 1.0.0, configuration schema 1.0.0, audit event schema 1.0.0
- Immediate next task: add format-specific Poetry/Conda repair adapters only after authoritative backend validation succeeds; expand pip-tools/local/Git acceptance fixtures
- Exact first command: cargo test --workspace --all-features
