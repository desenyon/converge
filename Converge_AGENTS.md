# AGENTS.md

# Converge

## Mission

Build Converge from an empty repository as a production grade, local first dependency intelligence and environment convergence system.

Converge must inspect an unfamiliar software repository, detect its languages, operating system assumptions, runtimes, package managers, manifests, lockfiles, imports, build tools, services, containers, workspaces, and native requirements. It must construct a unified dependency model, diagnose inconsistencies, compute the safest repair plan, validate that plan in isolation, create a reproducible environment, install the project, run verification, and explain every decision.

The primary user experience is:

```bash
converge solve .
```

The command should take a repository from unknown or broken state to the safest verified working state that Converge can produce.

Converge is part of Concatenate. It must meet Concatenate standards for correctness, evidence, reproducibility, explainability, modularity, and long term technical defensibility.

## Fresh repository rule

Assume the repository is empty or disposable.

Do not preserve legacy architecture merely because an earlier implementation existed.

Do not recreate the old Python only design.

Build the system from first principles around the contracts in this file.

Before implementing any major dependency, confirm its current maintenance status, license, security posture, platform support, and stable release. Use the newest stable compatible versions and commit the resulting lockfiles.

## Product definition

Converge is not a package installer and not a dependency graph viewer.

It is a repository scoped reasoning system with six responsibilities:

1. Discover the real project and host environment.
2. Normalize heterogeneous dependency evidence.
3. Build a versioned dependency and requirement graph.
4. Diagnose conflicts, drift, missing requirements, and uncertainty.
5. Plan and validate minimal safe repairs.
6. Produce a reproducible working environment with an auditable explanation.

## Nonnegotiable product guarantees

1. Every operation is scoped to an explicit target repository.
2. Read only analysis is the default.
3. No host repository mutation occurs before isolated validation succeeds.
4. Every mutation is represented as a typed plan before application.
5. Every applied change is atomic, auditable, and reversible.
6. Raw evidence remains available for every diagnosis and repair.
7. Uncertainty is surfaced rather than converted into false confidence.
8. The same repository state and configuration produce deterministic plans.
9. Network access is explicit and recorded.
10. External tools are used through replaceable adapters.
11. The core never depends on an AI model for correctness.
12. LLM assistance may explain or propose, but deterministic validation decides.
13. Converge must work locally without a cloud account.
14. Converge must expose stable machine readable output for agents and CI.
15. The common path must remain one command.

# Architecture decision

## Primary implementation language

Build the core, CLI, planner, graph engine, scanner coordinator, sandbox controller, and transaction system in stable Rust using Rust edition 2024.

Reasons:

1. Fast startup and low steady memory use.
2. Safe concurrent filesystem and process handling.
3. Reliable distribution as one native binary.
4. Strong typed domain models.
5. Good support for parsers, graphs, databases, archives, and process isolation.
6. Easier embedding into future Cerebrum and agent runtimes.

Python is a target ecosystem and optional extension language, not the implementation language of the core.

## Runtime model

Converge is one native CLI binary with an internal asynchronous task runtime.

The first release must not require a daemon, server, browser interface, or cloud service.

Long running scans may later use an optional local daemon, but all core commands must work without it.

## Core stack

Use the following architecture unless a measured experiment proves a superior choice.

### Rust platform

1. Rust stable, edition 2024.
2. Cargo workspace.
3. Tokio for bounded asynchronous process and filesystem coordination.
4. Clap for the CLI contract.
5. Serde for typed serialization.
6. Thiserror for library errors.
7. Miette for human readable diagnostics.
8. Tracing and tracing subscriber for structured telemetry.
9. Rayon only for CPU bound parsing where it measurably helps.
10. Reqwest with rustls for controlled network access.
11. Semver and PEP 440 compatible domain types rather than ad hoc string comparison.
12. Tempfile for ephemeral validation workspaces.
13. Fs2 or platform appropriate locking for repository state.
14. Blake3 for content and state fingerprints.
15. Time for explicit UTC timestamps.

Do not add a framework when a small typed module is sufficient.

