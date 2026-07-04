"""Remove dependencies from manifest files."""

from __future__ import annotations

import re
from pathlib import Path

from converge.solver.planner import RepairActionType, RepairPlan
from converge.versioning.constraints import normalize_package_name


def _remove_from_requirements_file(path: Path, package_name: str) -> bool:
    target = normalize_package_name(package_name)
    lines = path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        pkg, _ = _line_package_name(stripped)
        if pkg and normalize_package_name(pkg) == target:
            removed = True
            continue
        kept.append(line)
    if removed:
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed


def _line_package_name(line: str) -> tuple[str | None, str]:
    from converge.versioning.constraints import parse_requirement

    try:
        name, _ = parse_requirement(line)
        return name, line
    except Exception:
        return None, line


def apply_removals_to_requirements(root: Path, plan: RepairPlan) -> list[Path]:
    updated: list[Path] = []
    removals = [
        a.target_package
        for a in plan.actions
        if a.action_type == RepairActionType.REMOVE_DEPENDENCY and a.target_package
    ]
    if not removals:
        return updated
    for req_file in sorted(root.glob("requirements*.txt")):
        for pkg in removals:
            if _remove_from_requirements_file(req_file, pkg):
                if req_file not in updated:
                    updated.append(req_file)
    return updated


def apply_removals_to_pyproject(pyproject_path: Path, plan: RepairPlan) -> bool:
    import tomllib

    removals = {
        normalize_package_name(a.target_package)
        for a in plan.actions
        if a.action_type == RepairActionType.REMOVE_DEPENDENCY and a.target_package
    }
    if not removals or not pyproject_path.is_file():
        return False

    content = pyproject_path.read_text(encoding="utf-8")
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)

    project = data.get("project", {})
    deps = list(project.get("dependencies", []))
    new_deps = [
        d
        for d in deps
        if normalize_package_name(str(d).split(";")[0].split("==")[0].split("[")[0].strip())
        not in removals
    ]
    if len(new_deps) == len(deps):
        return False

    rendered = ", ".join(f'"{d}"' for d in new_deps)
    replacement = f"dependencies = [{rendered}]"
    if "dependencies = [" in content:
        new_content = re.sub(
            r"dependencies\s*=\s*\[[^\]]*\]",
            replacement,
            content,
            count=1,
            flags=re.DOTALL,
        )
        pyproject_path.write_text(new_content, encoding="utf-8")
        return True
    return False
