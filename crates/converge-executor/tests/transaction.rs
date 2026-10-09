#![allow(missing_docs)]

use std::path::{Path, PathBuf};

use converge_discovery::discover;
use converge_executor::{
    TransactionStep, apply_validated, apply_validated_with_failure, undo_last,
};
use converge_model::{SCHEMA_VERSION, VerificationReport};
use converge_planner::{diagnose, plan};

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../fixtures/python/broken_missing")
}

fn copy_fixture(destination: &Path) {
    for entry in walkdir::WalkDir::new(fixture()) {
        let entry = entry.expect("fixture entry");
        let relative = entry.path().strip_prefix(fixture()).expect("relative");
        let output = destination.join(relative);
        if entry.file_type().is_dir() {
            std::fs::create_dir_all(&output).expect("directory");
        } else {
            std::fs::copy(entry.path(), output).expect("copy");
        }
    }
}

fn candidate(target: &Path, output: &Path) {
    copy_fixture(output);
    let manifest = output.join("pyproject.toml");
    let original = std::fs::read_to_string(&manifest).expect("candidate manifest");
    let changed = original.replace(
        "dependencies = []",
        "dependencies = [\n  \"httpx\",\n  \"rich\",\n]",
    );
    std::fs::write(manifest, changed).expect("write candidate");
    std::fs::write(
        output.join("uv.lock"),
        "version = 1\nrevision = 3\nrequires-python = \">=3.11\"\n",
    )
    .expect("candidate lock");

    assert!(target.join("pyproject.toml").is_file());
}

fn report_for(plan: &converge_model::RepairPlan) -> VerificationReport {
    VerificationReport {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "verificationReport".to_owned(),
        plan_id: plan.plan_id.clone(),
        source_fingerprint: plan.source_fingerprint.clone(),
        network_allowed: false,
        passed: true,
        checks: plan
            .verification_contract
            .checks
            .iter()
            .map(|check| converge_model::CheckResult {
                tool: check.tool.clone(),
                arguments: check.arguments.clone(),
                exit_code: Some(0),
                passed: true,
                stdout: String::new(),
                stderr: String::new(),
            })
            .collect(),
    }
}

#[test]
fn every_injected_transaction_failure_preserves_host_files() {
    let steps = [
        TransactionStep::FingerprintChecked,
        TransactionStep::SnapshotCreated,
        TransactionStep::CandidateFilesLoaded,
        TransactionStep::FilesReplaced,
        TransactionStep::ReceiptCommitted,
    ];

    for step in steps {
        let target = tempfile::tempdir().expect("target");
        copy_fixture(target.path());
        let original =
            std::fs::read_to_string(target.path().join("pyproject.toml")).expect("original");
        let snapshot = discover(target.path()).expect("discover");
        let repair = plan(&snapshot, &diagnose(&snapshot));
        let validated = tempfile::tempdir().expect("validated");
        candidate(target.path(), validated.path());

        let result = apply_validated_with_failure(
            target.path(),
            validated.path(),
            &repair,
            &report_for(&repair),
            Some(step),
        );
        assert!(result.is_err(), "{step:?} should fail");
        assert_eq!(
            std::fs::read_to_string(target.path().join("pyproject.toml")).expect("host"),
            original,
            "{step:?} changed the manifest"
        );
        assert!(
            !target.path().join("uv.lock").exists(),
            "{step:?} left a lockfile"
        );
    }
}