### Storage

Use SQLite in WAL mode for repository local state.

Use SQLx with compile time checked queries or rusqlite with explicit migrations. Pick one during bootstrap and document the decision. Prefer the choice that gives the strongest migration discipline and simplest static binary distribution.

Repository state lives under:

```text
.converge/
  state.db
  cache/
  logs/
  plans/
  snapshots/
  sandboxes/
  exports/
```

The database is a derived local index. Original repository files remain canonical evidence.

Every schema change requires a forward migration and a migration test.

### Parsing and code intelligence

Use a layered parser system.

1. Native structured parsers for manifests and lockfiles.
2. Tree sitter for language agnostic syntax and import extraction.
3. Ecosystem specific analyzers when they provide materially better semantics.
4. SCIP ingestion when a repository already provides an index or a supported indexer can create one.
5. Regex only for tightly bounded fallback detection, never as the primary parser for structured files.
6. Git history for temporal and ownership evidence.
7. Build and test output for behavioral evidence.

Initial language support must prioritize Python, then JavaScript and TypeScript, Rust, and container or system configuration.

The plugin boundary must allow additional ecosystems without changing the core graph model.

### Python environment execution

Use uv as the authoritative Python environment and package execution backend.

Converge must call the installed uv binary through a typed adapter and parse its machine readable outputs where available.

Do not reimplement uv installation, lock generation, virtual environment creation, wheel building, or package downloading.

Required Python behavior:

1. Detect compatible Python versions.
2. Install a required Python version through uv when permitted.
3. Create `.venv` in the target repository.
4. Generate or verify `uv.lock`.
5. Run `uv sync --frozen` when a valid lock exists.
6. Resolve and lock when no valid lock exists.
7. Import constraints from `pyproject.toml`, requirements files, Poetry, pip tools, and Conda evidence.
8. Avoid destructive migration of source manifests unless the repair plan explicitly includes it.
9. Support a dry run that produces the complete proposed plan.
10. Record the exact uv version and every command executed.

### Constraint solving

Separate package resolution from repair planning.

Package resolution answers whether a candidate manifest can be resolved.

Repair planning answers which repository changes produce the safest valid state.

Use:

1. uv for Python package resolution.
2. Native ecosystem tools for other package ecosystems.
3. A Converge planning engine for cross source constraints and repair selection.
4. Resolvo or a maintained PubGrub implementation for explainable dependency constraints when appropriate.
5. An optional SMT adapter, initially Z3, only for cross ecosystem or multi objective plans that cannot be represented cleanly in the simpler solver.

The core planner must expose an internal solver trait so implementations remain replaceable.

Do not make Z3 mandatory for the first useful binary unless benchmarks prove it necessary.

### Graph engine

Implement a typed property graph over SQLite tables, not an opaque graph database.

Use petgraph for in memory algorithms.

The graph must support:

1. Nodes with stable identifiers.
2. Typed edges.
3. Evidence references.
4. Confidence and certainty classes.
5. Observation time.
6. Validity range when known.
7. Source location.
8. Ecosystem and platform scope.
9. State fingerprints.
10. Supersession relationships.

Initial node types:

1. Repository
2. Workspace
3. Project
4. File
5. Manifest
6. Lockfile
7. Package
8. PackageVersion
9. Module
10. Symbol
11. Runtime
12. Toolchain
13. OperatingSystem
14. Architecture
15. SystemPackage
16. Service
17. ContainerImage
18. BuildTarget
19. TestTarget
20. EnvironmentVariable
21. RepairPlan
22. VerificationRun

Initial edge types:

1. Declares
2. ResolvesTo
3. Imports
4. Calls
5. Contains
6. Requires
7. ConflictsWith
8. Supersedes
9. Provides
10. Builds
11. Tests
12. RunsOn
13. GeneratedBy
14. ObservedDuring
15. AffectedBy
16. ValidatedBy
17. ProposedBy
18. DerivedFrom

### Sandbox and isolation

Validation must happen outside the host repository mutation path.

