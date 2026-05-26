from __future__ import annotations

import tomllib
from pathlib import Path

from converge.solver.planner import RepairActionType, RepairPlan


def _extract_dependencies(pyproject_path: Path) -> list[str]:
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    return list(data.get("project", {}).get("dependencies", []))


def _replace_dependencies_assignment(content: str, replacement: str) -> str:
    replaced: list[str] = []
    skip_until_closed = False
    bracket_depth = 0

    for line in content.splitlines():
        if skip_until_closed:
            bracket_depth += line.count("[") - line.count("]")
            if bracket_depth <= 0:
                skip_until_closed = False
            continue

        if line.strip().startswith("dependencies = ["):
            replaced.append(replacement)
            bracket_depth = line.count("[") - line.count("]")
            skip_until_closed = bracket_depth > 0
        else:
            replaced.append(line)

    return "\n".join(replaced) + "\n"


def apply_plan_to_pyproject(pyproject_path: Path, plan: RepairPlan) -> None:
    content = pyproject_path.read_text()
    dependencies = _extract_dependencies(pyproject_path)

    for action in plan.actions:
        if action.action_type not in {
            RepairActionType.ADD_DEPENDENCY,
            RepairActionType.PIN_VERSION,
            RepairActionType.UPGRADE_DEPENDENCY,
            RepairActionType.DOWNGRADE_DEPENDENCY,
        }:
            continue

        dependency = action.target_package
        if action.target_version and action.target_version != "latest":
            dependency = f"{dependency}=={action.target_version}"

        if dependency not in dependencies:
            dependencies.append(dependency)

    rendered_dependencies = ", ".join(f'"{dependency}"' for dependency in dependencies)
    replacement = f"dependencies = [{rendered_dependencies}]"

    if "dependencies = [" in content:
        pyproject_path.write_text(_replace_dependencies_assignment(content, replacement))
        return

    project_header = "[project]"
    if project_header in content:
        pyproject_path.write_text(
            content.replace(project_header, f"{project_header}\n{replacement}", 1)
        )
        return

    pyproject_path.write_text(f"{content.rstrip()}\n[project]\n{replacement}\n")
