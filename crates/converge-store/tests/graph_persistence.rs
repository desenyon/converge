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
