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
    assert_eq!(snapshot.projects[0].backend, "pep621");
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
fn discovers_poetry_project_and_lockfile() {
    let snapshot = discover(fixture("poetry_basic")).expect("discover poetry fixture");

    assert_eq!(snapshot.projects.len(), 1);
    assert_eq!(snapshot.projects[0].name.as_deref(), Some("poetry-app"));
    assert_eq!(snapshot.projects[0].backend, "poetry");
    assert_eq!(
        snapshot.projects[0].requires_python.as_deref(),
        Some("^3.12")
    );
    let deps: Vec<_> = snapshot.projects[0]
        .dependencies
        .iter()
        .map(|item| (item.normalized_name.as_str(), item.group.as_str()))
        .collect();
    assert!(deps.contains(&("httpx", "default")));
    assert!(deps.contains(&("pytest", "dev")));
    assert_eq!(snapshot.lockfiles.len(), 1);
    assert_eq!(snapshot.lockfiles[0].format, "poetry.lock");
    assert!(
        snapshot
            .locked_packages
            .iter()
            .any(|package| package.name == "httpx")
    );
    assert!(snapshot.imports.iter().any(|item| item.module == "httpx"));
    assert!(
        snapshot
            .package_managers
            .iter()
            .any(|item| item.name == "poetry")
    );
}

#[test]
fn discovers_conda_environment_file() {
    let snapshot = discover(fixture("conda_env")).expect("discover conda fixture");

    assert_eq!(snapshot.projects.len(), 1);
    assert_eq!(snapshot.projects[0].backend, "conda");
    assert_eq!(snapshot.projects[0].name.as_deref(), Some("conda-app"));
    assert_eq!(
        snapshot.projects[0].requires_python.as_deref(),
        Some("==3.12")
    );
    let deps: Vec<_> = snapshot.projects[0]
        .dependencies
        .iter()
        .map(|item| (item.normalized_name.as_str(), item.group.as_str()))
        .collect();
    assert!(deps.contains(&("numpy", "default")));
    assert!(deps.contains(&("requests", "pip")));
    assert!(snapshot.imports.iter().any(|item| item.module == "numpy"));
    assert!(
        snapshot
            .imports
            .iter()
            .any(|item| item.module == "requests")
    );
    assert!(
        snapshot
            .package_managers
            .iter()
            .any(|item| item.name == "conda")
    );
}

#[test]
fn discovers_uv_workspace_members() {
    let snapshot = discover(fixture("uv_workspace")).expect("discover workspace fixture");

    assert_eq!(snapshot.workspaces.len(), 1);
    assert_eq!(snapshot.workspaces[0].kind, "uv");
    assert_eq!(snapshot.workspaces[0].root, "pyproject.toml");
    assert_eq!(
        snapshot.workspaces[0].members,
        vec![
            "packages/api/pyproject.toml".to_owned(),
            "packages/worker/pyproject.toml".to_owned(),
        ]
    );
    assert_eq!(snapshot.projects.len(), 3);
    let names: Vec<_> = snapshot
        .projects
        .iter()
        .filter_map(|project| project.name.as_deref())
        .collect();
    assert_eq!(names, ["api", "worker", "uv-workspace-root"]);
    assert!(snapshot.projects.iter().any(|project| {
        project.name.as_deref() == Some("api")
            && project
                .dependencies
                .iter()
                .any(|dep| dep.normalized_name == "httpx")
    }));
    assert!(
        snapshot
            .package_managers
            .iter()
            .any(|item| item.name == "uv")
    );
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