Implement a sandbox abstraction with platform specific backends.

Priority order:

1. Temporary filesystem copy or reflink clone for universal support.
2. Git worktree when safe and available.
3. Container backend when a repository already defines a container or the user requests one.
4. macOS sandbox and Linux namespace based hardening when available.
5. No privileged operations by default.

A validation sandbox receives:

1. Immutable source snapshot identifier.
2. Proposed file changes.
3. Environment configuration.
4. Network policy.
5. Time limit.
6. Disk limit.
7. Process limit.
8. Command allowlist.
9. Expected verification contract.

The sandbox returns a structured verification report.

### Security and supply chain

Integrate security checks through adapters.

Initial adapters:

1. OSV Scanner for known vulnerabilities.
2. cargo audit for Rust lockfiles.
3. npm audit or a safer registry advisory adapter for Node projects.
4. pip audit or OSV data for Python environments.
5. gitleaks for secret detection before logs or snapshots are persisted.
6. Syft for optional SBOM generation.
7. CycloneDX and SPDX export formats.

Security findings do not automatically force upgrades. They become constraints and risks inside the repair plan.

Any external binary must be version detected, capability checked, and invoked without shell interpolation.

# Repository structure

Create this workspace:

```text
converge/
  AGENTS.md
  README.md
  LICENSE
  SECURITY.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  CHANGELOG.md
  Cargo.toml
  Cargo.lock
  rust-toolchain.toml
  deny.toml
  typos.toml
  justfile
  .editorconfig
  .gitignore
  .github/
    workflows/
    ISSUE_TEMPLATE/
    pull_request_template.md
  crates/
    converge-cli/
    converge-core/
    converge-model/
    converge-store/
    converge-discovery/
    converge-graph/
    converge-planner/
    converge-sandbox/
    converge-executor/
    converge-report/
    converge-telemetry/
    converge-mcp/
    converge-testkit/
  plugins/
    python/
    node/
    rust/
    system/
    containers/
  schemas/
    output/
    config/
    events/
  fixtures/
    python/
    node/
    rust/
    polyglot/
    broken/
  tests/
    acceptance/
    compatibility/
    performance/
    security/
  docs/
    architecture/
    commands/
    formats/
    decisions/
    development/
    CURRENT_STATE.md
    ROADMAP.md
    HANDOFF.md
    FAILURE_LOG.md
  scripts/
    bootstrap/
    release/
    fixtures/
  benches/
    scan/
    graph/
    planner/
    solve/
```

## Crate responsibilities

### converge model

Contains stable domain types only.

No filesystem, network, database, CLI, or process code.

### converge core

Contains use case orchestration, service traits, policy, and transactions.

It depends on abstractions, not concrete adapters.

### converge store

Owns SQLite migrations, repositories, caching, snapshots, and state locking.

### converge discovery

Finds repository boundaries, host capabilities, toolchains, manifests, workspaces, and project topology.

### converge graph

Builds and queries the typed dependency graph and runs graph algorithms.

### converge planner

Converts diagnoses into ranked candidate repair plans and coordinates solver adapters.

### converge sandbox

Creates isolated validation environments and enforces resource policies.

### converge executor

Invokes uv and other external tools through typed process adapters.

### converge report

Produces terminal, JSON, SARIF, CycloneDX, SPDX, and explanation outputs.

### converge telemetry

Provides local structured traces and opt in OpenTelemetry export.

Telemetry is disabled by default.

### converge mcp

Exposes read only analysis and explicit plan or apply tools through MCP.

It must never make mutation less explicit.

### converge testkit

Provides fixture builders, fake registries, fake toolchains, deterministic clocks, and sandbox test helpers.

# Stable domain contracts

Define versioned schemas before broad implementation.

## DiscoverySnapshot

Contains:

1. Repository identity.
2. Source fingerprint.
3. Host operating system.
4. Host architecture.
5. Detected runtimes.
6. Detected package managers.
7. Manifests.
8. Lockfiles.
9. Workspaces.
10. Source roots.
11. Imported modules.
12. System requirements.
13. Build and test commands.
14. Evidence and confidence for each detection.
15. Warnings and unresolved ambiguities.

