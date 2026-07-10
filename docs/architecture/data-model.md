# Data model

All machine contracts use schema version `1.0.0`. The canonical definitions are Rust types in `converge-model`; JSON schemas live under `schemas/`.

Discovery retains repository identity, source fingerprint, host facts, tools, manifests, lockfiles, Python projects, normalized PEP 508 requirements, locked packages, syntax-tree imports, raw evidence, warnings, confidence, and observation time.

The graph uses stable string identifiers and typed nodes and edges. SQLite is a derived index; repository files remain canonical.
