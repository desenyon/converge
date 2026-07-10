//! Atomic, recoverable host file transactions.

use std::collections::BTreeSet;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Component, Path, PathBuf};

use atomic_write_file::AtomicWriteFile;
use converge_core::ConvergeError;
use converge_model::{
    AppliedFile, RepairAction, RepairPlan, SCHEMA_VERSION, TransactionReceipt, UndoReceipt,
    VerificationReport,
};
use fs2::FileExt;
use serde::{Deserialize, Serialize};

/// Transaction phase available to failure-injection tests.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransactionStep {
    /// Source fingerprint was rechecked under the repository lock.
    FingerprintChecked,
    /// Recoverable copies and transaction metadata were created.
    SnapshotCreated,
    /// All validated candidate contents were loaded.
    CandidateFilesLoaded,
    /// All candidate files atomically replaced host files.
    FilesReplaced,
    /// The latest-transaction pointer was committed.
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
}

struct RepositoryLock {
    file: File,
}

impl RepositoryLock {
    fn acquire(target: &Path) -> Result<Self, ConvergeError> {
        let state = target.join(".converge");
        std::fs::create_dir_all(&state).map_err(|error| ConvergeError::Store(error.to_string()))?;
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(state.join("state.lock"))
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        file.lock_exclusive()
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        Ok(Self { file })
    }
}

impl Drop for RepositoryLock {
    fn drop(&mut self) {
        let _ = self.file.unlock();
    }
}

/// Apply the exact files from a passing validation sandbox.
///
/// # Errors
///
/// Returns an error when validation did not pass, the source changed, or the transaction fails.
pub fn apply_validated(
    target: &Path,
    validated_root: &Path,
    plan: &RepairPlan,
    report: &VerificationReport,
) -> Result<TransactionReceipt, ConvergeError> {
    apply_validated_with_failure(target, validated_root, plan, report, None)
}

/// Apply with an optional failure point for mutation-safety testing.
///
/// # Errors
///
/// Returns the injected or real transaction error after restoring prior host file contents.
#[doc(hidden)]
pub fn apply_validated_with_failure(
    target: &Path,
    validated_root: &Path,
    plan: &RepairPlan,
    report: &VerificationReport,
    fail_after: Option<TransactionStep>,
) -> Result<TransactionReceipt, ConvergeError> {
    validate_report(plan, report)?;
    let target = target
        .canonicalize()
        .map_err(|error| ConvergeError::InvalidInvocation(error.to_string()))?;
    let _lock = RepositoryLock::acquire(&target)?;
    let current = converge_discovery::discover(&target)?;
    if current.repository.source_fingerprint != plan.source_fingerprint {
        return Err(ConvergeError::Validation(
            "repository fingerprint changed after planning".to_owned(),
        ));
    }
    inject(fail_after, TransactionStep::FingerprintChecked)?;

    let relative_files = affected_files(plan)?;
    let snapshot_relative = format!(".converge/snapshots/{}", plan.plan_id);
    let snapshot = target.join(&snapshot_relative);
    if snapshot.exists() {
        return Err(ConvergeError::Validation(format!(
            "snapshot already exists for plan {}",
            plan.plan_id
        )));
    }
    std::fs::create_dir_all(snapshot.join("files"))
        .map_err(|error| ConvergeError::Store(error.to_string()))?;

    let mut files = Vec::new();
    for relative in &relative_files {
        let destination = target.join(relative);
        let existed_before = destination.is_file();
        if existed_before {
            let backup = snapshot.join("files").join(relative);
            if let Some(parent) = backup.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|error| ConvergeError::Store(error.to_string()))?;
            }
            std::fs::copy(&destination, backup)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
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
    };
    atomic_write(
        &snapshot.join("metadata.json"),
        &serde_json::to_vec_pretty(&metadata)
            .map_err(|error| ConvergeError::Invariant(error.to_string()))?,
    )?;
    inject(fail_after, TransactionStep::SnapshotCreated)?;

    let mut candidates = Vec::new();
    for relative in &relative_files {
        let source = validated_root.join(relative);
        let bytes = std::fs::read(&source).map_err(|error| {
            ConvergeError::Validation(format!(
                "validated candidate is missing {}: {error}",
                source.display()
            ))
        })?;
        candidates.push((relative.clone(), bytes));
    }
    inject(fail_after, TransactionStep::CandidateFilesLoaded)?;

    for (relative, bytes) in &candidates {
        let destination = target.join(relative);
        if let Some(parent) = destination.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
        if let Err(error) = atomic_write(&destination, bytes) {
            let _ = restore_files(&target, &snapshot, &files);
            return Err(error);
        }
    }
    if let Err(error) = inject(fail_after, TransactionStep::FilesReplaced) {
        restore_files(&target, &snapshot, &files)?;
        return Err(error);
    }

    let last_applied = target.join(".converge/last_applied");
    atomic_write(&last_applied, plan.plan_id.as_bytes())?;
    if let Err(error) = inject(fail_after, TransactionStep::ReceiptCommitted) {
        restore_files(&target, &snapshot, &files)?;
        let _ = std::fs::remove_file(last_applied);
        return Err(error);
    }

    Ok(TransactionReceipt {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "transactionReceipt".to_owned(),
        plan_id: plan.plan_id.clone(),
        source_fingerprint_before: plan.source_fingerprint.clone(),
        files,
        snapshot_path: snapshot_relative,
    })
}

