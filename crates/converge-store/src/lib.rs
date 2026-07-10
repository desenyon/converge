//! Repository-local `SQLite` state and migrations.

use std::path::Path;

use converge_core::ConvergeError;
use converge_model::{AuditRecord, AuditReport, GraphEdge, GraphNode, SCHEMA_VERSION};
use rusqlite::{Connection, OptionalExtension};

const MIGRATION_1: &str = include_str!("../migrations/0001_initial.sql");

/// Repository-local derived state store.
pub struct Store {
    connection: Connection,
}

impl Store {
    /// Open a state database and apply forward migrations.
    ///
    /// # Errors
    ///
    /// Returns a storage error when the database cannot be opened or migrated.
    pub fn open(path: &Path) -> Result<Self, ConvergeError> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
        let connection =
            Connection::open(path).map_err(|error| ConvergeError::Store(error.to_string()))?;
        connection
            .pragma_update(None, "journal_mode", "WAL")
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        connection
            .execute_batch(
                "PRAGMA foreign_keys = ON;
                 CREATE TABLE IF NOT EXISTS schema_migrations (
                   version INTEGER PRIMARY KEY,
                   applied_at TEXT NOT NULL
                 );",
            )
            .map_err(|error| ConvergeError::Store(error.to_string()))?;

        let applied = connection
            .query_row(
                "SELECT version FROM schema_migrations WHERE version = 1",
                [],
                |row| row.get::<_, i64>(0),
            )
            .optional()
            .map_err(|error| ConvergeError::Store(error.to_string()))?;

        if applied.is_none() {
            let transaction = connection
                .unchecked_transaction()
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
            transaction
                .execute_batch(MIGRATION_1)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
            transaction
                .execute(
                    "INSERT INTO schema_migrations(version, applied_at)
                     VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                    [],
                )
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
            transaction
                .commit()
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }

        Ok(Self { connection })
    }

    /// Highest applied schema migration.
    ///
    /// # Errors
    ///
    /// Returns a storage error when migration state cannot be queried.
    pub fn schema_version(&self) -> Result<i64, ConvergeError> {
        self.connection
            .query_row("SELECT MAX(version) FROM schema_migrations", [], |row| {
                row.get(0)
            })
            .map_err(|error| ConvergeError::Store(error.to_string()))
    }

    /// Current `SQLite` journal mode.
    ///
    /// # Errors
    ///
    /// Returns a storage error when `SQLite` pragmas cannot be queried.
    pub fn journal_mode(&self) -> Result<String, ConvergeError> {
        self.connection
            .query_row("PRAGMA journal_mode", [], |row| row.get(0))
            .map_err(|error| ConvergeError::Store(error.to_string()))
    }

    /// Atomically replace the derived graph for a source snapshot.
    ///
    /// # Errors
    ///
    /// Returns a storage error when serialization or the transaction fails.
    pub fn replace_graph(
        &self,
        source_fingerprint: &str,
        nodes: &[GraphNode],
        edges: &[GraphEdge],
    ) -> Result<(), ConvergeError> {
        let transaction = self
            .connection
            .unchecked_transaction()
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        transaction
            .execute("DELETE FROM graph_edges", [])
            .and_then(|_| transaction.execute("DELETE FROM graph_nodes", []))
            .map_err(|error| ConvergeError::Store(error.to_string()))?;

        for node in nodes {
            let payload = serde_json::to_string(node)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
            transaction
                .execute(
                    "INSERT INTO graph_nodes(id, node_type, payload_json, source_fingerprint, observed_at)
                     VALUES (?1, ?2, ?3, ?4, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                    rusqlite::params![
                        node.id,
                        format!("{:?}", node.node_type),
                        payload,
                        source_fingerprint
                    ],
                )
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
        for edge in edges {
            let payload = serde_json::to_string(edge)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
            transaction
                .execute(
                    "INSERT INTO graph_edges(id, source_id, target_id, edge_type, evidence_json, confidence, observed_at)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                    rusqlite::params![
                        edge.id,
                        edge.source_id,
                        edge.target_id,
                        format!("{:?}", edge.edge_type),
                        payload,
                        format!("{:?}", edge.confidence)
                    ],
                )
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        }
        transaction
            .commit()
            .map_err(|error| ConvergeError::Store(error.to_string()))
    }

    /// Return persisted graph node and edge counts.
    ///
    /// # Errors
    ///
    /// Returns a storage error when either count cannot be queried.
    pub fn graph_counts(&self) -> Result<(i64, i64), ConvergeError> {
        let nodes = self
            .connection
            .query_row("SELECT COUNT(*) FROM graph_nodes", [], |row| row.get(0))
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        let edges = self
            .connection
            .query_row("SELECT COUNT(*) FROM graph_edges", [], |row| row.get(0))
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        Ok((nodes, edges))
    }

    /// Append one redacted audit event.
    ///
    /// # Errors
    ///
    /// Returns a storage error when the append-only insert fails.
    pub fn append_audit_event(
        &self,
        event_id: &str,
        event_json: &str,
    ) -> Result<(), ConvergeError> {
        self.connection
            .execute(
                "INSERT INTO audit_events(event_id, event_json, recorded_at)
                 VALUES (?1, ?2, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                rusqlite::params![event_id, event_json],
            )
            .map(|_| ())
            .map_err(|error| ConvergeError::Store(error.to_string()))
    }

    /// Read the append-only audit log without creating or migrating state.
    ///
    /// # Errors
    ///
    /// Returns a storage error when state is absent or records cannot be read.
    pub fn read_audit(path: &Path) -> Result<AuditReport, ConvergeError> {
        if !path.is_file() {
            return Err(ConvergeError::Store(format!(
                "state database does not exist: {}",
                path.display()
            )));
        }
        let connection =
            Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
                .map_err(|error| ConvergeError::Store(error.to_string()))?;
        let mut statement = connection
            .prepare(
                "SELECT sequence, event_id, event_json, recorded_at
                 FROM audit_events ORDER BY sequence",
            )
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        let records = statement
            .query_map([], |row| {
                Ok(AuditRecord {
                    sequence: row.get(0)?,
                    event_id: row.get(1)?,
                    event_json: row.get(2)?,
                    recorded_at: row.get(3)?,
                })
            })
            .map_err(|error| ConvergeError::Store(error.to_string()))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| ConvergeError::Store(error.to_string()))?;
        Ok(AuditReport {
            schema_version: SCHEMA_VERSION.to_owned(),
            kind: "auditReport".to_owned(),
            records,
        })
    }
}
