#![cfg(unix)]
#![allow(missing_docs)]

use std::os::unix::fs::PermissionsExt;
use std::process::Command;

fn setup(script: &str) -> (tempfile::TempDir, tempfile::TempDir) {
    let target = tempfile::tempdir().unwrap();
    std::fs::write(
        target.path().join("pyproject.toml"),
        "[project]\nname='policy-test'\nversion='0.1.0'\ndependencies=[]\n",
    )
    .unwrap();
    let tools = tempfile::tempdir().unwrap();
    let binary = tools.path().join("uv");
    std::fs::write(&binary, format!("#!/bin/sh\n{script}\n")).unwrap();
    std::fs::set_permissions(binary, std::fs::Permissions::from_mode(0o755)).unwrap();
    (target, tools)
}
fn command(target: &tempfile::TempDir, tools: &tempfile::TempDir) -> Command {
    let paths = std::env::join_paths(
        std::iter::once(tools.path().to_path_buf())
            .chain(std::env::split_paths(&std::env::var_os("PATH").unwrap())),
    )
    .unwrap();
    let mut command = Command::new(env!("CARGO_BIN_EXE_converge"));
    command
        .args(["verify", "--json"])
        .arg(target.path())
        .env("PATH", paths)
        .env_remove("CONVERGE_NETWORK")
        .env_remove("CONVERGE_COMMAND_TIMEOUT_SECONDS");
    command
}

#[test]
fn repository_network_policy_is_enforced_for_every_validation_command() {
    let (target, tools) = setup(
        "[ \"$1\" = --offline ] || exit 42\nshift\nif [ \"$1\" = --version ]; then echo 'uv test'; fi\nexit 0",
    );
    std::fs::write(
        target.path().join(".converge.toml"),
        "network='deny'\ncommandTimeoutSeconds=5\n",
    )
    .unwrap();
    let output = command(&target, &tools).output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stdout)
    );
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["networkAllowed"], false);
    assert!(report["checks"].as_array().unwrap().len() >= 5);
}

#[test]
fn configured_timeout_terminates_a_stalled_command() {
    let (target, tools) =
        setup("if [ \"$1\" = --version ]; then echo 'uv test'; exit 0; fi\nexec sleep 10");
    std::fs::write(
        target.path().join(".converge.toml"),
        "commandTimeoutSeconds=1\n",
    )
    .unwrap();
    let start = std::time::Instant::now();
    let output = command(&target, &tools).output().unwrap();
    assert_eq!(output.status.code(), Some(5));
    assert!(start.elapsed().as_secs() < 8);
    assert!(String::from_utf8_lossy(&output.stdout).contains("timed out after 1 seconds"));
    assert!(!target.path().join(".venv").exists());
}

#[test]
fn noisy_stdout_and_stderr_are_drained_and_bounded() {
    let (target, tools) = setup(
        "if [ \"$1\" = --version ]; then echo 'uv test'; exit 0; fi\ni=0\nwhile [ \"$i\" -lt 8000 ]; do\n echo 'long public diagnostic output'; echo 'long public diagnostic error' >&2\n i=$((i+1))\ndone\nexit 1",
    );
    let output = command(&target, &tools).output().unwrap();
    assert_eq!(output.status.code(), Some(5));
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    let failed = &report["checks"][1];
    for stream in ["stdout", "stderr"] {
        let text = failed[stream].as_str().unwrap();
        assert!(text.len() < 65_600);
        assert!(text.contains("output truncated"));
    }
    assert_eq!(report["checks"].as_array().unwrap().len(), 2);
}
