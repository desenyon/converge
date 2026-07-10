#![allow(missing_docs)]

use converge_store::Store;

#[test]
fn migration_is_idempotent_and_enables_wal() {
    let temp = tempfile::tempdir().expect("tempdir");
    let path = temp.path().join("state.db");
    let store = Store::open(&path).expect("first open");
    assert_eq!(store.schema_version().expect("schema version"), 1);
    drop(store);

    let store = Store::open(&path).expect("second open");
    assert_eq!(store.schema_version().expect("schema version"), 1);
    assert_eq!(store.journal_mode().expect("journal mode"), "wal");
}
