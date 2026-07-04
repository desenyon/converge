from converge.solver.conflict import Conflict, ConflictType
from converge.solver.planner import RepairActionType, RepairPlanner, rank_plans


def test_unresolved_test_import_plans_dev_group() -> None:
    conflict = Conflict(
        id="conflict:unresolved_mod:tests/test_a.py_pkg:pytest",
        type=ConflictType.UNRESOLVED_IMPORT,
        description="missing pytest in tests",
        involved_entities=["mod:tests/test_a.py", "pkg:pytest"],
        metadata={"scan_kind": "test"},
    )
    plans = RepairPlanner([conflict]).generate_plans()
    add_plan = next(p for p in plans if p.id == "plan:add")
    assert add_plan.actions[0].dependency_group == "dev"
    assert add_plan.actions[0].action_type == RepairActionType.ADD_DEPENDENCY


def test_rank_plans_prefers_add_over_remove() -> None:
    from converge.solver.planner import RepairAction, RepairPlan

    add = RepairPlan(id="plan:add", rationale="", actions=[RepairAction(action_type="add_dependency", target_package="a", description="")])
    remove = RepairPlan(id="plan:remove", rationale="", actions=[RepairAction(action_type="remove_dependency", target_package="b", description="")])
    ranked = rank_plans([remove, add])
    assert ranked[0].id == "plan:add"