#[test]
fn successful_apply_is_reversible() {
    let target = tempfile::tempdir().expect("target");
    copy_fixture(target.path());
    let original = std::fs::read_to_string(target.path().join("pyproject.toml")).expect("original");
    let snapshot = discover(target.path()).expect("discover");
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().expect("validated");
    candidate(target.path(), validated.path());

    let receipt = apply_validated(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .expect("apply");
    assert_eq!(receipt.files.len(), 2);
    assert!(target.path().join("uv.lock").is_file());

    let undo = undo_last(target.path()).expect("undo");
    assert_eq!(undo.plan_id, repair.plan_id);
    assert_eq!(
        std::fs::read_to_string(target.path().join("pyproject.toml")).expect("restored"),
        original
    );
    assert!(!target.path().join("uv.lock").exists());
}

#[test]
fn retry_after_undo_uses_a_distinct_attempt_snapshot() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let first = apply_validated(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    undo_last(target.path()).unwrap();
    let second = apply_validated(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    assert_ne!(first.snapshot_path, second.snapshot_path);
}

#[test]
fn empty_verification_cannot_authorize_mutation() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let mut report = report_for(&repair);
    report.checks.clear();
    assert!(apply_validated(target.path(), validated.path(), &repair, &report).is_err());
    assert!(!target.path().join("uv.lock").exists());
}

#[test]
fn active_attempt_blocks_undo_and_rolls_back_on_drop() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let transaction = converge_executor::ApplicationTransaction::begin(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    assert!(undo_last(target.path()).is_err());
    assert!(
        converge_executor::ApplicationTransaction::begin(
            target.path(),
            validated.path(),
            &repair,
            &report_for(&repair)
        )
        .is_err()
    );
    drop(transaction);
    assert!(!target.path().join("uv.lock").exists());
    assert!(!target.path().join(".converge/pending").exists());
}

#[test]
fn audit_failure_rolls_back_exact_attempt_and_preserves_previous_receipt() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    std::fs::create_dir_all(target.path().join(".converge")).unwrap();
    std::fs::write(
        target.path().join(".converge/last_applied"),
        "prior-attempt",
    )
    .unwrap();
    let transaction = converge_executor::ApplicationTransaction::begin(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    let error = transaction
        .commit(|_| {
            Err(converge_core::ConvergeError::Store(
                "injected audit failure".to_owned(),
            ))
        })
        .unwrap_err();
    assert_eq!(error.exit_code(), 6);
    assert!(!target.path().join("uv.lock").exists());
    assert_eq!(
        std::fs::read_to_string(target.path().join(".converge/last_applied")).unwrap(),
        "prior-attempt"
    );
}

#[test]
fn undo_preserves_source_edits_made_after_apply() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    apply_validated(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    std::fs::write(target.path().join("later.py"), "# user edit\n").unwrap();
    assert_eq!(undo_last(target.path()).unwrap_err().exit_code(), 5);
    assert!(target.path().join("uv.lock").exists());
}

#[tokio::test]
async fn environment_backup_failure_restores_original_environment_and_files() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    std::fs::create_dir(target.path().join(".venv")).unwrap();
    std::fs::write(target.path().join(".venv/original"), "prior").unwrap();
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let mut transaction = converge_executor::ApplicationTransaction::begin_with_failure(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
        Some(TransactionStep::EnvironmentBackedUp),
    )
    .unwrap();
    let cause = transaction
        .synchronize(&repair, &converge_model::Config::default())
        .await
        .unwrap_err();
    assert_eq!(transaction.rollback(&cause).exit_code(), 6);
    assert_eq!(
        std::fs::read_to_string(target.path().join(".venv/original")).unwrap(),
        "prior"
    );
    assert!(!target.path().join("uv.lock").exists());
}

#[tokio::test]
async fn metadata_failure_before_environment_move_is_reversible() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    std::fs::create_dir(target.path().join(".venv")).unwrap();
    std::fs::write(target.path().join(".venv/original"), "prior").unwrap();
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let mut transaction = converge_executor::ApplicationTransaction::begin(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    let metadata = target
        .path()
        .join(&transaction.receipt().snapshot_path)
        .join("metadata.json");
    std::fs::remove_file(&metadata).unwrap();
    std::fs::create_dir(metadata).unwrap();
    let cause = transaction
        .synchronize(&repair, &converge_model::Config::default())
        .await
        .unwrap_err();
    assert_eq!(transaction.rollback(&cause).exit_code(), 6);
    assert_eq!(
        std::fs::read_to_string(target.path().join(".venv/original")).unwrap(),
        "prior"
    );
    assert!(!target.path().join("uv.lock").exists());
}

