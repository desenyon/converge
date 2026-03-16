from pathlib import Path

import networkx as nx

from converge.env_manager import EnvironmentManager
from converge.models import EntityType
from converge.project_context import ProjectContext


def test_env_manager_plans_install_from_repo_graph(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    context = ProjectContext.from_target(repo)
    manager = EnvironmentManager(context)

    graph = nx.DiGraph()
    graph.add_node("pkg:requests", type=EntityType.PACKAGE, name="requests")
    graph.add_node("pkg:fastapi", type=EntityType.PACKAGE, name="fastapi")
    graph.add_node("mod:main.py", type=EntityType.MODULE, name="main.py")

    assert manager.plan_packages(graph) == ["fastapi", "requests"]
