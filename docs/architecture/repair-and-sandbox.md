# Repair, validation, and recovery

The CLI resolves configuration, discovers the explicit target, diagnoses each project's imports/declarations, and constructs a deterministic plan. Supported automatic execution requires one root PEP 621 project, optional root uv.lock, no other manifest/lock backend, no workspace, and no discovery warnings. Unsupported targets receive a discovery-only explanation; an empty required contract cannot pass verification.

The filesystem-copy backend excludes .git, .converge, .venv, target, and node_modules directories, rejects symlinks, checks the copied evidence fingerprint, and applies typed root manifest changes. It records uv's version, resolves when a lock action exists, checks the lock, actually installs with `uv sync --frozen`, then runs isolated Python virtual-environment/import checks. Required failure short-circuits; advisory failure is retained in the report.

`ApplicationTransaction` owns the host lock across file replacement, host sync/checks, and persistence. It rejects a pending journal or changed fingerprint before source mutation. Candidate bytes are loaded before replacements. Each attempt uses a UUID snapshot; the deterministic plan ID remains independent of an attempt. Metadata and a pending pointer are written before host changes. Environment intent is journaled before moving the old .venv into the snapshot, allowing recovery on either side of the rename.

The CLI uses the guard through host synchronization and runtime verification, then commits the receipt and stores the graph/application audit in one SQLite transaction. Explicit rollback restores that attempt, including its previous successful receipt. A dropped unfinished guard performs best-effort restoration. A restoration failure retains the journal and is returned as exit 7. New writers fail promptly when the repository lock is held.

Undo acquires the same lock and recovers `pending` first, otherwise `last_applied`. Completed snapshots record the post-apply evidence fingerprint; undo refuses later relevant source edits. Legacy snapshots lack this optional field and remain readable. Recovery is idempotent across environment restoration: absence of an original environment backup means its rename either never occurred or a prior recovery already restored it.

Atomicity is per file. Multi-file updates, directory renames and SQLite cannot be one atomic commit. There is no power-loss guarantee; abrupt termination can leave an application audit plus a pending recovery journal. Undo does not currently append its own audit event or rebuild the derived graph. Snapshots have no automatic garbage collection.

The temporary copy is not a hostile-code security boundary. Dependency builds and imported modules run with user privileges. Network deny supplies uv's `--offline`, but no OS firewall, disk/process quota, or descendant process-tree termination is implemented. See [the threat model](threat-model.md).