#[test]
fn rollback_failure_retains_recovery_journal_and_can_be_retried() {
    let target = tempfile::tempdir().unwrap();
    copy_fixture(target.path());
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    candidate(target.path(), validated.path());
    let mut transaction = converge_executor::ApplicationTransaction::begin(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
    )
    .unwrap();
    let backup = target
        .path()
        .join(&transaction.receipt().snapshot_path)
        .join("files/pyproject.toml");
    let original = std::fs::read(&backup).unwrap();
    std::fs::remove_file(&backup).unwrap();
    assert_eq!(
        transaction
            .rollback(&converge_core::ConvergeError::Validation("test".to_owned()))
            .exit_code(),
        7
    );
    drop(transaction);
    assert!(target.path().join(".converge/pending").is_file());
    assert!(
        converge_executor::ApplicationTransaction::begin(
            target.path(),
            validated.path(),
            &repair,
            &report_for(&repair)
        )
        .is_err()
    );
    std::fs::write(backup, &original).unwrap();
    std::fs::write(target.path().join(".converge/last_applied"), "../invalid").unwrap();
    undo_last(target.path()).unwrap();
    assert_eq!(
        std::fs::read(target.path().join("pyproject.toml")).unwrap(),
        original
    );
    assert!(!target.path().join(".converge/pending").exists());
}

#[tokio::test]
async fn failure_after_real_offline_sync_restores_previous_environment() {
    let target = tempfile::tempdir().unwrap();
    std::fs::write(target.path().join("pyproject.toml"), "[project]\nname='transaction-test'\nversion='0.1.0'\nrequires-python='>=3.11'\ndependencies=[]\n").unwrap();
    std::fs::create_dir(target.path().join(".venv")).unwrap();
    std::fs::write(target.path().join(".venv/original"), "prior").unwrap();
    let cache = tempfile::tempdir().unwrap();
    std::fs::write(
        target.path().join("uv.toml"),
        format!("cache-dir = {:?}\n", cache.path().to_str().unwrap()),
    )
    .unwrap();
    let snapshot = discover(target.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    let validated = tempfile::tempdir().unwrap();
    std::fs::copy(
        target.path().join("pyproject.toml"),
        validated.path().join("pyproject.toml"),
    )
    .unwrap();
    std::fs::copy(
        target.path().join("uv.toml"),
        validated.path().join("uv.toml"),
    )
    .unwrap();
    let lock = std::process::Command::new("uv")
        .args(["--offline", "--no-cache", "lock"])
        .current_dir(validated.path())
        .env("UV_PYTHON_DOWNLOADS", "never")
        .env("UV_CACHE_DIR", cache.path())
        .output()
        .unwrap();
    assert!(
        lock.status.success(),
        "{}",
        String::from_utf8_lossy(&lock.stderr)
    );
    let mut transaction = converge_executor::ApplicationTransaction::begin_with_failure(
        target.path(),
        validated.path(),
        &repair,
        &report_for(&repair),
        Some(TransactionStep::EnvironmentSynchronized),
    )
    .unwrap();
    // Keep uv's cache inside the temporary repository by using a repository-level uv config.
    // The environment contains no packages and uses the already installed interpreter.
    let config = converge_model::Config {
        network: converge_model::NetworkPolicy::Deny,
        ..Default::default()
    };
    let error = transaction.synchronize(&repair, &config).await.unwrap_err();
    assert!(
        error.to_string().contains("EnvironmentSynchronized"),
        "{error}"
    );
    assert_eq!(transaction.rollback(&error).exit_code(), 6);
    assert_eq!(
        std::fs::read_to_string(target.path().join(".venv/original")).unwrap(),
        "prior"
    );
    assert!(!target.path().join("uv.lock").exists());
}
