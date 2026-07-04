from __future__ import annotations

import re
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


def _append_to_toml_array(content: str, section_header: str, array_name: str, value: str) -> str:
    pattern = rf"({re.escape(section_header)}\s*\n(?:[^\[]*\n)*){re.escape(array_name)}\s*=\s*\[([^\]]*)\]"
    match = re.search(pattern, content, flags=re.MULTILINE)
    if match:
        existing = match.group(2).strip()
        items = [existing] if existing else []
        rendered = ", ".join(items + [f'"{value}"'])
        replacement = f"{match.group(1)}{array_name} = [{rendered}]"
        return content[: match.start()] + replacement + content[match.end() :]
    return content.replace(
        section_header,
        f'{section_header}\n{array_name} = ["{value}"]',
        1,
    )


def apply_plan_to_pyproject(pyproject_path: Path, plan: RepairPlan) -> None:
    content = pyproject_path.read_text(encoding="utf-8")
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

        group = action.dependency_group or "main"
        if group == "main":
            if dependency not in dependencies:
                dependencies.append(dependency)
            continue

        if group == "dev":
            content = _append_to_toml_array(
                content, "[tool.uv]", "dependency-groups.dev", dependency
            )
            content = _append_to_toml_array(
                content, "[project.optional-dependencies]", "dev", dependency
            )
            continue

        content = _append_to_toml_array(
            content,
            "[project.optional-dependencies]",
            group,
            dependency,
        )

    if any(
        a.action_type
        in {
            RepairActionType.ADD_DEPENDENCY,
            RepairActionType.PIN_VERSION,
            RepairActionType.UPGRADE_DEPENDENCY,
            RepairActionType.DOWNGRADE_DEPENDENCY,
        }
        and (a.dependency_group or "main") == "main"
        for a in plan.actions
    ):
        rendered_dependencies = ", ".join(f'"{dependency}"' for dependency in dependencies)
        replacement = f"dependencies = [{rendered_dependencies}]"

        if "dependencies = [" in content:
            content = _replace_dependencies_assignment(content, replacement)
        elif "[project]" in content:
            content = content.replace("[project]", f"[project]\n{replacement}", 1)
        else:
            content = f"{content.rstrip()}\n[project]\n{replacement}\n"

    pyproject_path.write_text(content, encoding="utf-8")
