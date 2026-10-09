#![allow(missing_docs)]

use std::path::Path;
use std::process::{Command, Output};

fn invoke(target: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(args)
        .arg(target)
        .env("CONVERGE_NETWORK", "deny")
        .env("CONVERGE_AUTO_APPLY", "false")
        .env("CONVERGE_COMMAND_TIMEOUT_SECONDS", "30")
        .env("UV_CACHE_DIR", target.join(".converge-test-cache"))
        .output()
        .unwrap()
}
fn assert_success(output: &Output) -> serde_json::Value {
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}
fn manifest(target: &Path) {
    std::fs::write(target.join("pyproject.toml"), "[project]\nname='offline-demo'\nversion='0.1.0'\nrequires-python='>=3.11'\ndependencies=[]\n").unwrap();
}

#[test]
fn real_uv_offline_apply_undo_retry_restores_existing_environment() {
    let target = tempfile::tempdir().unwrap();
    manifest(target.path());
    std::fs::create_dir(target.path().join(".venv")).unwrap();
    std::fs::write(target.path().join(".venv/prior-environment"), "original").unwrap();
    let first = assert_success(&invoke(
        target.path(),
        &["solve", "--yes", "--offline", "--json"],
    ));
    assert_eq!(first["verification"]["networkAllowed"], false);
    assert_eq!(first["verification"]["passed"], true);
    let checks = first["verification"]["checks"].as_array().unwrap();
    assert!(
        checks
            .iter()
            .any(|check| check["arguments"] == serde_json::json!(["sync", "--frozen"]))
    );
    assert!(checks.iter().any(|check| check["arguments"][0] == "run"));
    assert!(!target.path().join(".venv/prior-environment").exists());
    let audit = assert_success(&invoke(target.path(), &["audit", "--json"]));
    let event: serde_json::Value =
        serde_json::from_str(audit["records"][0]["eventJson"].as_str().unwrap()).unwrap();
    assert_eq!(event["configuration"]["config"]["network"], "deny");
    assert_eq!(
        event["configuration"]["config"]["commandTimeoutSeconds"],
        30
    );
    assert_success(&invoke(target.path(), &["undo", "--json"]));
    assert_eq!(
        std::fs::read_to_string(target.path().join(".venv/prior-environment")).unwrap(),
        "original"
    );
    assert!(!target.path().join("uv.lock").exists());
    let second = assert_success(&invoke(
        target.path(),
        &["solve", "--yes", "--offline", "--json"],
    ));
    assert_ne!(
        first["appliedChanges"]["snapshotPath"],
        second["appliedChanges"]["snapshotPath"]
    );
}

#[test]
fn empty_target_fails_verification_instead_of_claiming_success() {
    let target = tempfile::tempdir().unwrap();
    let result = invoke(target.path(), &["verify", "--json"]);
    assert_eq!(result.status.code(), Some(5));
    assert!(!target.path().join(".converge").exists());
}

#[test]
fn frozen_refuses_missing_lock_before_host_mutation() {
    let target = tempfile::tempdir().unwrap();
    manifest(target.path());
    let result = invoke(target.path(), &["solve", "--yes", "--frozen", "--json"]);
    assert_eq!(result.status.code(), Some(4));
    assert!(!target.path().join(".venv").exists());
    assert!(!target.path().join("uv.lock").exists());
}

#[test]
fn preview_is_read_only_and_policy_changes_the_plan_identifier() {
    let target = tempfile::tempdir().unwrap();
    manifest(target.path());
    let plan = assert_success(&invoke(target.path(), &["plan", "--json"]));
    let changed = assert_success(&invoke(
        target.path(),
        &["plan", "--timeout", "7", "--json"],
    ));
    assert_ne!(plan["planId"], changed["planId"]);
    let dry = assert_success(&invoke(target.path(), &["solve", "--dry-run", "--json"]));
    assert_eq!(plan["planId"], dry["selectedPlan"]["planId"]);
    assert!(dry["verification"].is_null());
    assert!(!target.path().join(".converge").exists());
    assert!(!target.path().join(".venv").exists());
}

#[test]
fn relative_target_and_external_environment_override_stay_scoped() {
    let directory = tempfile::tempdir().unwrap();
    let target = directory.path().join("project");
    let external = directory.path().join("external-environment");
    std::fs::create_dir(&target).unwrap();
    std::fs::create_dir(&external).unwrap();
    std::fs::write(external.join("preserve"), "original").unwrap();
    manifest(&target);
    let output = Command::new(env!("CARGO_BIN_EXE_converge"))
        .current_dir(directory.path())
        .args(["solve", "project", "--yes", "--offline", "--json"])
        .env("UV_PROJECT_ENVIRONMENT", &external)
        .env("UV_CACHE_DIR", directory.path().join("cache"))
        .env("CONVERGE_COMMAND_TIMEOUT_SECONDS", "30")
        .output()
        .unwrap();
    assert_success(&output);
    assert!(target.join(".venv").is_dir());
    assert!(!target.join("project").exists());
    assert_eq!(
        std::fs::read_to_string(external.join("preserve")).unwrap(),
        "original"
    );
}
