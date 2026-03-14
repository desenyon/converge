from pydantic import BaseModel

from converge.solver.conflict import Conflict, ConflictType


class RepairActionType(str):
    ADD_DEPENDENCY = "add_dependency"
    PIN_VERSION = "pin_version"
    UPGRADE_DEPENDENCY = "upgrade_dependency"
    DOWNGRADE_DEPENDENCY = "downgrade_dependency"


class RepairAction(BaseModel):
    action_type: str
    target_package: str
    target_version: str = "latest"
    description: str


class RepairPlan(BaseModel):
    id: str
    rationale: str
    actions: list[RepairAction]


class RepairPlanner:
    """
    Generates Candidate Repair Plans based on detected conflicts.
    """

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts

    def generate_plans(self) -> list[RepairPlan]:
        plans = []

        # We handle generating plans for unhandled imports
        actions = []
        for c in self.conflicts:
            if c.type == ConflictType.UNRESOLVED_IMPORT:
                # Extract the package name from 'pkg:name'
                target = c.involved_entities[1]
                pkg_name = target.replace("pkg:", "")
                # Simple rule: add dependency to pyproject.toml
                action = RepairAction(
                    action_type=RepairActionType.ADD_DEPENDENCY,
                    target_package=pkg_name,
                    description=f"Add {pkg_name} to pyproject.toml dependencies to satisfy import.",
                )
                actions.append(action)

            elif c.type == ConflictType.VERSION_CLASH:
                # In a real engine, we calculate the intersection of semver ranges.
                target = c.involved_entities[1]
                pkg_name = target.replace("pkg:", "")
                action = RepairAction(
                    action_type=RepairActionType.PIN_VERSION,
                    target_package=pkg_name,
                    description=f"Pin {pkg_name} to a safe version.",
                )
                actions.append(action)

        if actions:
            plan = RepairPlan(
                id="plan:001",
                rationale="Candidate plan to fix missing and conflicting dependencies.",
                actions=actions,
            )
            plans.append(plan)

        return plans
