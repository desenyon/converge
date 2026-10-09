//! Recoverable host transactions held under one repository lock.

use std::collections::BTreeSet;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Component, Path, PathBuf};

use atomic_write_file::AtomicWriteFile;
use converge_core::ConvergeError;
use converge_model::{
    AppliedFile, CheckResult, Config, NetworkPolicy, RepairAction, RepairPlan, SCHEMA_VERSION,
    TransactionReceipt, UndoReceipt, VerificationReport,
};
use fs2::FileExt;
use serde::{Deserialize, Serialize};

/// Transaction phases exposed for deterministic failure injection.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransactionStep {
    /// Source fingerprint was checked under the lock.
    FingerprintChecked,
    /// Recoverable file snapshots were written.
    SnapshotCreated,
    /// All candidate files were loaded before any replacement.
    CandidateFilesLoaded,
    /// Candidate files replaced the originals.
    FilesReplaced,
    /// The previous environment was saved.
    EnvironmentBackedUp,
    /// Host synchronization finished.
    EnvironmentSynchronized,
    /// The latest-transaction pointer was written.
    ReceiptCommitted,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SnapshotMetadata {
    plan_id: String,
    source_fingerprint_before: String,
    files: Vec<AppliedFile>,
    #[serde(default)]
    environment_synced: bool,
    #[serde(default)]
    environment_existed: bool,
    #[serde(default)]
    previous_transaction: Option<String>,
    #[serde(default)]
    source_fingerprint_after: Option<String>,
}

struct RepositoryLock {
    file: File,
}
impl RepositoryLock {
    fn acquire(target: &Path) -> Result<Self, ConvergeError> {
        checked_path(target, ".converge/state.lock")?;
        std::fs::create_dir_all(target.join(".converge")).map_err(store_error)?;
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(target.join(".converge/state.lock"))
            .map_err(store_error)?;
        // Fail promptly instead of blocking an async runtime thread indefinitely.
        file.try_lock_exclusive().map_err(|error| {
            ConvergeError::Validation(format!("repository is busy or cannot be locked: {error}"))
        })?;
        Ok(Self { file })
    }
}
impl Drop for RepositoryLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

/// A host application attempt. The lock remains held until commit or rollback.
///
/// Dropping an unfinished attempt makes a best-effort rollback. Explicit rollback returns
/// restoration failures to the caller; an interrupted process leaves a journal for `undo`.
pub struct ApplicationTransaction {
    _lock: RepositoryLock,
    target: PathBuf,
    snapshot: PathBuf,
    attempt: String,
    metadata: SnapshotMetadata,
    receipt: TransactionReceipt,
    finished: bool,
    fail_after: Option<TransactionStep>,
}

impl ApplicationTransaction {
    /// Begin an attempt and install validated files under a single repository lock.
    ///
    /// # Errors
    /// Rejects stale/empty verification, unsafe paths, unfinished attempts, and file failures.
    pub fn begin(
        target: &Path,
        validated_root: &Path,
        plan: &RepairPlan,
        report: &VerificationReport,
    ) -> Result<Self, ConvergeError> {
        Self::begin_with_failure(target, validated_root, plan, report, None)
    }

