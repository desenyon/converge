# ADR 0002: YAML parser for Conda discovery

Status: accepted

Converge parses Conda `environment.yml` / `environment.yaml` files during read-only discovery.

`yaml-rust2` 0.11 was selected because it is actively maintained, YAML 1.2 compliant, MIT OR Apache-2.0 licensed, pure Rust, and exposes a document walk API comparable to the existing `toml::Value` approach used for manifests and lockfiles. Deprecated Serde YAML shims were rejected to avoid unmaintained supply-chain risk.

The dependency is confined to the discovery adapter. It does not control planning, mutation, or solver semantics and remains replaceable.
