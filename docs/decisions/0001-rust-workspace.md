# ADR 0001: Rust workspace and SQLite adapter

Status: accepted

Converge uses Rust 1.96, edition 2024, as a Cargo workspace. Stable domain contracts live in `converge-model`; orchestration depends on traits in `converge-core`; concrete adapters remain replaceable.

Repository-local derived state uses rusqlite 0.40 with bundled SQLite. This avoids build-time database access, supports explicit forward migrations, and simplifies a single native binary. SQLite is opened in WAL mode with foreign keys enabled.

The foundational crates were checked against current crates.io metadata on 2026-07-10. Tokio, Clap, Serde, rusqlite, petgraph, and reqwest are actively published, cross-platform Rust libraries under MIT or MIT/Apache-2.0 licenses. The lockfile is the exact adopted-version record. Security is checked from the resolved lockfile rather than inferred from package age.

The Python requirement parser uses `pep508_rs` behind the discovery adapter. Its transitive `version-ranges` crate is MPL-2.0; this is accepted as file-level copyleft in an unmodified dependency and does not change Converge's Apache-2.0 licensing. The dependency controls PEP syntax parsing only, not Converge planning semantics, and remains replaceable at the adapter boundary.
