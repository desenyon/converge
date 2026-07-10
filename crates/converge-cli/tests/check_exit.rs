#![allow(missing_docs)]

use std::path::PathBuf;
use std::process::Command;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/python")
        .join(name)
}

#[test]
fn check_returns_one_for_detected_issues_and_json_report() {
    let output = Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(["check", "--json"])
        .arg(fixture("broken_missing"))
        .output()
        .expect("run converge");

    assert_eq!(output.status.code(), Some(1));
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).expect("JSON");
    assert_eq!(value["kind"], "diagnosticReport");
    assert_eq!(
        value["diagnostics"].as_array().expect("diagnostics").len(),
        2
    );
}