    /// Begin with a deterministic failure point for transaction tests.
    ///
    /// # Errors
    /// Returns injected or actual failures, including any rollback failure.
    #[doc(hidden)]
    #[allow(clippy::too_many_lines)]
    pub fn begin_with_failure(
        target: &Path,
        validated_root: &Path,
        plan: &RepairPlan,
        report: &VerificationReport,
        fail_after: Option<TransactionStep>,
    ) -> Result<Self, ConvergeError> {
        validate_report(plan, report)?;
        let target = target.canonicalize().map_err(store_error)?;
        let lock = RepositoryLock::acquire(&target)?;
        if checked_path(&target, ".converge/pending")?.exists() {
            return Err(ConvergeError::Validation(
                "unfinished transaction exists; run converge undo to recover before applying again"
                    .to_owned(),
            ));
        }
        if converge_discovery::discover(&target)?
            .repository
            .source_fingerprint
            != plan.source_fingerprint
        {
            return Err(ConvergeError::Validation(
                "repository fingerprint changed after planning".to_owned(),
            ));
        }
        inject(fail_after, TransactionStep::FingerprintChecked)?;
        let relative_files = affected_files(plan)?;
        let mut candidates = Vec::new();
        for relative in &relative_files {
            let path = path_string(relative);
            checked_path(&target, &path)?;
            let source = checked_path(validated_root, &path)?;
            candidates.push((
                relative.clone(),
                std::fs::read(source).map_err(store_error)?,
            ));
        }
        inject(fail_after, TransactionStep::CandidateFilesLoaded)?;
        let attempt = format!("attempt-{}", uuid::Uuid::new_v4());
        let snapshot_relative = format!(".converge/snapshots/{attempt}");
        let snapshot = checked_path(&target, &snapshot_relative)?;
        std::fs::create_dir_all(snapshot.join("files")).map_err(store_error)?;
        let mut files = Vec::new();
        for relative in &relative_files {
            let destination = target.join(relative);
            let existed_before = destination.is_file();
            if destination.exists() && !existed_before {
                return Err(ConvergeError::Validation(format!(
                    "not a regular file: {}",
                    destination.display()
                )));
            }
            if existed_before {
                let backup = snapshot.join("files").join(relative);
                std::fs::create_dir_all(backup.parent().expect("backup parent"))
                    .map_err(store_error)?;
                let bytes = std::fs::read(&destination).map_err(store_error)?;
                atomic_write(&backup, &bytes)?;
            }
            files.push(AppliedFile {
                path: path_string(relative),
                existed_before,
            });
        }
        let metadata = SnapshotMetadata {
            plan_id: plan.plan_id.clone(),
            source_fingerprint_before: plan.source_fingerprint.clone(),
            files: files.clone(),
            environment_synced: false,
            environment_existed: false,
            previous_transaction: read_pointer(&target, "last_applied")?,
            source_fingerprint_after: None,
        };
        write_metadata(&snapshot, &metadata)?;
        inject(fail_after, TransactionStep::SnapshotCreated)?;
        atomic_write(&target.join(".converge/pending"), attempt.as_bytes())?;
        let receipt = TransactionReceipt {
            schema_version: SCHEMA_VERSION.to_owned(),
            kind: "transactionReceipt".to_owned(),
            plan_id: plan.plan_id.clone(),
            source_fingerprint_before: plan.source_fingerprint.clone(),
            files,
            snapshot_path: snapshot_relative,
        };
        let mut transaction = Self {
            _lock: lock,
            target,
            snapshot,
            attempt,
            metadata,
            receipt,
            finished: false,
            fail_after,
        };
        let result = (|| {
            for (relative, bytes) in candidates {
                let destination = transaction.target.join(relative);
                std::fs::create_dir_all(destination.parent().expect("destination parent"))
                    .map_err(store_error)?;
                atomic_write(&destination, &bytes)?;
            }
            inject(fail_after, TransactionStep::FilesReplaced)
        })();
        if let Err(error) = result {
            return Err(transaction.rollback(&error));
        }
        Ok(transaction)
    }

    /// Inspect the attempt receipt for audit persistence.
    #[must_use]
    pub const fn receipt(&self) -> &TransactionReceipt {
        &self.receipt
    }