## Diagnostic

Contains:

1. Stable diagnostic identifier.
2. Type.
3. Severity.
4. Affected entities.
5. Evidence.
6. Explanation.
7. Confidence.
8. Possible consequences.
9. Candidate repair actions.
10. Whether the finding blocks environment creation.

## RepairAction

Use typed variants such as:

1. AddDependency
2. RemoveDependency
3. ChangeConstraint
4. SelectRuntime
5. InstallRuntime
6. GenerateLockfile
7. RefreshLockfile
8. CreateEnvironment
9. AddSystemRequirement
10. ModifyWorkspace
11. ReplaceSource
12. AddConfiguration
13. RunMigration
14. NoChange

No repair is represented as free form shell text.

## RepairPlan

Contains:

1. Plan identifier.
2. Source snapshot.
3. Objective.
4. Actions.
5. Dependency ordering.
6. Expected resulting state.
7. Assumptions.
8. Unresolved uncertainty.
9. Estimated risk.
10. Reversibility.
11. Network requirements.
12. File diff preview.
13. Verification contract.
14. Solver explanation.
15. Alternative plans and rejection reasons.

## VerificationContract

Contains:

1. Environment creation checks.
2. Lock consistency checks.
3. Import checks.
4. Build checks.
5. Test commands.
6. Type checks.
7. Lint checks.
8. Security checks.
9. Timeout policy.
10. Required versus advisory checks.

## SolveReport

Contains:

1. Discovery summary.
2. Diagnostics.
3. Selected plan.
4. Alternatives.
5. Sandbox results.
6. Applied changes.
7. Environment details.
8. Verification results.
9. Audit record.
10. Exact reproduction commands.

# CLI contract

Use a concise noun and verb model.

## Primary commands

```bash
converge solve [PATH]
converge check [PATH]
converge explain [PATH] [SUBJECT]
converge verify [PATH]
converge undo [PATH]
```

## Advanced commands

```bash
converge discover [PATH]
converge graph [PATH]
converge diagnose [PATH]
converge plan [PATH]
converge apply [PATH] PLAN_ID
converge env [PATH]
converge lock [PATH]
converge audit [PATH]
converge export [PATH]
converge tools
converge doctor
converge mcp serve
```

## `converge solve`

`converge solve .` executes:

1. Resolve the target repository.
2. Acquire a repository state lock.
3. Inspect the host.
4. Discover projects and workspaces.
5. Parse dependency evidence.
6. Build or update the graph.
7. Diagnose inconsistencies.
8. Generate candidate repair plans.
9. Rank plans by correctness, minimality, compatibility, security, reversibility, and cost.
10. Show the plan unless automatic application is explicitly allowed.
11. Create an isolated sandbox.
12. Apply the plan inside the sandbox.
13. Create the environment with uv when Python is present.
14. Install dependencies.
15. Execute the verification contract.
16. Compare resulting graph state with the expected state.
17. Atomically apply validated file changes to the host repository.
18. Create or synchronize the host `.venv`.
19. Run final lightweight verification.
20. Append the audit event.
21. Print reproduction and undo commands.

Default behavior may ask for confirmation before mutation.

`--yes` permits noninteractive application of a fully validated plan.

`--dry-run` performs every safe stage through plan generation and prints expected commands without mutation.

`--offline` prohibits network access.

`--frozen` prohibits lockfile changes.

`--json` emits only schema versioned JSON on standard output.

`--explain` includes the complete solver rationale.

## Exit codes

Use stable documented codes:

```text
0 success
1 issues detected but no command failure
2 invalid invocation or configuration
3 discovery failure
4 unsatisfied constraints
5 validation failure
6 mutation failure with rollback completed
7 rollback failure
8 required external tool unavailable
9 network prohibited or unavailable
10 internal invariant violation
```

Never overload one code with unrelated meanings.

# Automatic detection requirements

## Host detection

Detect:

