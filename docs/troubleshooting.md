# Troubleshooting

- **Unsupported verification**: inspect `converge discover TARGET --json`. Automatic execution requires one root PEP 621 project, optional root uv.lock, no mixed manifests/workspace, and no discovery warnings.
- **Plan ID mismatch**: regenerate with the same target, network policy and timeout used by apply. Relevant source/config changes invalidate the old ID.
- **Network/cache failure**: offline mode requires cached artifacts and an installed interpreter. Supply a writable `UV_CACHE_DIR` or explicitly permit networking after reviewing the project.
- **Busy repository**: another writer holds the cooperative lock. Wait for it to finish; do not delete a lock file that another process may be holding.
- **Pending transaction**: preserve snapshots and run `converge undo TARGET`. A new application is refused while a recovery journal remains.
- **Rollback failure (7)**: the error includes the original cause and restoration failure. Preserve metadata/backups and resolve that storage/path problem before retrying undo. Do not delete `.converge` to clear the error.
- **Undo rejects later edits**: preserve/reconcile changed source before undoing. Converge provides no force flag that discards those edits.
- **No tests reported**: verification currently covers uv resolution/install and curated runtime imports, not project test/lint/type suites. Run the project's own checks separately.
- **Truncated output**: capture retains only a bounded prefix of each stream and marks truncation. Increase timeout if appropriate; no complete unbounded raw log exists.

See the README for exact exit codes, migration behavior and recovery limitations.
