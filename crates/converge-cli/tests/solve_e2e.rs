#![allow(missing_docs)]

use std::path::{Path, PathBuf};
use std::process::Command;

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

#[test]
#[ignore = "requires public package registry access; run explicitly in CI"]
fn solve_validates_applies_installs_and_undoes() {
    let target = tempfile::tempdir().expect("target");
    copy_fixture(target.path());
    let original = std::fs::read_to_string(target.path().join("pyproject.toml")).expect("original");
    let cache = tempfile::tempdir().expect("isolated uv cache");

    let solve = Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(["solve", "--yes", "--json"])
        .env("UV_CACHE_DIR", cache.path())
        .env("CONVERGE_NETWORK", "allow")
        .env("CONVERGE_COMMAND_TIMEOUT_SECONDS", "60")
        .arg(target.path())
        .output()
        .expect("solve");
    assert!(
        solve.status.success(),
        "stderr: {}\nstdout: {}",
        String::from_utf8_lossy(&solve.stderr),
        String::from_utf8_lossy(&solve.stdout)
    );
    let report: serde_json::Value = serde_json::from_slice(&solve.stdout).expect("solve JSON");
    assert_eq!(report["kind"], "solveReport");
    assert_eq!(report["verification"]["passed"], true);
    assert!(report["appliedChanges"].is_object());
    assert!(target.path().join("uv.lock").is_file());
    assert!(target.path().join(".venv").is_dir());

    let audit = Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(["audit", "--json"])
        .arg(target.path())
        .output()
        .expect("audit");
    assert!(audit.status.success());
    let audit: serde_json::Value = serde_json::from_slice(&audit.stdout).expect("audit JSON");
    assert_eq!(audit["kind"], "auditReport");
    assert_eq!(audit["records"].as_array().expect("records").len(), 1);

    let undo = Command::new(env!("CARGO_BIN_EXE_converge"))
        .arg("undo")
        .arg(target.path())
        .output()
        .expect("undo");
    assert!(
        undo.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&undo.stderr)
    );
    assert_eq!(
        std::fs::read_to_string(target.path().join("pyproject.toml")).expect("restored"),
        original
    );
    assert!(!target.path().join("uv.lock").exists());
    assert!(!target.path().join(".venv").exists());
}

#[test]
fn offline_failure_never_mutates_the_host() {
    let target = tempfile::tempdir().expect("target");
    let empty_cache = tempfile::tempdir().expect("cache");
    copy_fixture(target.path());
    let original = std::fs::read_to_string(target.path().join("pyproject.toml")).expect("original");

    let solve = Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(["solve", "--yes", "--offline", "--json"])
        .arg(target.path())
        .env("UV_CACHE_DIR", empty_cache.path())
        .output()
        .expect("solve");
    assert_eq!(solve.status.code(), Some(5));
    assert_eq!(
        std::fs::read_to_string(target.path().join("pyproject.toml")).expect("unchanged"),
        original
    );
    assert!(!target.path().join("uv.lock").exists());
    assert!(!target.path().join(".venv").exists());
}
