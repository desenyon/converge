from pathlib import Path

import pytest

from converge.graph.store import GraphStore
from converge.models import EntityType, GraphEntity
from converge.project_context import ProjectContext


def test_graph_store_uses_repo_local_database(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    context = ProjectContext.from_target(repo)

    store = GraphStore.for_context(context)
    try:
        store.add_entity(GraphEntity(id="pkg:requests", type=EntityType.PACKAGE, name="requests"))
        assert context.graph_db_path.exists()
    finally:
        store.close()


def test_graph_store_requires_explicit_database_location(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TypeError):
        GraphStore()

    assert not (tmp_path / "converge_graph.db").exists()
