#![allow(missing_docs)]

use converge_graph::build_graph;
use converge_model::{
    DiscoverySnapshot, EdgeType, ImportEvidence, NodeType, PythonProject, WorkspaceEvidence,
};

#[test]
fn builds_stable_typed_nodes_and_edges() {
    let mut snapshot = DiscoverySnapshot::empty("/project");
    snapshot.repository.source_fingerprint = "abc".to_owned();
    snapshot.projects.push(PythonProject {
        manifest_path: "pyproject.toml".to_owned(),
        name: Some("example".to_owned()),
        requires_python: Some(">=3.12".to_owned()),
        backend: "pep621".to_owned(),
        dependencies: Vec::new(),
    });
    snapshot.imports.push(ImportEvidence {
        module: "httpx".to_owned(),
        source_path: "src/example.py".to_owned(),
        line: 1,
        kind: "import".to_owned(),
    });

    let graph = build_graph(&snapshot);
    assert!(
        graph
            .nodes
            .iter()
            .any(|node| node.node_type == NodeType::Repository)
    );
    assert!(
        graph
            .nodes
            .iter()
            .any(|node| node.node_type == NodeType::Module)
    );
    assert!(
        graph
            .edges
            .iter()
            .any(|edge| edge.edge_type == EdgeType::Imports)
    );

    let again = build_graph(&snapshot);
    assert_eq!(graph, again);
}

#[test]
fn includes_workspace_nodes_for_member_projects() {
    let mut snapshot = DiscoverySnapshot::empty("/project");
    snapshot.repository.source_fingerprint = "ws".to_owned();
    snapshot.projects.push(PythonProject {
        manifest_path: "packages/api/pyproject.toml".to_owned(),
        name: Some("api".to_owned()),
        requires_python: Some(">=3.12".to_owned()),
        backend: "pep621".to_owned(),
        dependencies: Vec::new(),
    });
    snapshot.workspaces.push(WorkspaceEvidence {
        kind: "uv".to_owned(),
        root: "pyproject.toml".to_owned(),
        members: vec!["packages/api/pyproject.toml".to_owned()],
    });

    let graph = build_graph(&snapshot);
    assert!(
        graph
            .nodes
            .iter()
            .any(|node| node.node_type == NodeType::Workspace)
    );
    assert!(graph.edges.iter().any(|edge| {
        edge.edge_type == EdgeType::Contains
            && edge.source_id.starts_with("workspace:")
            && edge.target_id == "project:packages/api/pyproject.toml"
    }));
}
