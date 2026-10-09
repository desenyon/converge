# Roadmap

## Implemented Python/uv vertical slice

- Versioned model, typed configuration/provenance, SQLite migrations and graph.
- Root PEP 621/uv, requirements, Poetry, Conda and workspace discovery.
- Project-scoped static diagnostics and deterministic supported repair actions.
- Temporary-copy validation with actual frozen installation and runtime/import checks.
- Single-lock host transactions, unique snapshots, failure restoration and undo/recovery.
- Local application audit, JSON/SARIF, source build and tested Bash bootstrap.

## Before broad public readiness

- Audited undo/recovery lifecycle and stronger crash consistency across filesystem/database commits.
- Additional local/Git/native dependency and version/marker-drift acceptance fixtures.
- Explicit project test/build/type/lint contracts, with honest no-tests reporting.
- OS-enforced isolation, process-tree cleanup and resource quotas.
- More import mappings supported by evidence and conservative marker/optional-import behavior.
- Snapshot retention/garbage collection and stronger sensitive-data handling.
- Cross-platform CI evidence for each change and separately validated published release assets.

## Later

- Authoritative Poetry/Conda/pip-tools mutation adapters.
- Workspace-aware execution and additional ecosystems.
- Security/SBOM adapters, MCP transport and impact analysis.

The README and current-state document describe implemented behavior; this roadmap is not a capability claim.
