## Invariant

State the product or safety invariant implemented.

## Evidence

- [ ] Failing test existed before the implementation
- [ ] Targeted tests pass
- [ ] `cargo fmt --all -- --check`
- [ ] `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- [ ] `cargo test --workspace --all-features`
- [ ] Schemas and documentation updated when contracts changed
- [ ] No secret or machine-specific path is present

## Mutation safety

Describe validation, rollback, and failure-injection coverage, or state why no mutation path changed.
