# Development and testing

Run:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
cargo audit
cargo deny check
```

The acceptance test uses the real uv backend. Transaction tests inject a failure after each protocol phase and prove source restoration.
