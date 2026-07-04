from pydantic import BaseModel

from converge.solver.conflict import Conflict, ConflictType


class RepairActionType(str):
    ADD_DEPENDENCY = "add_dependency"
    PIN_VERSION = "pin_version"
    UPGRADE_DEPENDENCY = "upgrade_dependency"
    DOWNGRADE_DEPENDENCY = "downgrade_dependency"
    REMOVE_DEPENDENCY = "remove_dependency"
    REGENERATE_LOCKFILE = "regenerate_lockfile"


class RepairAction(BaseModel):
    action_type: str
    target_package: str
    target_version: str = "latest"
    description: str
    dependency_group: str = "main"


class RepairPlan(BaseModel):
    id: str
    rationale: str
    actions: list[RepairAction]


def rank_plans(plans: list[RepairPlan]) -> list[RepairPlan]:
    """Prefer fewer actions and additive plans over destructive ones."""

    def sort_key(plan: RepairPlan) -> tuple[int, int, str]:
        destructive = 1 if plan.id == "plan:remove" else 0
        return (destructive, len(plan.actions), plan.id)

    return sorted(plans, key=sort_key)


class RepairPlanner:
    """
    Generates Candidate Repair Plans based on detected conflicts.
    """

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts

    def generate_plans(self) -> list[RepairPlan]:
        plans: list[RepairPlan] = []
        add_actions: list[RepairAction] = []
        pin_actions: list[RepairAction] = []
        remove_actions: list[RepairAction] = []

        for c in self.conflicts:
            if c.type == ConflictType.UNRESOLVED_IMPORT:
                target = c.involved_entities[1]
                pkg_name = target.replace("pkg:", "")
                scan_kind = str(c.metadata.get("scan_kind", "source"))
                group = "dev" if scan_kind == "test" else "main"
                add_actions.append(
                    RepairAction(
                        action_type=RepairActionType.ADD_DEPENDENCY,
                        target_package=pkg_name,
                        dependency_group=group,
                        description=f"Add {pkg_name} to {group} dependencies to satisfy import.",
                    )
                )

            elif c.type in (ConflictType.VERSION_CLASH, ConflictType.COMPILE_DRIFT):
                target = c.involved_entities[0]
                pkg_name = target.replace("pkg:", "")
                locked = c.metadata.get("locked_version") or c.metadata.get("compiled_constraint")
                pin_actions.append(
                    RepairAction(
                        action_type=RepairActionType.PIN_VERSION,
                        target_package=pkg_name,
                        target_version=str(locked).split("==")[-1] if locked else "latest",
                        description=f"Pin {pkg_name} to a compatible version.",
                    )
                )

            elif c.type == ConflictType.LOCKFILE_DRIFT:
                pkg_id = c.involved_entities[0]
                pkg_name = pkg_id.replace("pkg:", "")
                locked = c.metadata.get("locked_version")
                pin_actions.append(
                    RepairAction(
                        action_type=RepairActionType.PIN_VERSION,
                        target_package=pkg_name,
                        target_version=str(locked) if locked else "latest",
                        description=(
                            f"Align manifest pin for {pkg_name} with lockfile ({locked})."
                        ),
                    )
                )

            elif c.type == ConflictType.UNUSED_DEPENDENCY:
                pkg_id = c.involved_entities[0]
                pkg_name = pkg_id.replace("pkg:", "")
                remove_actions.append(
                    RepairAction(
                        action_type=RepairActionType.REMOVE_DEPENDENCY,
                        target_package=pkg_name,
                        description=f"Remove unused package {pkg_name} from manifests.",
                    )
                )

        if add_actions:
            plans.append(
                RepairPlan(
                    id="plan:add",
                    rationale="Add missing dependencies for unresolved imports.",
                    actions=add_actions,
                )
            )

        if pin_actions:
            lock_action = RepairAction(
                action_type=RepairActionType.REGENERATE_LOCKFILE,
                target_package="",
                description="Regenerate lockfile after manifest changes.",
            )
            plans.append(
                RepairPlan(
                    id="plan:pin",
                    rationale="Resolve version, compile, and lockfile drift.",
                    actions=pin_actions + [lock_action],
                )
            )

        if remove_actions:
            lock_action = RepairAction(
                action_type=RepairActionType.REGENERATE_LOCKFILE,
                target_package="",
                description="Regenerate lockfile after manifest changes.",
            )
            plans.append(
                RepairPlan(
                    id="plan:remove",
                    rationale="Remove declared packages that are never imported.",
                    actions=remove_actions + [lock_action],
                )
            )

        return rank_plans(plans)
