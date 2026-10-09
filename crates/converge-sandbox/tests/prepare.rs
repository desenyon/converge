#![allow(missing_docs)]

use std::path::PathBuf;

use converge_discovery::discover;
use converge_planner::{diagnose, plan};
use converge_sandbox::PreparedSandbox;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/python")
        .join(name)
}

#[test]
fn applies_plan_only_to_temporary_snapshot() {
    let target = fixture("broken_missing");
    let original = std::fs::read_to_string(target.join("pyproject.toml")).expect("original");
    let snapshot = discover(&target).expect("discover");
    let repair = plan(&snapshot, &diagnose(&snapshot));

    let sandbox = PreparedSandbox::create(&target, &repair).expect("sandbox");
    let changed =
        std::fs::read_to_string(sandbox.root().join("pyproject.toml")).expect("sandbox manifest");

    assert!(changed.contains(r#""httpx""#));
    assert!(changed.contains(r#""rich""#));
    assert_eq!(
        std::fs::read_to_string(target.join("pyproject.toml")).expect("host manifest"),
        original
    );
    assert_ne!(sandbox.root(), target);
}

#[tokio::test]
async fn empty_required_contract_is_not_success() {
    let target = fixture("broken_missing");
    let snapshot = discover(&target).unwrap();
    let mut repair = plan(&snapshot, &diagnose(&snapshot));
    repair.verification_contract.checks.clear();
    assert!(
        converge_sandbox::validate(&target, &repair, true)
            .await
            .is_err()
    );
}

#[tokio::test]
async fn advisory_failure_is_recorded_without_failing_required_checks() {
    let target = fixture("broken_missing");
    let snapshot = discover(&target).unwrap();
    let mut repair = plan(&snapshot, &diagnose(&snapshot));
    repair.actions.clear();
    repair.verification_contract.checks = vec![
        converge_model::ToolInvocation {
            tool: "uv".to_owned(),
            arguments: vec!["--version".to_owned()],
            required: true,
            timeout_seconds: 5,
        },
        converge_model::ToolInvocation {
            tool: "uv".to_owned(),
            arguments: vec!["invalid-converge-test-command".to_owned()],
            required: false,
            timeout_seconds: 5,
        },
    ];
    let report = converge_sandbox::validate(&target, &repair, true)
        .await
        .unwrap();
    assert!(report.passed);
    assert!(!report.checks.last().unwrap().passed);
}

#[test]
fn sandbox_rejects_stale_source_and_escaping_actions() {
    let target = fixture("broken_missing");
    let snapshot = discover(&target).unwrap();
    let mut repair = plan(&snapshot, &diagnose(&snapshot));
    repair.source_fingerprint = "stale".to_owned();
    assert!(PreparedSandbox::create(&target, &repair).is_err());
    repair.source_fingerprint = snapshot.repository.source_fingerprint;
    if let converge_model::RepairAction::AddDependency { manifest_path, .. } =
        &mut repair.actions[0]
    {
        *manifest_path = "../outside.toml".to_owned();
    }
    assert!(PreparedSandbox::create(&target, &repair).is_err());
}
