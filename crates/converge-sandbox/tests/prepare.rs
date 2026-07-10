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
