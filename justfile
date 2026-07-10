default:
    just --list

check:
    cargo fmt --check
    cargo clippy --workspace --all-targets --all-features -- -D warnings
    cargo test --workspace --all-features

run *args:
    cargo run -p converge-cli -- {{args}}
