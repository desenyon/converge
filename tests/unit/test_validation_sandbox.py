from pathlib import Path

from converge.solver.planner import RepairAction, RepairActionType, RepairPlan
from converge.validation.sandbox import UVSandbox


def test_sandbox_applies_manifest_repairs_to_isolated_copy(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    pyproject = repo / "pyproject.toml"
    pyproject.write_text('[project]\nname = "repo"\ndependencies = []\n', encoding="utf-8")
    plan = RepairPlan(
        id="plan:001",
        rationale="add missing dependency",
        actions=[
            RepairAction(
                action_type=RepairActionType.ADD_DEPENDENCY,
                target_package="requests",
                description="Add requests",
            )
        ],
    )

    installed: list[list[str]] = []

    def fake_install(self: UVSandbox, packages: list[str]) -> None:
        installed.append(packages)

    monkeypatch.setattr(UVSandbox, "_uv_pip_install", fake_install)

    sandbox = UVSandbox(str(repo))
    sandbox.create()
    try:
        sandbox.apply_plan(plan)
        assert sandbox.work_dir is not None
        assert sandbox.work_dir != repo
        assert '"requests"' in (sandbox.work_dir / "pyproject.toml").read_text(encoding="utf-8")
        assert '"requests"' not in pyproject.read_text(encoding="utf-8")
        assert installed == [["requests"]]
    finally:
        sandbox.cleanup()