1. Operating system and release.
2. Architecture.
3. Libc variant where relevant.
4. Shell.
5. Available package managers.
6. Installed compilers.
7. Installed runtimes.
8. Container environment.
9. CI environment.
10. Network availability only when needed.
11. Filesystem capabilities such as reflinks and case sensitivity.
12. Available disk space.
13. Permission boundaries.

## Repository detection

Detect:

1. Git root.
2. Nested repositories.
3. Monorepo roots.
4. Workspace definitions.
5. Language distribution.
6. Source and test roots.
7. Generated files.
8. Vendored directories.
9. Ignored paths.
10. CI workflows.
11. Build systems.
12. Container definitions.
13. Task runners.
14. Documentation that defines setup commands.
15. Previous Converge state.

## Python detection

Support:

1. `pyproject.toml`
2. `uv.lock`
3. `requirements.txt`
4. `requirements.in`
5. Constraints files
6. Poetry lockfiles and configuration
7. pip tools output
8. `setup.py`
9. `setup.cfg`
10. Conda environment files
11. PEP 723 inline script metadata
12. Workspace members
13. Dependency groups
14. Extras
15. Direct URLs
16. Git dependencies
17. Local path dependencies
18. Platform markers
19. Python version constraints
20. Compiled extension requirements
21. Static, dynamic, and type checking imports

Normalize names according to Python packaging rules.

Map import names to distributions using installed metadata, package indexes, curated mappings, and evidence. Never assume that import name and distribution name are identical.

# Planning objective

Rank plans using a transparent multi objective score.

Order of importance:

1. Satisfies hard constraints.
2. Passes the verification contract.
3. Preserves declared project intent.
4. Minimizes file and dependency changes.
5. Preserves lockfile reproducibility.
6. Preserves supported runtime range.
7. Reduces known security risk.
8. Avoids unnecessary major upgrades.
9. Minimizes network and build work.
10. Maximizes reversibility.
11. Minimizes uncertainty.

Never optimize only for newest versions.

The safest correct version is preferred over the newest version.

# Mutation protocol

Every host mutation uses this transaction:

1. Confirm the current source fingerprint matches the plan.
2. Create a recoverable snapshot.
3. Write all new content to temporary sibling files.
4. Fsync when supported.
5. Atomically replace files.
6. Synchronize the environment.
7. Run final checks.
8. Commit the audit event.
9. Retain rollback metadata.

If any step fails, restore the previous repository files and report the exact state.

Do not edit user source files to make tests pass unless the selected plan explicitly represents a source migration and the user approved it.

# Audit model

Use an append only event log inside SQLite plus exportable JSON Lines.

Record:

1. Tool version.
2. Schema version.
3. Timestamp.
4. Actor mode.
5. Repository fingerprint before and after.
6. Command.
7. Configuration.
8. Discovered evidence.
9. Diagnostics.
10. Candidate plans.
11. Selected plan.
12. External commands.
13. Network endpoints contacted.
14. File diffs.
15. Validation results.
16. Applied changes.
17. Rollback data.
18. Final result.

Sensitive values and secrets must be redacted before persistence.

# Open source integration policy

Open source tools may be embedded, invoked, forked, patched, or replaced when they improve correctness or time to value.

For each adopted component:

1. Record the license.
2. Record the exact version or commit.
3. Identify the adapter boundary.
4. Add a conformance test.
5. Document why it is used.
6. Confirm that it does not control Converge domain semantics.
7. Avoid a hard dependency when an external executable adapter is sufficient.
8. Upstream generally useful fixes where practical.
9. Maintain a patch file or fork note for custom changes.
10. Provide a replacement path.

Likely integrations include uv, Tree sitter, SCIP tools, ast grep, OSV Scanner, Syft, gitleaks, cargo metadata, npm or pnpm, Docker or Podman, and platform package query tools.

Do not combine tools into an untestable shell pipeline.

# Agent and MCP integration

Converge must be usable by coding agents without requiring screen scraping.

Expose:

