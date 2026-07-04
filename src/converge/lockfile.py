"""Lockfile detection, parsing, and graph extraction."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from converge.models import EntityType, GraphEntity, GraphRelationship, RelationshipType
from converge.versioning.constraints import normalize_package_name


def _parse_toml_lock_packages(path: Path) -> list[dict[str, str]]:
    """Parse [[package]] entries from uv.lock or poetry.lock."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    packages_raw = data.get("package")
    if not isinstance(packages_raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in packages_raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        version = item.get("version")
        out.append(
            {
                "name": name,
                "version": str(version) if version is not None else "",
            }
        )
    return out


def _append_lock_packages(
    *,
    entities: list[GraphEntity],
    relationships: list[GraphRelationship],
    lock_id: str,
    rel_path: str,
    packages: list[dict[str, str]],
) -> None:
    for pkg in packages:
        pkg_name = normalize_package_name(pkg["name"])
        pkg_id = f"pkg:{pkg_name}"
        version = pkg.get("version", "")
        entities.append(
            GraphEntity(
                id=pkg_id,
                type=EntityType.PACKAGE,
                name=pkg_name,
                metadata={
                    "locked_version": version,
                    "source": rel_path,
                    "from_lockfile": True,
                },
            )
        )
        relationships.append(
            GraphRelationship(
                source_id=lock_id,
                target_id=pkg_id,
                type=RelationshipType.RESOLVES_TO,
                metadata={"version": version, "source": rel_path},
            )
        )


def summarize_lockfiles(root: Path) -> dict[str, Any]:
    """Return lockfile paths, sizes, and parsed hints where cheap."""
    out: dict[str, Any] = {"root": str(root), "lockfiles": []}
    candidates = [
        ("uv", root / "uv.lock"),
        ("poetry", root / "poetry.lock"),
        ("pip_tools", root / "requirements.txt"),
    ]
    for name, path in candidates:
        if not path.is_file():
            continue
        if name == "pip_tools" and not any(root.glob("requirements*.in")):
            continue
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        entry: dict[str, Any] = {"kind": name, "path": rel, "bytes": path.stat().st_size}
        if name in ("uv", "poetry"):
            try:
                entry["resolved_packages"] = _parse_toml_lock_packages(path)
            except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
                entry["resolved_packages"] = []
        out["lockfiles"].append(entry)
    return out


def lockfile_to_graph(
    root: Path, repo_id: str
) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """Extract lockfile entities and RESOLVES_TO edges from uv.lock and poetry.lock."""
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []

    for kind, filename in (("uv", "uv.lock"), ("poetry", "poetry.lock")):
        lock_path = root / filename
        if not lock_path.is_file():
            continue
        try:
            rel_path = lock_path.relative_to(root).as_posix()
        except ValueError:
            rel_path = lock_path.name

        lock_id = f"lockfile:{rel_path}"
        entities.append(
            GraphEntity(
                id=lock_id,
                type=EntityType.LOCKFILE,
                name=rel_path,
                metadata={"kind": kind, "path": rel_path},
            )
        )
        relationships.append(
            GraphRelationship(
                source_id=repo_id,
                target_id=lock_id,
                type=RelationshipType.LOCKED_BY,
                metadata={"kind": kind},
            )
        )
        _append_lock_packages(
            entities=entities,
            relationships=relationships,
            lock_id=lock_id,
            rel_path=rel_path,
            packages=_parse_toml_lock_packages(lock_path),
        )

    return entities, relationships
