#![allow(missing_docs)]

use converge_discovery::discover;
use converge_model::RepairAction;
use converge_planner::{diagnose, plan};
use std::path::PathBuf;

#[test]
fn missing_lock_has_an_explicit_action_and_real_environment_checks() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(
        root.path().join("pyproject.toml"),
        "[project]\nname='demo'\nversion='0.1.0'\nrequires-python='>=3.11'\ndependencies=[]\n",
    )
    .unwrap();
    let snapshot = discover(root.path()).unwrap();
    let repair = plan(&snapshot, &diagnose(&snapshot));
    assert!(
        repair
            .actions
            .iter()
            .any(|a| matches!(a, RepairAction::GenerateLockfile { .. }))
    );
    assert!(
        repair
            .verification_contract
            .checks
            .iter()
            .any(|c| c.arguments == ["sync", "--frozen"])
    );
    assert!(
        repair
            .verification_contract
            .checks
            .iter()
            .any(|c| c.arguments.first().is_some_and(|a| a == "run"))
    );
}

#[test]
fn discovery_only_backends_never_receive_uv_repairs() {
    for fixture in ["poetry_basic", "conda_env", "uv_workspace"] {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../fixtures/python")
            .join(fixture);
        let snapshot = discover(root).unwrap();
        let repair = plan(&snapshot, &diagnose(&snapshot));
        assert!(
            repair
                .actions
                .iter()
                .all(|a| matches!(a, RepairAction::NoChange { .. })),
            "{fixture}"
        );
        assert_eq!(repair.verification_contract.checks.len(), 0, "{fixture}");
        assert_ne!(repair.unresolved_uncertainty.len(), 0, "{fixture}");
    }
}

#[test]
fn sibling_project_dependency_does_not_satisfy_another_projects_import() {
    let root = tempfile::tempdir().unwrap();
    for name in ["a", "b"] {
        std::fs::create_dir(root.path().join(name)).unwrap();
    }
    std::fs::write(
        root.path().join("a/pyproject.toml"),
        "[project]\nname='a'\ndependencies=['httpx']\n",
    )
    .unwrap();
    std::fs::write(
        root.path().join("b/pyproject.toml"),
        "[project]\nname='b'\ndependencies=[]\n",
    )
    .unwrap();
    std::fs::write(root.path().join("b/app.py"), "import httpx\n").unwrap();
    let snapshot = discover(root.path()).unwrap();
    assert!(
        diagnose(&snapshot)
            .diagnostics
            .iter()
            .any(
                |d| d.diagnostic_type == converge_model::DiagnosticType::MissingDependency
                    && d.evidence.contains(&"b/app.py:1".to_owned())
            )
    );
}
