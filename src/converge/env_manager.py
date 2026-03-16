from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import networkx as nx
from rich.console import Console

from converge.models import EntityType
from converge.project_context import ProjectContext

console = Console()


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
        self.venv_path = context.default_env_path if env_dir_name is None else self.base_dir / env_dir_name

    def plan_packages(self, graph: nx.DiGraph[Any]) -> list[str]:
        packages = {
            str(data["name"])
            for _node_id, data in graph.nodes(data=True)
            if data.get("type") == EntityType.PACKAGE and data.get("name")
        }
        return sorted(packages)

    def is_uv_installed(self) -> bool:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def create_venv(self, provider: str = "uv", python_version: str | None = None) -> None:
        """
        Creates a fresh virtual environment. Wipes the existing one if present.
        """
        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)

        if provider == "uv":
            cmd = ["uv", "venv", str(self.venv_path)]
            if python_version:
                cmd.extend(["--python", python_version])
        else:
            # Fallback to standard venv
            # If a specific version is requested with pip, we assume the host has it accessible via e.g. `python3.11`
            py_exec = f"python{python_version}" if python_version else "python3"
            cmd = [py_exec, "-m", "venv", str(self.venv_path)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise EnvironmentError(f"Failed to provision {provider} environment: {result.stderr}")

    def install_packages(self, provider: str, packages: list[str]) -> None:
        """
        Installs the list of packages into the active sandbox or environment.
        """
        if not packages:
            return

        python_exec = str(self.venv_path / "bin" / "python")
        if not Path(python_exec).exists():
            python_exec = str(
                self.venv_path / "Scripts" / "python.exe"
            )  # Windows fallback for robustness

        if provider == "uv":
            cmd = ["uv", "pip", "install", "--python", python_exec] + packages
        else:
            pip_exec = str(self.venv_path / "bin" / "pip")
            if not Path(pip_exec).exists():
                pip_exec = str(self.venv_path / "Scripts" / "pip.exe")
            cmd = [pip_exec, "install"] + packages

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise EnvironmentError(f"Failed resolving dependencies via {provider}: {result.stderr}")

    def get_executable(self) -> str:
        python_exec = str(self.venv_path / "bin" / "python")
        if not Path(python_exec).exists():
            python_exec = str(self.venv_path / "Scripts" / "python.exe")
        return python_exec
