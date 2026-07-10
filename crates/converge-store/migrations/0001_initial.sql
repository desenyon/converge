CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE graph_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    confidence TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX graph_edges_source_idx ON graph_edges(source_id);
CREATE INDEX graph_edges_target_idx ON graph_edges(target_id);