1. `discover_repository`
2. `get_dependency_graph`
3. `list_diagnostics`
4. `create_repair_plan`
5. `explain_repair_plan`
6. `validate_repair_plan`
7. `apply_repair_plan`
8. `get_verification_report`
9. `get_change_impact`
10. `undo_last_change`

Read operations may run without approval.

Mutation tools require an explicit plan identifier and confirmation token.

Every tool response includes schema version, source fingerprint, evidence, uncertainty, and next safe actions.

# Testing strategy

No feature is complete without tests at the correct level.

## Unit tests

Use for:

1. Manifest parsing.
2. Version normalization.
3. Graph transformations.
4. Scoring.
5. Plan construction.
6. Redaction.
7. Configuration merging.
8. Error classification.

## Property tests

Use proptest for:

1. Graph serialization round trips.
2. Deterministic plan ordering.
3. Version constraint normalization.
4. Transaction rollback.
5. Path scoping.
6. Parser robustness.
7. Idempotent repeated scans.

## Integration tests

Use hermetic fixtures with fake registries and fake tool binaries.

Test:

1. Discovery.
2. uv execution.
3. Sandbox creation.
4. Lockfile generation.
5. Plan validation.
6. Atomic application.
7. Rollback.
8. JSON output.
9. MCP contracts.

## Acceptance tests

Run the native binary against representative repositories.

Required fixture classes:

1. Clean uv project.
2. Missing Python dependency.
3. Wrong import to distribution mapping.
4. Stale uv lockfile.
5. Incompatible Python range.
6. Poetry project.
7. pip tools project.
8. Conda project.
9. Local path dependency.
10. Git dependency.
11. Python monorepo.
12. Python and Node polyglot repository.
13. Native extension requiring a compiler.
14. Project with a Dockerfile.
15. Project with contradictory manifests.
16. Project with no tests.
17. Malicious or malformed manifest.
18. Offline environment.

## Differential tests

Compare Converge results against native ecosystem tools.

For Python:

1. uv lock.
2. uv sync.
3. Installed metadata.
4. Import execution.

Converge must never claim a resolution that the authoritative ecosystem backend rejects.

## Performance tests

Establish budgets for:

1. Cold startup.
2. Incremental scan.
3. Full scan.
4. Graph query.
5. Plan generation.
6. JSON serialization.
7. Memory use.

Track regressions in CI.

## Mutation safety tests

Inject failures after every transaction step and prove rollback correctness.

This is mandatory before enabling automatic application.

# CI and quality gates

Use GitHub Actions on Linux, macOS, and Windows.

Required checks:

1. `cargo fmt --check`
2. `cargo clippy --workspace --all-targets --all-features -- -D warnings`
3. `cargo test --workspace --all-features`
4. `cargo nextest run --workspace`
5. `cargo deny check`
6. `cargo audit`
7. `cargo machete`
8. `cargo llvm-cov` with a justified threshold
9. Schema compatibility tests
10. Fixture acceptance tests
11. Installer tests
12. Generated documentation checks
13. Secret scanning
14. License checks

Use cargo dist for release artifacts if it remains the best maintained option at implementation time.

Use signed checksums and provenance attestations for releases.

# Configuration

Support configuration in this precedence order:

1. CLI flags.
2. Environment variables prefixed with `CONVERGE_`.
3. `.converge.toml`.
4. `[tool.converge]` where the manifest format supports it.
5. User configuration.
6. Built in defaults.

Configuration must be typed, validated, explainable, and printable through:

```bash
converge config explain
```

# Documentation requirements

Before the first release, document:

1. Architecture.
2. Threat model.
3. Data model.
4. Plan model.
5. Sandbox model.
6. Mutation and rollback guarantees.
7. Supported ecosystems.
8. External tool behavior.
9. JSON schemas.
10. MCP tools.
11. Installation.
12. Troubleshooting.
13. Limitations.
14. Privacy.
15. Security reporting.

Do not document a capability before an acceptance test proves it.

# Observability

Use structured tracing internally.

Each solve run receives a unique run identifier.

Every stage records duration, cache result, evidence count, graph changes, solver result, subprocess status, and validation result.

