#![allow(missing_docs)]

use converge_model::{Confidence, EdgeType, GraphEdge, GraphNode, NodeType};
use converge_store::Store;

#[test]
fn persists_and_replaces_a_snapshot_graph() {
    let temp = tempfile::tempdir().expect("tempdir");
    let store = Store::open(&temp.path().join("state.db")).expect("store");
    let nodes = vec![
        GraphNode::new("repo", NodeType::Repository, "fingerprint"),
        GraphNode::new("manifest", NodeType::Manifest, "fingerprint"),
    ];
    let edges = vec![GraphEdge::new(
        "declares",
        "repo",
        "manifest",
        EdgeType::Contains,
        Confidence::Certain,
    )];

    store
        .replace_graph("fingerprint", &nodes, &edges)
        .expect("persist");
    let (node_count, edge_count) = store.graph_counts().expect("counts");
    assert_eq!((node_count, edge_count), (2, 1));
}

#[test]
fn audit_insert_failure_rolls_back_graph_replacement() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("state.db");
    let store = Store::open(&path).unwrap();
    let graph = converge_model::GraphSnapshot {
        schema_version: converge_model::SCHEMA_VERSION.to_owned(),
        kind: "graphSnapshot".to_owned(),
        source_fingerprint: "before".to_owned(),
        nodes: vec![GraphNode::new("repo", NodeType::Repository, "before")],
        edges: vec![],
    };
    store.record_application(&graph, "event", "{}").unwrap();
    let changed = converge_model::GraphSnapshot {
        nodes: vec![],
        source_fingerprint: "after".to_owned(),
        ..graph
    };
    assert!(store.record_application(&changed, "event", "{}").is_err());
    assert_eq!(store.graph_counts().unwrap(), (1, 0));
    assert_eq!(Store::read_audit(&path).unwrap().records.len(), 1);
}

#[cfg(unix)]
#[test]
fn state_database_symlinks_are_rejected() {
    let temp = tempfile::tempdir().unwrap();
    let external = temp.path().join("external.db");
    std::fs::write(&external, "preserve").unwrap();
    let path = temp.path().join("state.db");
    std::os::unix::fs::symlink(&external, &path).unwrap();
    assert!(Store::open(&path).is_err());
    assert_eq!(std::fs::read_to_string(&external).unwrap(), "preserve");
}
