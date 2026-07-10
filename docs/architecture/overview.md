# Architecture

Converge is one Rust 2024 native binary assembled from replaceable crates:

- `converge-model` owns stable serialized contracts and contains no I/O.
- `converge-core` owns policy, configuration precedence, and error taxonomy.
- `converge-discovery` reads repository evidence with native TOML parsers and Tree-sitter.
- `converge-graph` creates deterministic typed property graphs.
- `converge-planner` diagnoses evidence and ranks typed repairs.
- `converge-sandbox` applies candidate edits only to temporary snapshots.
- `converge-executor` invokes allowlisted tools and performs atomic host transactions.
- `converge-store` persists derived graph and append-only audit state in SQLite WAL mode.
- `converge-report` emits terminal, JSON, and SARIF output.

The core correctness path is deterministic and does not call an AI model.
