import shutil
import subprocess
from pathlib import Path

from converge.solver.planner import RepairActionType, RepairPlan


class SandboxError(Exception):
    pass


class UVSandbox:
    """
    Manages isolated Python environments using `uv`.
    """

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.venv_path = self.base_dir / ".venv-converge-test"

    def create(self, python_version: str | None = None) -> None:
        """Creates a fresh virtual environment."""
        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)

        cmd = ["uv", "venv", str(self.venv_path)]
        if python_version:
            cmd.extend(["--python", python_version])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SandboxError(f"Failed to create venv: {result.stderr}")

    def apply_plan(self, plan: RepairPlan) -> None:
        """Installs exactly what the repair plan dictates."""
        # For a real implementation, we would modify pyproject.toml in a temp dir.
        # Here we just `uv pip install` into the sandbox.
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

        if to_install:
            self._uv_pip_install(to_install)

    def _uv_pip_install(self, packages: list[str]) -> None:
        python_exec = str(self.venv_path / "bin" / "python")
        cmd = ["uv", "pip", "install", "--python", python_exec] + packages
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SandboxError(f"uv install failed: {result.stderr}")

    def run_python_cmd(self, code: str) -> bool:
        """Runs a snippet of Python code in the sandbox and returns True if successful."""
        python_exec = str(self.venv_path / "bin" / "python")
        cmd = [python_exec, "-c", code]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def cleanup(self) -> None:
        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)
