#![allow(missing_docs)]

use std::path::PathBuf;

use converge_discovery::discover;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/python")
        .join(name)
}

#[test]
fn discovers_clean_uv_project_evidence() {
    let snapshot = discover(fixture("clean_uv")).expect("discover clean fixture");

    assert_eq!(snapshot.projects.len(), 1);
    assert_eq!(snapshot.projects[0].name.as_deref(), Some("clean-app"));
    assert_eq!(
        snapshot.projects[0].requires_python.as_deref(),
        Some(">=3.12")
    );
    assert_eq!(
        snapshot.projects[0].dependencies[0].normalized_name,
        "httpx"
    );
    assert_eq!(snapshot.lockfiles.len(), 1);
    assert!(snapshot.imports.iter().any(|item| item.module == "httpx"));
    assert!(
        snapshot
            .package_managers
            .iter()
            .any(|item| item.name == "uv")
    );
}

#[test]
fn discovers_undeclared_imports_as_evidence_without_diagnosing() {
    let snapshot = discover(fixture("broken_missing")).expect("discover broken fixture");

    let modules: Vec<_> = snapshot
        .imports
        .iter()
        .map(|item| item.module.as_str())
        .collect();
    assert_eq!(modules, ["httpx", "rich"]);
    assert!(snapshot.projects[0].dependencies.is_empty());
}

#[test]
fn source_fingerprint_changes_with_relevant_content() {
    let temp = tempfile::tempdir().expect("tempdir");
    std::fs::write(
        temp.path().join("pyproject.toml"),
        "[project]\nname='first'\n",
    )
    .expect("write manifest");
    let first = discover(temp.path()).expect("first discovery");

    std::fs::write(
        temp.path().join("pyproject.toml"),
        "[project]\nname='second'\n",
    )
    .expect("write manifest");
    let second = discover(temp.path()).expect("second discovery");

    assert_ne!(
        first.repository.source_fingerprint,
        second.repository.source_fingerprint
    );
}
