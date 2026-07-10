#![allow(missing_docs)]

use converge_discovery::resolve_target;

#[test]
fn target_must_be_an_existing_directory() {
    let temp = tempfile::tempdir().expect("tempdir");
    let resolved = resolve_target(temp.path()).expect("directory resolves");
    assert!(resolved.is_absolute());
    assert!(resolve_target(temp.path().join("missing")).is_err());
}
