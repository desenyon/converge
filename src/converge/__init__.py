"""
Converge API
Main entrypoints for using Converge programmatically.
"""

from converge.exporter import GraphExporter
from converge.graph.queries import GraphQueries
from converge.graph.store import GraphStore
from converge.models import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    Module,
    Package,
    RelationshipType,
    Repository,
    Route,
)
from converge.project_context import ProjectContext
from converge.scanner.scanner import Scanner
from converge.solver.conflict import ConflictDetector, ConflictType
from converge.solver.planner import RepairPlan, RepairPlanner
from converge.validation.sandbox import UVSandbox
from converge.validation.smoke import ValidationRunner

__all__ = [
    "Scanner",
    "GraphStore",
    "GraphQueries",
    "GraphExporter",
    "ProjectContext",
    "ConflictDetector",
    "RepairPlanner",
    "UVSandbox",
    "ValidationRunner",
    "EntityType",
    "RelationshipType",
    "GraphEntity",
    "GraphRelationship",
    "Repository",
    "Package",
    "Module",
    "Route",
    "ConflictType",
    "RepairPlan",
]
