from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

import networkx as nx
from rich.console import Console

from converge.models import EntityType, RelationshipType
from converge.project_context import ProjectContext
from converge.toolchain import ToolchainError, detect_toolchain, get_backend

console = Console()
log = logging.getLogger("converge.env")


class EnvironmentError(Exception):
    pass


class EnvironmentManager:
    """
    Handles robust provisioning of virtual environments dynamically, utilizing highly performant
    subprocesses with interactive rich telemetry.
    """

    def __init__(self, context: ProjectContext, env_dir_name: str | None = None):
        self.context = context
        self.base_dir = context.root_dir
        self.venv_path = (
            context.default_env_path if env_dir_name is None else self.base_dir / env_dir_name
        )

    def plan_packages(self, graph: nx.DiGraph[Any]) -> list[str]:
        """Build install specs from declared REQUIRES edges (constraint-aware)."""
        specs: dict[str, str] = {}
        for _u, v, data in graph.edges(data=True):
            if data.get("type") not in (
                RelationshipType.REQUIRES,
                RelationshipType.REQUIRES.value,
            ):
                continue
            if graph.nodes.get(v, {}).get("type") not in (
                EntityType.PACKAGE,
                EntityType.PACKAGE.value,
            ):
                continue
            md = data.get("metadata")
            constraint = None
            group = "main"
            if isinstance(md, dict):
                constraint = md.get("constraint")
                group = str(md.get("dependency_group", "main"))
            if group not in ("main", "requirements"):
                continue
            pkg_name = str(graph.nodes[v].get("name", v.replace("pkg:", "")))
            if constraint and isinstance(constraint, str):
                specs[pkg_name] = constraint
            else:
                specs.setdefault(pkg_name, pkg_name)
        return sorted(specs.values())

    def is_uv_installed(self) -> bool:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def resolve_provider(self, provider: str) -> str:
        if provider == "auto":
            detected = detect_toolchain(self.base_dir)
            return "uv" if detected in ("uv", "poetry") else "pip"
        return provider

    def create_venv(self, provider: str = "uv", python_version: str | None = None) -> None:
        """Creates a fresh virtual environment. Wipes the existing one if present."""
        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)

        resolved = self.resolve_provider(provider)
        backend = get_backend(resolved)
        try:
            backend.create_venv(self.venv_path, python_version)
        except ToolchainError as e:
            raise EnvironmentError(str(e)) from e

    def install_packages(self, provider: str, packages: list[str]) -> None:
        """Install packages or sync from lockfile when available."""
        resolved = self.resolve_provider(provider)
        backend = get_backend(resolved)
        try:
            if resolved == "uv" and backend.sync_from_lock(self.base_dir, self.venv_path):
                log.debug("install_packages: uv sync from lock")
                return
            backend.install_packages(self.venv_path, packages)
        except ToolchainError as e:
            raise EnvironmentError(f"Failed resolving dependencies via {resolved}: {e}") from e

    def get_executable(self) -> str:
        python_exec = str(self.venv_path / "bin" / "python")
        if not Path(python_exec).exists():
            python_exec = str(self.venv_path / "Scripts" / "python.exe")
        return python_exec
