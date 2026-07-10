#![allow(missing_docs)]

use std::process::Command;

#[test]
fn discover_emits_only_versioned_json() {
    let temp = tempfile::tempdir().expect("tempdir");
    let output = Command::new(env!("CARGO_BIN_EXE_converge"))
        .args(["discover", "--json"])
        .arg(temp.path())
        .output()
        .expect("run converge");

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stderr.is_empty(), "JSON mode must keep stderr quiet");
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).expect("valid JSON");
    assert_eq!(value["schemaVersion"], "1.0.0");
    assert_eq!(value["kind"], "discoverySnapshot");
}