    /// Create the host environment and repeat the required runtime checks.
    ///
    /// # Errors
    /// Returns synchronization or verification failure; the caller must roll back.
    pub async fn synchronize(
        &mut self,
        plan: &RepairPlan,
        config: &Config,
    ) -> Result<Vec<CheckResult>, ConvergeError> {
        if self.metadata.environment_synced {
            return Err(ConvergeError::Validation(
                "environment synchronization already attempted".to_owned(),
            ));
        }
        let environment = checked_path(&self.target, ".venv")?;
        self.metadata.environment_existed = environment.exists();
        if environment.exists() && !environment.is_dir() {
            return Err(ConvergeError::Validation(
                ".venv is not a directory".to_owned(),
            ));
        }
        self.metadata.environment_synced = true;
        // Journal intent before moving the old environment; recovery is idempotent if the
        // process stops on either side of rename.
        write_metadata(&self.snapshot, &self.metadata)?;
        if self.metadata.environment_existed {
            std::fs::rename(&environment, self.snapshot.join("environment"))
                .map_err(store_error)?;
        }
        inject(self.fail_after, TransactionStep::EnvironmentBackedUp)?;
        let invocation = converge_model::ToolInvocation {
            tool: "uv".to_owned(),
            arguments: vec!["sync".to_owned(), "--frozen".to_owned()],
            required: true,
            timeout_seconds: config.command_timeout_seconds,
        };
        let offline = config.network == NetworkPolicy::Deny;
        let mut checks = vec![super::run_tool(&invocation, &self.target, offline).await?];
        if !checks[0].passed {
            return Err(ConvergeError::Validation(format!(
                "host uv sync failed: {}",
                checks[0].stderr
            )));
        }
        inject(self.fail_after, TransactionStep::EnvironmentSynchronized)?;
        for invocation in plan
            .verification_contract
            .checks
            .iter()
            .filter(|check| check.arguments.first().is_some_and(|arg| arg == "run"))
        {
            let check = super::run_tool(invocation, &self.target, offline).await?;
            if invocation.required && !check.passed {
                return Err(ConvergeError::Validation(format!(
                    "host runtime verification failed: {}",
                    check.stderr
                )));
            }
            checks.push(check);
        }
        Ok(checks)
    }

    /// Publish this receipt and persist audit data while still holding the lock.
    ///
    /// # Errors
    /// Rolls back if pointer publication or the supplied persistence operation fails.
    pub fn commit(
        mut self,
        persist: impl FnOnce(&TransactionReceipt) -> Result<(), ConvergeError>,
    ) -> Result<TransactionReceipt, ConvergeError> {
        let result = (|| {
            self.metadata.source_fingerprint_after = Some(
                converge_discovery::discover(&self.target)?
                    .repository
                    .source_fingerprint,
            );
            write_metadata(&self.snapshot, &self.metadata)?;
            atomic_write(
                &self.target.join(".converge/last_applied"),
                self.attempt.as_bytes(),
            )?;
            inject(self.fail_after, TransactionStep::ReceiptCommitted)?;
            persist(&self.receipt)?;
            std::fs::remove_file(self.target.join(".converge/pending")).map_err(store_error)
        })();
        if let Err(error) = result {
            return Err(self.rollback(&error));
        }
        self.finished = true;
        Ok(self.receipt.clone())
    }

    /// Restore this specific attempt, never an unrelated latest transaction.
    #[must_use]
    pub fn rollback(&mut self, cause: &ConvergeError) -> ConvergeError {
        let result = restore_attempt(&self.target, &self.snapshot, &self.metadata);
        // Keep the journal if restoration fails; do not silently retry from Drop.
        self.finished = true;
        match result {
            Ok(()) => ConvergeError::MutationRolledBack(cause.to_string()),
            Err(error) => ConvergeError::RollbackFailed(format!(
                "original error: {cause}; recovery error: {error}; snapshot: {}",
                self.receipt.snapshot_path
            )),
        }
    }
}
impl Drop for ApplicationTransaction {
    fn drop(&mut self) {
        if !self.finished {
            let _ = restore_attempt(&self.target, &self.snapshot, &self.metadata);
        }
    }
}

