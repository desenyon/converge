#![allow(missing_docs)]

use converge_model::{DiscoverySnapshot, SCHEMA_VERSION};

#[test]
fn discovery_snapshot_is_versioned() {
    let snapshot = DiscoverySnapshot::empty("/tmp/project");
    assert_eq!(snapshot.schema_version, SCHEMA_VERSION);
    assert_eq!(snapshot.repository.target, "/tmp/project");
}
