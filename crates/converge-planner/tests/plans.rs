#![allow(missing_docs)]

use std::path::PathBuf;

use converge_discovery::discover;
use converge_model::RepairAction;
use converge_planner::{diagnose, plan};

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/python")
        .join(name)
}

#[test]
fn creates_minimal_deterministic_plan_for_missing_dependencies() {
    let snapshot = discover(fixture("broken_missing")).expect("discover");
    let diagnostics = diagnose(&snapshot);
    let first = plan(&snapshot, &diagnostics);
    let second = plan(&snapshot, &diagnostics);

    assert_eq!(first, second);
    let additions: Vec<_> = first
        .actions
        .iter()
        .filter_map(|action| match action {
            RepairAction::AddDependency { distribution, .. } => Some(distribution.as_str()),
            _ => None,
        })
        .collect();
    assert_eq!(additions, ["httpx", "rich"]);
    assert!(matches!(
        first.actions.last(),
        Some(RepairAction::GenerateLockfile { .. })
    ));
    assert!(first.network_required);
    assert_ne!(first.file_diff_preview.len(), 0);
}
