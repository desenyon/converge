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
        checks: Vec::new(),
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
