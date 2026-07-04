import shutil
import subprocess
import tempfile
from pathlib import Path

from converge.repair.manifest import apply_plan_to_pyproject
from converge.repair.requirements import apply_plan_to_requirements
from converge.solver.planner import RepairActionType, RepairPlan
from converge.toolchain import ToolchainError, get_backend


class SandboxError(Exception):
    pass


class UVSandbox:
    """
    Manages isolated Python environments using the unified toolchain backend.
    """

    def __init__(self, base_dir: str, provider: str = "uv"):
        self.source_dir = Path(base_dir)
        self.provider = provider
        self.work_dir: Path | None = None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.venv_path = self.source_dir / ".venv-converge-test"

    def create(self, python_version: str | None = None) -> None:
        """Creates a fresh virtual environment."""
        self.cleanup()
        self._temp_dir = tempfile.TemporaryDirectory(prefix="converge-validation-")
        self.work_dir = Path(self._temp_dir.name) / self.source_dir.name
        shutil.copytree(
            self.source_dir,
            self.work_dir,
            ignore=shutil.ignore_patterns(
                ".git",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                ".venv",
                ".venv-converge-test",
                "__pycache__",
            ),
        )
        self.venv_path = self.work_dir / ".venv-converge-test"

        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)

        backend = get_backend(self.provider)
        try:
            backend.create_venv(self.venv_path, python_version)
        except ToolchainError as e:
            raise SandboxError(str(e)) from e

    def apply_plan(self, plan: RepairPlan) -> None:
        """Installs exactly what the repair plan dictates."""
        if self.work_dir is None:
            raise SandboxError("Sandbox must be created before applying a plan.")

        pyproject_path = self.work_dir / "pyproject.toml"
        if pyproject_path.exists():
            apply_plan_to_pyproject(pyproject_path, plan)
        apply_plan_to_requirements(self.work_dir, plan)

        to_install = []
        for action in plan.actions:
            if action.action_type in (
                RepairActionType.ADD_DEPENDENCY,
                RepairActionType.PIN_VERSION,
                RepairActionType.UPGRADE_DEPENDENCY,
                RepairActionType.DOWNGRADE_DEPENDENCY,
            ):
                if action.target_version and action.target_version != "latest":
                    to_install.append(f"{action.target_package}=={action.target_version}")
                else:
                    to_install.append(action.target_package)

        backend = get_backend(self.provider)
        try:
            if self.provider == "uv" and backend.sync_from_lock(self.work_dir, self.venv_path):
                return
            if to_install:
                backend.install_packages(self.venv_path, to_install)
        except ToolchainError as e:
            raise SandboxError(str(e)) from e

    def run_python_cmd(self, code: str) -> bool:
        """Runs a snippet of Python code in the sandbox and returns True if successful."""
        python_exec = str(self.venv_path / "bin" / "python")
        if not Path(python_exec).exists():
            python_exec = str(self.venv_path / "Scripts" / "python.exe")
        cmd = [python_exec, "-c", code]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def cleanup(self) -> None:
        if self.venv_path.exists() and self.venv_path.is_relative_to(self.source_dir):
            shutil.rmtree(self.venv_path)
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
        self._temp_dir = None
        self.work_dir = None
        self.venv_path = self.source_dir / ".venv-converge-test"