/// Apply validated file changes only. Full workflows should use `ApplicationTransaction`.
///
/// # Errors
/// Rejects invalid verification and returns mutation/rollback failures.
pub fn apply_validated(
    target: &Path,
    validated_root: &Path,
    plan: &RepairPlan,
    report: &VerificationReport,
) -> Result<TransactionReceipt, ConvergeError> {
    apply_validated_with_failure(target, validated_root, plan, report, None)
}

/// Apply file changes with a deterministic failure injection point.
///
/// # Errors
/// Returns injected or actual transaction failures.
#[doc(hidden)]
pub fn apply_validated_with_failure(
    target: &Path,
    validated_root: &Path,
    plan: &RepairPlan,
    report: &VerificationReport,
    fail_after: Option<TransactionStep>,
) -> Result<TransactionReceipt, ConvergeError> {
    ApplicationTransaction::begin_with_failure(target, validated_root, plan, report, fail_after)?
        .commit(|_| Ok(()))
}

/// Restore the unfinished attempt, or the most recent committed transaction.
///
/// # Errors
/// Returns an error when no transaction exists or recovery cannot complete.
pub fn undo_last(target: &Path) -> Result<UndoReceipt, ConvergeError> {
    let target = target.canonicalize().map_err(store_error)?;
    let _lock = RepositoryLock::acquire(&target)?;
    let pending = read_pointer(&target, "pending")?;
    let attempt = pending
        .clone()
        .or(read_pointer(&target, "last_applied")?)
        .ok_or_else(|| {
            ConvergeError::InvalidInvocation("no applied transaction to undo".to_owned())
        })?;
    let snapshot = checked_path(&target, &format!(".converge/snapshots/{attempt}"))?;
    let metadata = read_metadata(&snapshot)?;
    if pending.is_none()
        && let Some(expected) = &metadata.source_fingerprint_after
        && converge_discovery::discover(&target)?
            .repository
            .source_fingerprint
            != *expected
    {
        return Err(ConvergeError::Validation(
            "repository changed after apply; preserve those edits before undoing".to_owned(),
        ));
    }
    // A journal also makes retrying an interrupted undo deterministic.
    atomic_write(&target.join(".converge/pending"), attempt.as_bytes())?;
    restore_attempt(&target, &snapshot, &metadata)
        .map_err(|error| ConvergeError::RollbackFailed(error.to_string()))?;
    Ok(UndoReceipt {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "undoReceipt".to_owned(),
        plan_id: metadata.plan_id,
        files: metadata.files,
    })
}

/// Synchronize a file-only application for compatibility with older library callers.
/// Prefer `ApplicationTransaction` to keep file and environment changes under one lock.
///
/// # Errors
/// Rejects a different latest plan or an unfinished attempt, and restores on failure.
pub async fn synchronize_environment(
    target: &Path,
    plan: &RepairPlan,
    offline: bool,
) -> Result<CheckResult, ConvergeError> {
    let target = target.canonicalize().map_err(store_error)?;
    let lock = RepositoryLock::acquire(&target)?;
    if read_pointer(&target, "pending")?.is_some() {
        return Err(ConvergeError::Validation(
            "unfinished transaction; run undo".to_owned(),
        ));
    }
    let attempt = read_pointer(&target, "last_applied")?
        .ok_or_else(|| ConvergeError::Validation("no applied plan".to_owned()))?;
    let snapshot = checked_path(&target, &format!(".converge/snapshots/{attempt}"))?;
    let metadata = read_metadata(&snapshot)?;
    if metadata.plan_id != plan.plan_id || metadata.environment_synced {
        return Err(ConvergeError::Validation(
            "latest transaction does not match an unsynchronized plan".to_owned(),
        ));
    }
    let receipt = TransactionReceipt {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "transactionReceipt".to_owned(),
        plan_id: plan.plan_id.clone(),
        source_fingerprint_before: plan.source_fingerprint.clone(),
        files: metadata.files.clone(),
        snapshot_path: format!(".converge/snapshots/{attempt}"),
    };
    atomic_write(&target.join(".converge/pending"), attempt.as_bytes())?;
    let mut transaction = ApplicationTransaction {
        _lock: lock,
        target,
        snapshot,
        attempt,
        metadata,
        receipt,
        finished: false,
        fail_after: None,
    };
    let config = Config {
        network: if offline {
            NetworkPolicy::Deny
        } else {
            NetworkPolicy::Allow
        },
        ..Config::default()
    };
    let checks = match transaction.synchronize(plan, &config).await {
        Ok(checks) => checks,
        Err(error) => return Err(transaction.rollback(&error)),
    };
    transaction.commit(|_| Ok(()))?;
    Ok(checks[0].clone())
}

