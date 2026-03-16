from pathlib import Path

from converge.graph.store import GraphStore
from converge.models import EntityType, GraphEntity
from converge.project_context import ProjectContext


def test_graph_store_uses_repo_local_database(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    context = ProjectContext.from_target(repo)

    store = GraphStore.for_context(context)
    store.add_entity(GraphEntity(id="pkg:requests", type=EntityType.PACKAGE, name="requests"))

    assert context.graph_db_path.exists()
