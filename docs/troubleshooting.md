# Troubleshooting

- Exit 8 means uv is unavailable. Install a current uv release and run `converge doctor`.
- Exit 5 means isolated validation failed. Inspect the JSON verification checks; no host files were changed.
- Exit 6 means application failed and rollback completed.
- Exit 7 means rollback itself failed. Preserve `.converge/snapshots` and avoid further mutation.
- A plan-ID mismatch means repository evidence changed; regenerate the plan.
- `--offline` can fail when required distributions are absent from the uv cache.