fn restore_attempt(
    target: &Path,
    snapshot: &Path,
    metadata: &SnapshotMetadata,
) -> Result<(), ConvergeError> {
    if metadata.environment_synced {
        let environment = checked_path(target, ".venv")?;
        let backup = snapshot.join("environment");
        // With an original environment, absence of the backup means either rename never
        // happened or a previous recovery already restored it. Never delete it in that case.
        if !metadata.environment_existed || backup.exists() {
            if environment.exists() {
                std::fs::remove_dir_all(&environment).map_err(store_error)?;
            }
            if metadata.environment_existed {
                std::fs::rename(backup, environment).map_err(store_error)?;
            }
        }
    }
    restore_files(target, snapshot, &metadata.files)?;
    let pointer = checked_path(target, ".converge/last_applied")?;
    if let Some(previous) = &metadata.previous_transaction {
        validate_pointer(previous)?;
        atomic_write(&pointer, previous.as_bytes())?;
    } else if pointer.exists() {
        std::fs::remove_file(pointer).map_err(store_error)?;
    }
    let pending = checked_path(target, ".converge/pending")?;
    if pending.exists() {
        std::fs::remove_file(pending).map_err(store_error)?;
    }
    Ok(())
}

fn validate_report(plan: &RepairPlan, report: &VerificationReport) -> Result<(), ConvergeError> {
    let required: Vec<_> = plan
        .verification_contract
        .checks
        .iter()
        .filter(|check| check.required)
        .collect();
    if !report.passed
        || required.is_empty()
        || required.iter().any(|expected| {
            !report.checks.iter().any(|actual| {
                actual.tool == expected.tool
                    && actual.arguments == expected.arguments
                    && actual.passed
            })
        })
    {
        return Err(ConvergeError::Validation(
            "host application requires a complete passing verification contract".to_owned(),
        ));
    }
    if report.plan_id != plan.plan_id || report.source_fingerprint != plan.source_fingerprint {
        return Err(ConvergeError::Validation(
            "verification report does not match the selected plan".to_owned(),
        ));
    }
    Ok(())
}

