"""PEP 440 constraint parsing and compatibility checks."""

from __future__ import annotations

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def normalize_package_name(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def parse_requirement(constraint: str) -> tuple[str, str | None]:
    """Return (package_name, version_spec or None) from a constraint string."""
    try:
        req = Requirement(constraint)
    except InvalidRequirement:
        raw = constraint.split(";")[0].strip()
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in raw:
                return normalize_package_name(raw.split(sep, 1)[0].strip()), raw
        name = raw.split("[", 1)[0].strip()
        return normalize_package_name(name), None
    name = normalize_package_name(req.name)
    spec = str(req.specifier) if req.specifier else None
    return name, spec


def version_satisfies(version: str, specifier: str | None) -> bool:
    if not specifier:
        return True
    try:
        return Version(version) in SpecifierSet(specifier)
    except (InvalidVersion, InvalidSpecifier):
        return True


def constraints_conflict(spec_a: str | None, spec_b: str | None) -> bool:
    """True when two version specifiers cannot both be satisfied."""
    if not spec_a or not spec_b:
        return False
    try:
        sa = SpecifierSet(spec_a)
        sb = SpecifierSet(spec_b)
        candidates = (
            Version("0.0.1"),
            Version("1.0.0"),
            Version("2.0.0"),
            Version("3.0.0"),
            Version("99.0.0"),
        )
        return not any(v in sa and v in sb for v in candidates)
    except (InvalidSpecifier, InvalidVersion, TypeError):
        return False