/// Restore files from the latest successful transaction.
///
/// # Errors
///
/// Returns an error when no transaction exists or restoration cannot complete.
pub fn undo_last(target: &Path) -> Result<UndoReceipt, ConvergeError> {
    let target = target
        .canonicalize()
        .map_err(|error| ConvergeError::InvalidInvocation(error.to_string()))?;
    let _lock = RepositoryLock::acquire(&target)?;
    let last_applied = target.join(".converge/last_applied");
    let plan_id = std::fs::read_to_string(&last_applied).map_err(|_| {
        ConvergeError::InvalidInvocation("no applied transaction to undo".to_owned())
    })?;
    let plan_id = plan_id.trim();
    let snapshot = target.join(".converge/snapshots").join(plan_id);
    let metadata: SnapshotMetadata = serde_json::from_slice(
        &std::fs::read(snapshot.join("metadata.json"))
            .map_err(|error| ConvergeError::Store(error.to_string()))?,
    )
    .map_err(|error| ConvergeError::Store(error.to_string()))?;

    if metadata.environment_synced {
        let environment = target.join(".venv");
        if environment.exists() {
            std::fs::remove_dir_all(&environment)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
        if metadata.environment_existed {
            std::fs::rename(snapshot.join("environment"), environment)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
    }
    restore_files(&target, &snapshot, &metadata.files)?;
    std::fs::remove_file(last_applied).map_err(|error| ConvergeError::Store(error.to_string()))?;
    Ok(UndoReceipt {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "undoReceipt".to_owned(),
        plan_id: metadata.plan_id,
        files: metadata.files,
    })
}

/// Create a fresh frozen host environment while retaining any previous environment for undo.
///
/// # Errors
///
/// Returns a mutation error after restoring the prior environment when synchronization fails.
pub async fn synchronize_environment(
    target: &Path,
    plan: &RepairPlan,
    offline: bool,
) -> Result<converge_model::CheckResult, ConvergeError> {
    let target = target
        .canonicalize()
        .map_err(|error| ConvergeError::InvalidInvocation(error.to_string()))?;
    let _lock = RepositoryLock::acquire(&target)?;
    let snapshot = target.join(".converge/snapshots").join(&plan.plan_id);
    let metadata_path = snapshot.join("metadata.json");
    let mut metadata: SnapshotMetadata = serde_json::from_slice(
        &std::fs::read(&metadata_path).map_err(|error| ConvergeError::Store(error.to_string()))?,
    )
    .map_err(|error| ConvergeError::Store(error.to_string()))?;
    let environment = target.join(".venv");
    let previous_environment = snapshot.join("environment");
    let existed = environment.exists();
    if existed {
        std::fs::rename(&environment, &previous_environment)
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
    }

    let invocation = converge_model::ToolInvocation {
        tool: "uv".to_owned(),
        arguments: vec!["sync".to_owned(), "--frozen".to_owned()],
        required: true,
        timeout_seconds: 600,
    };
    let result = match super::run_tool(&invocation, &target, offline).await {
        Ok(result) => result,
        Err(error) => {
            restore_environment(&environment, &previous_environment, existed)?;
            return Err(ConvergeError::MutationRolledBack(error.to_string()));
        }
    };
    if !result.passed {
        restore_environment(&environment, &previous_environment, existed)?;
        return Err(ConvergeError::MutationRolledBack(
            "uv sync --frozen rejected the validated host state".to_owned(),
        ));
    }

    metadata.environment_synced = true;
    metadata.environment_existed = existed;
    atomic_write(
        &metadata_path,
        &serde_json::to_vec_pretty(&metadata)
            .map_err(|error| ConvergeError::Invariant(error.to_string()))?,
    )?;
    Ok(result)
}

fn restore_environment(
    environment: &Path,
    previous_environment: &Path,
    existed: bool,
) -> Result<(), ConvergeError> {
    if environment.exists() {
        std::fs::remove_dir_all(environment)
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
    }
    if existed {
        std::fs::rename(previous_environment, environment)
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
    }
    Ok(())
}

fn validate_report(plan: &RepairPlan, report: &VerificationReport) -> Result<(), ConvergeError> {
    if !report.passed {
        return Err(ConvergeError::Validation(
            "host application requires a passing verification report".to_owned(),
        ));
    }
    if report.plan_id != plan.plan_id || report.source_fingerprint != plan.source_fingerprint {
        return Err(ConvergeError::Validation(
            "verification report does not match the selected plan".to_owned(),
        ));
    }
    Ok(())
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
        let relative = safe_relative(&file.path)?;
        let destination = target.join(&relative);
        if file.existed_before {
            let bytes = std::fs::read(snapshot.join("files").join(&relative))
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