Default logs remain local.

No telemetry leaves the machine without explicit opt in.

# Implementation phases

## Phase 0: Contracts and bootstrap

Create:

1. Cargo workspace.
2. Domain model.
3. Error taxonomy.
4. Configuration model.
5. JSON schemas.
6. SQLite migration framework.
7. CLI skeleton.
8. Fixture testkit.
9. CI.
10. Architecture decision records.

Exit criterion:

The empty repository builds, tests, lints, packages, and emits versioned JSON for a no operation discovery command.

## Phase 1: Python discovery

Implement:

1. Repository root detection.
2. Host detection.
3. Python manifests.
4. uv lock parsing.
5. Requirements and constraints parsing.
6. Python source import extraction.
7. Import to distribution evidence.
8. Typed graph persistence.
9. Incremental fingerprints.
10. `converge discover`.
11. `converge graph`.
12. `converge check`.

Exit criterion:

Converge accurately models clean and broken Python fixtures without mutating them.

## Phase 2: Diagnosis and explanation

Implement:

1. Missing dependency diagnosis.
2. Unused dependency diagnosis.
3. Lock drift.
4. Python version conflicts.
5. Incompatible constraints.
6. Local path failures.
7. System requirement warnings.
8. Evidence backed explanations.
9. Stable JSON and SARIF.
10. `converge explain`.

Exit criterion:

Every diagnostic traces to raw evidence and matches expected fixture results.

## Phase 3: Repair planning

Implement:

1. Typed actions.
2. Candidate generation.
3. Solver adapter.
4. Multi objective ranking.
5. Plan preview.
6. Alternative plan comparison.
7. Deterministic planning.
8. `converge plan`.

Exit criterion:

Broken fixtures receive minimal valid plans that authoritative backend dry runs accept.

## Phase 4: Sandbox validation

Implement:

1. Snapshot creation.
2. Sandbox backend.
3. uv adapter.
4. Environment creation.
5. Install.
6. Import checks.
7. Project verification discovery.
8. Resource limits.
9. Structured reports.
10. `converge verify`.

Exit criterion:

A candidate plan cannot reach the host mutation stage unless its complete required verification contract passes.

## Phase 5: Transactional application

Implement:

1. Confirmation flow.
2. Atomic file updates.
3. Host `.venv` synchronization.
4. Audit event.
5. Rollback.
6. `converge apply`.
7. `converge undo`.

Exit criterion:

Failure injection proves that every interrupted mutation either completes fully or restores the prior repository state.

## Phase 6: One command solve

Implement the complete `converge solve .` state machine.

Exit criterion:

On the acceptance fixture suite, one command discovers, plans, validates, applies, installs, verifies, and explains with no manual command chaining.

## Phase 7: Polyglot expansion

Add Node, Rust, containers, and system package evidence through plugins.

Do not begin this phase until the Python path is reliable and measured.

## Phase 8: Agent integration and impact analysis

Add MCP, graph impact queries, test selection, and Cerebrum integration contracts.

# First release scope

Version 0.1 must support Python repositories exceptionally well.

It must include:

1. Native binary CLI.
2. Automatic repository and host detection.
3. Python manifest and lock parsing.
4. Source import analysis.
5. Unified graph.
6. Deterministic diagnostics.
7. Ranked repair plans.
8. uv environment creation.
9. Sandbox validation.
10. Atomic apply.
11. Undo.
12. JSON output.
13. Local audit.
14. Linux, macOS, and Windows support.
15. Installer and release binaries.

Do not delay 0.1 for a web interface, cloud service, broad ecosystem catalog, LLM features, or enterprise administration.

# Success metrics

Measure:

1. Percentage of broken fixtures correctly diagnosed.
2. Percentage repaired without unnecessary changes.
3. Environment creation success.
4. Verification pass rate.
5. Rollback success under injected failures.
6. False positive diagnostic rate.
7. Median cold solve time.
8. Median incremental check time.
9. Percentage of decisions with complete evidence.
10. Percentage of plans reproduced from audit data.

