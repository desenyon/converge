# Testing

Use the commands in the [README](../../README.md#development-and-tests). Set `-j 2` on Cargo builds on shared hosts. Avoid running overlapping compilation groups.

The default workspace tests require uv and an installed Python interpreter (the offline fixtures use Python >=3.11), but no package-index downloads. Real uv fixtures exercise lock generation, frozen installation, runtime checks, existing-environment backup, undo, reapplication, and relative-target scoping. Fake-tool process tests are Unix-specific; cross-platform Rust and real-uv tests run on all CI platforms.

The ignored `solve_validates_applies_installs_and_undoes` acceptance test intentionally accesses public package registries using an isolated uv cache. Run it explicitly:

```bash
cargo test -p converge-cli --test solve_e2e --locked -- --ignored
```

CI runs it separately on Linux/macOS/Windows. Cargo's `--offline` only controls Cargo dependency fetching, not subprocess networking.

Mutation tests expose named failure points for fingerprint, snapshot, candidate loading, file replacement, environment backup/synchronization and receipt publication. Additional failures exercise metadata persistence, audit callbacks, broken recovery backups, retained journals, lock contention, and undo edit protection. SQLite tests prove graph updates roll back when audit insertion fails.

Schema tests validate schema JSON/version identifiers and discovery top-level compatibility. No public schema fields change in the transactional hardening; internal metadata uses optional serde defaults for old snapshots.

Quality CI installs pinned nextest/audit/deny/machete/llvm-cov tools, checks a 65% line-coverage threshold, and runs rustdoc with warnings denied. Tool installation and platform results must be verified from the actual workflow run; local success alone does not imply hosted success.
