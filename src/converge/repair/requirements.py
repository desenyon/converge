"""Apply repair plans to requirements-style manifest files."""

from __future__ import annotations

from pathlib import Path

from converge.solver.planner import RepairActionType, RepairPlan


def _primary_requirements_file(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = root / explicit
        return p if p.is_file() else None
    for name in ("requirements.txt", "requirements/base.txt"):
        p = root / name
        if p.is_file():
            return p
    reqs = sorted(root.glob("requirements*.txt"))
    return reqs[0] if reqs else None


def apply_plan_to_requirements(
    root: Path, plan: RepairPlan, explicit_file: str | None = None
) -> Path | None:
    """Append missing packages from the plan to a requirements file. Returns path if updated."""
    target = _primary_requirements_file(root, explicit_file)
    if target is None:
        return None

    existing_lines = target.read_text(encoding="utf-8").splitlines()
    existing_lower = {line.strip().lower() for line in existing_lines if line.strip()}
    to_add: list[str] = []

    for action in plan.actions:
        if action.action_type not in {
            RepairActionType.ADD_DEPENDENCY,
            RepairActionType.PIN_VERSION,
            RepairActionType.UPGRADE_DEPENDENCY,
            RepairActionType.DOWNGRADE_DEPENDENCY,
        }:
            continue
        pkg = action.target_package.strip()
        if not pkg:
            continue
        line = (
            f"{pkg}=={action.target_version}"
            if action.target_version and action.target_version != "latest"
            else pkg
        )
        key = line.split(";", maxsplit=1)[0].strip().lower()
        if key not in existing_lower:
            to_add.append(line)
            existing_lower.add(key)

    if not to_add:
        return None

    body = target.read_text(encoding="utf-8").rstrip()
    extra = "\n".join(to_add)
    if body:
        target.write_text(body + "\n" + extra + "\n", encoding="utf-8")
    else:
        target.write_text(extra + "\n", encoding="utf-8")
    return target
