#![allow(missing_docs)]

use std::path::PathBuf;

use converge_discovery::discover;
use converge_model::{DiagnosticType, Severity};
use converge_planner::diagnose;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/python")
        .join(name)
}

#[test]
fn diagnoses_missing_dependencies_with_source_evidence() {
    let snapshot = discover(fixture("broken_missing")).expect("discover");
    let report = diagnose(&snapshot);

    let missing: Vec<_> = report
        .diagnostics
        .iter()
        .filter(|item| item.diagnostic_type == DiagnosticType::MissingDependency)
        .collect();
    assert_eq!(missing.len(), 2);
    assert_eq!(missing[0].severity, Severity::Error);
    assert!(!missing[0].evidence.is_empty());
    assert!(missing[0].blocks_environment_creation);
}

#[test]
fn clean_fixture_has_no_blocking_diagnostics() {
    let snapshot = discover(fixture("clean_uv")).expect("discover");
    let report = diagnose(&snapshot);

    assert!(
        !report
            .diagnostics
            .iter()
            .any(|item| item.severity == Severity::Error)
    );
}

#[test]
fn declared_same_name_import_is_usage_evidence_not_a_missing_guess() {
    let temp = tempfile::tempdir().expect("tempdir");
    std::fs::create_dir_all(temp.path().join("src")).expect("src");
    std::fs::write(
        temp.path().join("pyproject.toml"),
        "[project]\nname='example'\ndependencies=['requests>=2']\n",
    )
    .expect("manifest");
    std::fs::write(temp.path().join("src/app.py"), "import requests\n").expect("source");
    let snapshot = discover(temp.path()).expect("discover");
    let report = diagnose(&snapshot);

    assert!(report.diagnostics.is_empty());
}
