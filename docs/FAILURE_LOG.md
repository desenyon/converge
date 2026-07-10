# Failure log

## 2026-07-10

- Rustup found a partially installed pinned 1.96.0 toolchain during bootstrap and repaired it automatically before compilation.
- The first cargo-deny run rejected unversioned internal path dependencies and MPL-2.0. Internal edges were pinned to `=0.1.0`; MPL-2.0 was explicitly accepted for the replaceable `version-ranges` parser dependency and documented in ADR 0001.
