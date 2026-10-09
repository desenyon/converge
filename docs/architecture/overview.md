# Architecture

Converge is a Rust 2024 Cargo workspace. `converge-cli` coordinates concrete adapters. `converge-model` contains I/O-free contracts; `converge-core` contains configuration, provenance, stable errors and service abstractions.

Discovery parses Python evidence, probes host tools and computes a deterministic fingerprint. The planner scopes diagnoses to project boundaries and generates supported uv repair actions. The graph crate builds stable typed nodes and edges. The sandbox copies and validates candidate content; the executor invokes uv, owns host transaction guards, and restores snapshots. The store owns rusqlite migrations, atomic graph/audit persistence and read-only audit queries. Report and telemetry crates format output and initialize local traces.

This is a rule-based planner with uv as the package resolver. General solver adapters, security integrations, additional ecosystem executors, MCP transport and broad project verification discovery remain future work. The README's [crate table](../../README.md#architecture) and [scope matrix](../../README.md#supported-behavior) describe the implemented boundaries.

Public JSON/configuration contracts remain 1.0.0. Internal snapshot metadata gains backward-compatible optional fields for prior receipts and post-apply fingerprints; new attempt directories use UUIDs. SQLite's existing graph and audit table shapes remain unchanged.