fn read_pointer(target: &Path, name: &str) -> Result<Option<String>, ConvergeError> {
    let path = checked_path(target, &format!(".converge/{name}"))?;
    match std::fs::read_to_string(path) {
        Ok(value) => {
            let value = value.trim().to_owned();
            validate_pointer(&value)?;
            Ok(Some(value))
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(store_error(error)),
    }
}
fn validate_pointer(value: &str) -> Result<(), ConvergeError> {
    if safe_relative(value)?.components().count() != 1 {
        return Err(ConvergeError::Validation(
            "invalid transaction pointer".to_owned(),
        ));
    }
    Ok(())
}
fn read_metadata(snapshot: &Path) -> Result<SnapshotMetadata, ConvergeError> {
    let path = checked_path(snapshot, "metadata.json")?;
    serde_json::from_slice(&std::fs::read(path).map_err(store_error)?)
        .map_err(|error| ConvergeError::Store(error.to_string()))
}
fn write_metadata(snapshot: &Path, metadata: &SnapshotMetadata) -> Result<(), ConvergeError> {
    atomic_write(
        &snapshot.join("metadata.json"),
        &serde_json::to_vec_pretty(metadata)
            .map_err(|error| ConvergeError::Store(error.to_string()))?,
    )
}
#[allow(clippy::needless_pass_by_value)] // Matches Result::map_err without repeated closures.
fn store_error(error: std::io::Error) -> ConvergeError {
    ConvergeError::Store(error.to_string())
}

fn checked_path(root: &Path, value: &str) -> Result<PathBuf, ConvergeError> {
    let relative = safe_relative(value)?;
    let mut path = root.to_path_buf();
    for component in relative.components() {
        path.push(component);
        match std::fs::symlink_metadata(&path) {
            Ok(metadata) if metadata.file_type().is_symlink() => {
                return Err(ConvergeError::Validation(format!(
                    "symlink path is not supported: {}",
                    path.display()
                )));
            }
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => {
                return Err(store_error(error));
            }
            _ => {}
        }
    }
    Ok(path)
}
fn affected_files(plan: &RepairPlan) -> Result<Vec<PathBuf>, ConvergeError> {
    let mut files = BTreeSet::new();
    for action in &plan.actions {
        let path = match action {
            RepairAction::AddDependency { manifest_path, .. }
            | RepairAction::RemoveDependency { manifest_path, .. }
            | RepairAction::ChangeConstraint { manifest_path, .. } => Some(manifest_path.as_str()),
            RepairAction::GenerateLockfile { .. } => Some("uv.lock"),
            RepairAction::RefreshLockfile { lockfile_path, .. } => Some(lockfile_path.as_str()),
            RepairAction::SelectRuntime { .. }
            | RepairAction::CreateEnvironment { .. }
            | RepairAction::NoChange { .. } => None,
        };
        if let Some(path) = path {
            if !matches!(path, "pyproject.toml" | "uv.lock") {
                return Err(ConvergeError::Validation(format!(
                    "unsupported host mutation path: {path}"
                )));
            }
            files.insert(safe_relative(path)?);
        }
    }
    Ok(files.into_iter().collect())
}

fn safe_relative(value: &str) -> Result<PathBuf, ConvergeError> {
    let path = Path::new(value);
    if path.as_os_str().is_empty()
        || path.is_absolute()
        || path
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err(ConvergeError::Validation(format!(
            "repair path is not repository-relative: {value}"
        )));
    }
    Ok(path.to_path_buf())
}

fn restore_files(
    target: &Path,
    snapshot: &Path,
    files: &[AppliedFile],
) -> Result<(), ConvergeError> {
    for file in files.iter().rev() {
        if !matches!(file.path.as_str(), "pyproject.toml" | "uv.lock") {
            return Err(ConvergeError::Validation(format!(
                "unsupported recovery path: {}",
                file.path
            )));
        }
        let relative = safe_relative(&file.path)?;
        let destination = checked_path(target, &file.path)?;
        if file.existed_before {
            let bytes = std::fs::read(checked_path(
                snapshot,
                &format!("files/{}", path_string(&relative)),
            )?)
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
            atomic_write(&destination, &bytes)?;
        } else if destination.exists() {
            std::fs::remove_file(&destination)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
    }
    Ok(())
}

fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), ConvergeError> {
    let mut file =
        AtomicWriteFile::open(path).map_err(|error| ConvergeError::Store(error.to_string()))?;
    file.write_all(bytes)
        .and_then(|()| file.flush())
        .map_err(|error| ConvergeError::Store(error.to_string()))?;
    file.commit()
        .map_err(|error| ConvergeError::Store(error.to_string()))
}

fn inject(expected: Option<TransactionStep>, actual: TransactionStep) -> Result<(), ConvergeError> {
    if expected == Some(actual) {
        Err(ConvergeError::Validation(format!(
            "injected failure after {actual:?}"
        )))
    } else {
        Ok(())
    }
}

fn path_string(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}
