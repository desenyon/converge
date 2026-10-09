# Contributing

Read [AGENTS.md](AGENTS.md), [current state](docs/CURRENT_STATE.md), and the [testing guide](docs/development/testing.md). Preserve crate boundaries and typed public contracts. Add a regression test before fixing behavior, validate with real offline fixtures where possible, and document supported scope without claiming unimplemented guarantees.

Use an isolated branch, keep fixtures free of real credentials, run formatting/Clippy/workspace tests and the relevant acceptance checks, and submit a pull request. Changes to storage tables require forward migrations and migration tests. See the README for the complete local and hosted quality gates.