The core metric is:

```text
Verified repositories repaired correctly per attempted solve
```

# Engineering workflow for coding agents

At the beginning of every session:

1. Read `AGENTS.md`.
2. Read `docs/CURRENT_STATE.md`.
3. Read `docs/ROADMAP.md`.
4. Inspect Git status.
5. Inspect recent commits.
6. Run the smallest relevant test set.
7. Identify the next unblocked phase exit criterion.

During implementation:

1. State the invariant being implemented.
2. Write or update the failing test first.
3. Implement the smallest coherent vertical slice.
4. Run targeted tests.
5. Run affected integration tests.
6. Update schemas and docs when contracts change.
7. Record failures in `docs/FAILURE_LOG.md`.
8. Commit only verified work.

Before claiming completion:

1. Run formatting.
2. Run clippy with warnings denied.
3. Run relevant unit tests.
4. Run relevant integration tests.
5. Run acceptance tests for the changed path.
6. Verify JSON schema compatibility.
7. Verify no secret or machine specific path was committed.
8. Update `docs/CURRENT_STATE.md`.

# Handoff protocol

Maintain `docs/CURRENT_STATE.md` with:

1. Active phase.
2. Active invariant.
3. Completed work.
4. Tests passing.
5. Known failures.
6. Architectural decisions.
7. Changed schemas.
8. Immediate next task.
9. Exact first command for the next agent.

Maintain `docs/HANDOFF.md` with:

1. Session summary.
2. Branch and commit.
3. Important paths.
4. Commands run.
5. Verified results.
6. Unverified assumptions.
7. Blockers.
8. Next three tasks.

When session capacity is low, stop starting new work, stabilize the repository, run focused tests, update both files, commit, and push.

# Prohibited shortcuts

1. Do not implement the product as shell scripts.
2. Do not use an LLM to decide whether a dependency graph is valid.
3. Do not mutate before validation.
4. Do not hide subprocess output needed for diagnosis.
5. Do not parse TOML, JSON, YAML, or lockfiles with regular expressions.
6. Do not assume the current working directory is the target repository.
7. Do not assume imports map directly to package names.
8. Do not silently upgrade major versions.
9. Do not delete user configuration to obtain a clean solve.
10. Do not claim cross platform support without CI and acceptance tests.
11. Do not add cloud infrastructure before the local product works.
12. Do not make external integrations part of core semantics.
13. Do not accept nondeterministic plan ordering.
14. Do not store secrets in logs, snapshots, or traces.
15. Do not bypass failing verification with an automatic force flag.
16. Do not optimize for feature count over repair correctness.

# Immediate execution sequence

Begin from the empty repository.

1. Initialize the Rust 2024 Cargo workspace.
2. Create the crate boundaries listed above.
3. Add formatting, linting, testing, dependency policy, and CI.
4. Define the versioned domain contracts.
5. Define SQLite migration version 1.
6. Implement explicit target path resolution.
7. Implement host and repository discovery.
8. Implement Python `pyproject.toml` and `uv.lock` parsing.
9. Implement Python source import extraction.
10. Persist the first typed dependency graph.
11. Implement `converge discover .`.
12. Implement `converge check .`.
13. Add clean and broken Python fixtures.
14. Implement the uv adapter.
15. Implement repair plan generation.
16. Implement sandbox validation.
17. Implement transactional apply and undo.
18. Connect the complete `converge solve .` flow.
19. Measure results against the acceptance suite.
20. Do not expand scope until the Python solve path is reliable.

# Definition of done

Converge is ready for an initial public release when:

1. A new user can install one native binary.
2. `converge solve .` automatically understands a supported Python repository.
3. The system identifies broken dependency and environment state with evidence.
4. It generates a minimal deterministic repair plan.
5. It validates that plan in isolation.
6. It creates and installs a reproducible uv environment.
7. It applies only validated changes.
8. It explains all decisions.
9. It can undo the applied repair.
10. It passes the full cross platform acceptance suite.
11. It emits stable machine readable output.
12. No correctness claim depends on an LLM.
