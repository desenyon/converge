from pathlib import Path

import networkx as nx

from converge.env_manager import EnvironmentManager
from converge.models import EntityType, RelationshipType
from converge.project_context import ProjectContext
from converge.solver.conflict import ConflictDetector, ConflictType


def test_plan_packages_uses_constraints(tmp_path: Path) -> None:
    context = ProjectContext.from_target(tmp_path)
    manager = EnvironmentManager(context)
    graph = nx.DiGraph()
    graph.add_node("pkg:requests", type=EntityType.PACKAGE, name="requests")
    graph.add_edge(
        "repo:x",
        "pkg:requests",
        type=RelationshipType.REQUIRES,
        metadata={"constraint": "requests>=2.28", "dependency_group": "main"},
    )
    assert manager.plan_packages(graph) == ["requests>=2.28"]


def test_dev_group_not_flagged_unused(tmp_path: Path) -> None:
    graph = nx.DiGraph()
    graph.add_node("pkg:ruff", type=EntityType.PACKAGE, name="ruff")
    graph.add_edge(
        "repo:x",
        "pkg:ruff",
        type=RelationshipType.REQUIRES,
        metadata={"dependency_group": "dev", "constraint": "ruff>=0.3"},
    )
    detector = ConflictDetector(graph)
    unused = [c for c in detector.detect_all() if c.type == ConflictType.UNUSED_DEPENDENCY]
    assert unused == []
