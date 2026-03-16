from pathlib import Path

from converge.repair.manifest import apply_plan_to_pyproject
from converge.solver.planner import RepairAction, RepairActionType, RepairPlan


def test_fix_apply_updates_pyproject_dependencies(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "repo"\ndependencies = []\n')
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

    apply_plan_to_pyproject(pyproject, plan)

    content = pyproject.read_text()
    assert '"requests"' in content
