"""Unified package-manager backends for uv and pip."""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class ToolchainError(Exception):
    pass


class ToolchainBackend(ABC):
    @abstractmethod
    def create_venv(self, venv_path: Path, python_version: str | None = None) -> None: ...

    @abstractmethod
    def install_packages(self, venv_path: Path, packages: list[str]) -> None: ...

    def sync_from_lock(self, project_root: Path, venv_path: Path) -> bool:
        """Return True if sync was performed."""
        return False


class UvBackend(ToolchainBackend):
    def create_venv(self, venv_path: Path, python_version: str | None = None) -> None:
        cmd = ["uv", "venv", str(venv_path)]
        if python_version:
            cmd.extend(["--python", python_version])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolchainError(f"uv venv failed: {result.stderr}")

    def install_packages(self, venv_path: Path, packages: list[str]) -> None:
        if not packages:
            return
        python_exec = _python_in_venv(venv_path)
        cmd = ["uv", "pip", "install", "--python", python_exec] + packages
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolchainError(f"uv pip install failed: {result.stderr}")

    def sync_from_lock(self, project_root: Path, venv_path: Path) -> bool:
        lock = project_root / "uv.lock"
        if not lock.is_file():
            return False
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(venv_path.resolve())
        cmd = ["uv", "sync", "--frozen", "--directory", str(project_root)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, env=env)
        if result.returncode != 0:
            raise ToolchainError(f"uv sync failed: {result.stderr}")
        return True

    def lock(self, project_root: Path) -> None:
        result = subprocess.run(
            ["uv", "lock", "--directory", str(project_root)],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            raise ToolchainError(f"uv lock failed: {result.stderr}")

    def add_dependency(self, project_root: Path, package: str, *, dev: bool = False) -> None:
        cmd = ["uv", "add", package, "--directory", str(project_root)]
        if dev:
            cmd.append("--dev")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if result.returncode != 0:
            raise ToolchainError(f"uv add failed: {result.stderr}")

    def remove_dependency(self, project_root: Path, package: str, *, dev: bool = False) -> None:
        cmd = ["uv", "remove", package, "--directory", str(project_root)]
        if dev:
            cmd.append("--dev")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if result.returncode != 0:
            raise ToolchainError(f"uv remove failed: {result.stderr}")


class PipBackend(ToolchainBackend):
    def create_venv(self, venv_path: Path, python_version: str | None = None) -> None:
        py_exec = f"python{python_version}" if python_version else "python3"
        cmd = [py_exec, "-m", "venv", str(venv_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolchainError(f"venv failed: {result.stderr}")

    def install_packages(self, venv_path: Path, packages: list[str]) -> None:
        if not packages:
            return
        pip_exec = _pip_in_venv(venv_path)
        cmd = [pip_exec, "install"] + packages
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolchainError(f"pip install failed: {result.stderr}")

    def compile_lock(self, project_root: Path, input_file: str = "requirements.in") -> None:
        in_path = project_root / input_file
        if not in_path.is_file():
            raise ToolchainError(f"Missing {input_file}")
        out_name = input_file.replace(".in", ".txt")
        out_path = project_root / out_name
        cmd = ["pip-compile", str(in_path), "-o", str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if result.returncode != 0:
            raise ToolchainError(f"pip-compile failed: {result.stderr}")


def _python_in_venv(venv_path: Path) -> str:
    unix = venv_path / "bin" / "python"
    if unix.exists():
        return str(unix)
    return str(venv_path / "Scripts" / "python.exe")


def _pip_in_venv(venv_path: Path) -> str:
    unix = venv_path / "bin" / "pip"
    if unix.exists():
        return str(unix)
    return str(venv_path / "Scripts" / "pip.exe")


def get_backend(provider: str) -> ToolchainBackend:
    if provider == "uv":
        return UvBackend()
    if provider == "pip":
        return PipBackend()
    raise ToolchainError(f"Unknown provider: {provider}")
