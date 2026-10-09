# Privacy

Converge needs no cloud account. Graph/application audit data and recoverable snapshots stay in the target's `.converge/`; sandbox copies are temporary directories. No remote telemetry exporter is implemented. The `telemetry` setting is a reserved opt-in, not an active export feature.

uv can contact configured registries and use its cache/credentials when network is allowed. Deny policy supplies `--offline` to uv. Reports record permission, commands, bounded output and version information; they do not enumerate contacted endpoints. Build hooks/imports are not confined by an OS sandbox.

Audit data includes plans, effective configuration and paths. Snapshots retain original manifest/lock bytes and may retain the previous entire `.venv`. They can therefore contain sensitive data. Basic TOKEN=/PASSWORD=/API_KEY= output redaction is not a comprehensive secret scanner. Review local state before sharing; do not commit `.converge/` or `.venv`.
