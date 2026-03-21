from pathlib import Path

from converge.repair.requirements import apply_plan_to_requirements
from converge.solver.planner import RepairAction, RepairActionType, RepairPlan


def test_apply_plan_appends_to_requirements_txt(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("flask\n", encoding="utf-8")
    plan = RepairPlan(
        id="p1",
        rationale="test",
        actions=[
            RepairAction(
                action_type=RepairActionType.ADD_DEPENDENCY,
                target_package="requests",
                description="add",
            )
        ],
    )
    out = apply_plan_to_requirements(tmp_path, plan, None)
    assert out == req
    text = req.read_text()
    assert "requests" in text
    assert "flask" in text
