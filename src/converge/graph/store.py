from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import networkx as nx
from sqlalchemy import text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from converge.models import EntityType, GraphEntity, GraphRelationship, RelationshipType


# SQLModel classes for SQLite persistence
class SQLEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str  # Map to EntityType
    name: str
    metadata_json: str = "{}"  # JSON serialized metadata

    def to_pydantic(self) -> GraphEntity:
        return GraphEntity(
            id=self.id,
            type=EntityType(self.type),
            name=self.name,
            metadata=json.loads(self.metadata_json),
        )

    @classmethod
    def from_pydantic(cls, entity: GraphEntity) -> SQLEntity:
        return cls(
            id=entity.id,
            type=entity.type.value,
            name=entity.name,
            metadata_json=json.dumps(entity.metadata),
        )


class SQLRelationship(SQLModel, table=True):
    # Composite PK logically: source, target, type
    # For SQLModel without explicit composite primary key class simplicity, we use a surrogate
    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(index=True)
    target_id: str = Field(index=True)
    type: str  # Map to RelationshipType
    metadata_json: str = "{}"

    def to_pydantic(self) -> GraphRelationship:
        return GraphRelationship(
            source_id=self.source_id,
            target_id=self.target_id,
            type=RelationshipType(self.type),
            metadata=json.loads(self.metadata_json),
        )

    @classmethod
    def from_pydantic(cls, rel: GraphRelationship) -> SQLRelationship:
        return cls(
            source_id=rel.source_id,
            target_id=rel.target_id,
            type=rel.type.value,
            metadata_json=json.dumps(rel.metadata),
        )


class GraphStore:
    """
    Manages physical persistence of the graph using SQLModel (SQLite).
    Provides methods to persist and re-hydrate NetworkX graphs.
    """

    def __init__(self, db_url: str = "sqlite:///converge_graph.db"):
        self.engine = create_engine(db_url)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            yield session

    def add_entity(self, entity: GraphEntity) -> None:
        with Session(self.engine) as session:
            sql_ent = SQLEntity.from_pydantic(entity)
            session.merge(sql_ent)
            session.commit()

    def add_relationship(self, rel: GraphRelationship) -> None:
        with Session(self.engine) as session:
            # Simple deduplication strategy
            stmt = select(SQLRelationship).where(
                SQLRelationship.source_id == rel.source_id,
                SQLRelationship.target_id == rel.target_id,
                SQLRelationship.type == rel.type.value,
            )
            existing = session.exec(stmt).first()
            if not existing:
                sql_rel = SQLRelationship.from_pydantic(rel)
                session.add(sql_rel)
                session.commit()

    def load_networkx(self) -> nx.DiGraph[Any]:
        """Hydrates a fully loaded NetworkX directed graph from SQLite."""
        G: nx.DiGraph[Any] = nx.DiGraph()
        with Session(self.engine) as session:
            entities = session.exec(select(SQLEntity)).all()
            for e in entities:
                p_ent = e.to_pydantic()
                G.add_node(p_ent.id, **p_ent.model_dump())

            rels = session.exec(select(SQLRelationship)).all()
            for r in rels:
                p_rel = r.to_pydantic()
                G.add_edge(
                    p_rel.source_id, p_rel.target_id, type=p_rel.type, metadata=p_rel.metadata
                )
        return G

    def save_networkx(self, G: nx.DiGraph[Any]) -> None:
        """Persists a NetworkX digraph into SQLite."""
        with Session(self.engine) as session:
            # Clear existing logic for hard reset, or intelligent merge.
            # Fast path: wipe and replace
            session.execute(text("DELETE FROM sqlrelationship"))
            session.execute(text("DELETE FROM sqlentity"))

            for _node_id, data in G.nodes(data=True):
                ent = GraphEntity.model_validate(data)
                session.add(SQLEntity.from_pydantic(ent))

            for src, dst, data in G.edges(data=True):
                rel = GraphRelationship(
                    source_id=src,
                    target_id=dst,
                    type=data["type"],
                    metadata=data.get("metadata", {}),
                )
                session.add(SQLRelationship.from_pydantic(rel))

            session.commit()
