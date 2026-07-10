#![allow(missing_docs)]

use std::collections::BTreeSet;
use std::path::PathBuf;

use converge_model::DiscoverySnapshot;

fn schemas_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../schemas")
}

#[test]
fn every_schema_is_valid_json_with_a_versioned_identifier() {
    for directory in ["output", "config", "events"] {
        for entry in std::fs::read_dir(schemas_root().join(directory)).expect("schema directory") {
            let path = entry.expect("schema entry").path();
            let value: serde_json::Value =
                serde_json::from_slice(&std::fs::read(&path).expect("schema bytes"))
                    .expect("valid schema JSON");
            assert_eq!(
                value["$schema"],
                "https://json-schema.org/draft/2020-12/schema"
            );
            assert!(
                value["$id"].as_str().is_some_and(|id| id.contains("1.0.0")),
                "unversioned schema: {}",
                path.display()
            );
        }
    }
}

#[test]
fn discovery_schema_covers_every_serialized_top_level_field() {
    let schema: serde_json::Value = serde_json::from_slice(
        &std::fs::read(schemas_root().join("output/discovery-snapshot.schema.json"))
            .expect("schema"),
    )
    .expect("schema JSON");
    let snapshot = serde_json::to_value(DiscoverySnapshot::empty("/project")).expect("snapshot");

    let schema_fields: BTreeSet<_> = schema["properties"]
        .as_object()
        .expect("properties")
        .keys()
        .map(String::as_str)
        .collect();
    let contract_fields: BTreeSet<_> = snapshot
        .as_object()
        .expect("snapshot object")
        .keys()
        .map(String::as_str)
        .collect();
    assert_eq!(schema_fields, contract_fields);
}
