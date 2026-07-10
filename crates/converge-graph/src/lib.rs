//! Typed dependency graph construction and algorithms.

use std::collections::{BTreeMap, BTreeSet};

use converge_model::{
    Confidence, DiscoverySnapshot, EdgeType, GraphEdge, GraphNode, GraphSnapshot, NodeType,
    SCHEMA_VERSION,
};

/// Build a deterministic typed graph from normalized discovery evidence.
#[must_use]
pub fn build_graph(snapshot: &DiscoverySnapshot) -> GraphSnapshot {
    let fingerprint = &snapshot.repository.source_fingerprint;
    let repository_id = format!("repository:{fingerprint}");
    let mut nodes = BTreeMap::new();
    let mut edges = BTreeMap::new();

    insert_node(
        &mut nodes,
        &repository_id,
        NodeType::Repository,
        fingerprint,
    );

    for project in &snapshot.projects {
        let manifest_id = format!("manifest:{}", project.manifest_path);
        let project_id = format!("project:{}", project.manifest_path);
        insert_node(&mut nodes, &manifest_id, NodeType::Manifest, fingerprint);
        insert_node(&mut nodes, &project_id, NodeType::Project, fingerprint);
        insert_edge(&mut edges, &repository_id, &manifest_id, EdgeType::Contains);
        insert_edge(&mut edges, &manifest_id, &project_id, EdgeType::Declares);

        for requirement in &project.dependencies {
            let package_id = format!("package:{}", requirement.normalized_name);
            insert_node(&mut nodes, &package_id, NodeType::Package, fingerprint);
            insert_edge(&mut edges, &manifest_id, &package_id, EdgeType::Declares);
        }
    }

    for locked in &snapshot.locked_packages {
        let lock_id = format!("lockfile:{}", locked.source);
        let package_id = format!("package:{}", locked.name);
        insert_node(&mut nodes, &lock_id, NodeType::Lockfile, fingerprint);
        insert_node(&mut nodes, &package_id, NodeType::Package, fingerprint);
        insert_edge(&mut edges, &repository_id, &lock_id, EdgeType::Contains);
        if let Some(version) = &locked.version {
            let version_id = format!("package-version:{}@{version}", locked.name);
            insert_node(
                &mut nodes,
                &version_id,
                NodeType::PackageVersion,
                fingerprint,
            );
            insert_edge(&mut edges, &package_id, &version_id, EdgeType::ResolvesTo);
            insert_edge(&mut edges, &lock_id, &version_id, EdgeType::ResolvesTo);
        }
    }

    let mut source_files = BTreeSet::new();
    for import in &snapshot.imports {
        let file_id = format!("file:{}", import.source_path);
        let module_id = format!("module:{}", import.module);
        insert_node(&mut nodes, &file_id, NodeType::File, fingerprint);
        insert_node(&mut nodes, &module_id, NodeType::Module, fingerprint);
        if source_files.insert(file_id.clone()) {
            insert_edge(&mut edges, &repository_id, &file_id, EdgeType::Contains);
        }
        insert_edge(&mut edges, &file_id, &module_id, EdgeType::Imports);
    }

    GraphSnapshot {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "graphSnapshot".to_owned(),
        source_fingerprint: fingerprint.clone(),
        nodes: nodes.into_values().collect(),
        edges: edges.into_values().collect(),
    }
}

fn insert_node(
    nodes: &mut BTreeMap<String, GraphNode>,
    id: &str,
    node_type: NodeType,
    fingerprint: &str,
) {
    nodes
        .entry(id.to_owned())
        .or_insert_with(|| GraphNode::new(id, node_type, fingerprint));
}

fn insert_edge(
    edges: &mut BTreeMap<String, GraphEdge>,
    source: &str,
    target: &str,
    edge_type: EdgeType,
) {
    let id = format!("{source}:{edge_type:?}:{target}");
    edges
        .entry(id.clone())
        .or_insert_with(|| GraphEdge::new(id, source, target, edge_type, Confidence::Certain));
}
