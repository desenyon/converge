# Current limitations

Automatic execution supports one independent root PEP 621 pyproject.toml and optional root uv.lock. Poetry, Conda, requirements-only and mixed manifests, nested projects and uv workspaces are discovery-only. Parser warnings block automatic execution. Select a supported independent project directly where possible.

Only seven curated import mappings are used for automatic additions/runtime import checks. Unknown mappings are not guessed. Static diagnostics do not establish runtime usage, complete marker/version consistency, or package provenance. Version/marker lock drift not diagnosed statically fails during uv lock checking; it is not silently refreshed.

No automatic project tests, lint, type checks, security adapters, service setup, container isolation, SBOM export, Node/Rust execution, runtime downloads or MCP server are implemented. The planner is deterministic rules, not a general constraint optimizer. Local/Git dependency and native build behavior is delegated to uv and lacks comprehensive acceptance coverage.

Filesystem-copy validation is not OS isolation. There are no disk/process quotas, firewall or descendant-process kill guarantee. Dependency build hooks and import checks can run code with user privileges. Paths with symlinks are rejected. Relevant-evidence fingerprints do not include every native build input or asset.

Each file replacement is atomic, but the filesystem and SQLite are not a single commit. Journals/snapshots support recovery; there is no power-loss guarantee. Undo does not rebuild the derived graph or append an audit event. Old snapshots lack new post-apply edit protection and receipt chaining. There is no snapshot garbage collection.

No benchmark claims are made. Hosted CI results, rather than a local run, establish platform-specific validation. Release metadata and installer scripts do not prove published release assets exist.
