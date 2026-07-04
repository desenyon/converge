"""Scan non-Python dependency manifests (npm, system packages, cargo, conda)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from converge.models import EntityType, GraphEntity, GraphRelationship, RelationshipType


def _repo_id(root: Path) -> str:
    return f"repo:{root.name}"


def scan_package_json(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    pkg_json = root / "package.json"
    if not pkg_json.is_file():
        return entities, relationships

    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return entities, relationships

    repo_id = _repo_id(root)
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        group = "main" if section == "dependencies" else section
        for name, version in deps.items():
            if not isinstance(name, str):
                continue
            node_id = f"npm:{name}"
            entities.append(
                GraphEntity(
                    id=node_id,
                    type=EntityType.NPM_PACKAGE,
                    name=name,
                    metadata={
                        "version": str(version),
                        "source": "package.json",
                        "dependency_group": group,
                    },
                )
            )
            relationships.append(
                GraphRelationship(
                    source_id=repo_id,
                    target_id=node_id,
                    type=RelationshipType.REQUIRES,
                    metadata={"source": "package.json", "dependency_group": group},
                )
            )
    return entities, relationships


def scan_dockerfile_system_packages(
    root: Path,
) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    dockerfile = root / "Dockerfile"
    if not dockerfile.is_file():
        return entities, relationships

    try:
        content = dockerfile.read_text(encoding="utf-8")
    except OSError:
        return entities, relationships

    repo_id = _repo_id(root)
    for line in content.splitlines():
        if "apt-get install" not in line.lower():
            continue
        tokens = line.split()
        install_idx = next(
            (i for i, t in enumerate(tokens) if t.lower() == "install"),
            None,
        )
        if install_idx is None:
            continue
        for token in tokens[install_idx + 1 :]:
            if token.startswith("-"):
                continue
            pkg = token.strip("\\").strip()
            if not pkg or pkg in {"&&", ";"}:
                continue
            node_id = f"sys:{pkg}"
            entities.append(
                GraphEntity(
                    id=node_id,
                    type=EntityType.SYSTEM_PACKAGE,
                    name=pkg,
                    metadata={"source": "Dockerfile"},
                )
            )
            relationships.append(
                GraphRelationship(
                    source_id=repo_id,
                    target_id=node_id,
                    type=RelationshipType.REQUIRES,
                    metadata={"source": "Dockerfile"},
                )
            )
    return entities, relationships


def scan_apt_txt(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    apt_txt = root / "apt.txt"
    if not apt_txt.is_file():
        return entities, relationships

    repo_id = _repo_id(root)
    for line in apt_txt.read_text(encoding="utf-8").splitlines():
        pkg = line.strip()
        if not pkg or pkg.startswith("#"):
            continue
        node_id = f"sys:{pkg}"
        entities.append(
            GraphEntity(
                id=node_id,
                type=EntityType.SYSTEM_PACKAGE,
                name=pkg,
                metadata={"source": "apt.txt"},
            )
        )
        relationships.append(
            GraphRelationship(
                source_id=repo_id,
                target_id=node_id,
                type=RelationshipType.REQUIRES,
                metadata={"source": "apt.txt"},
            )
        )
    return entities, relationships


def scan_cargo_toml(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    cargo = root / "Cargo.toml"
    if not cargo.is_file():
        return entities, relationships

    try:
        content = cargo.read_text(encoding="utf-8")
    except OSError:
        return entities, relationships

    repo_id = _repo_id(root)
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_deps = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_deps = stripped == "[dependencies]"
            continue
        if not in_deps or not stripped or stripped.startswith("#"):
            continue
        match = re.match(r'^([A-Za-z0-9_-]+)\s*=', stripped)
        if not match:
            continue
        name = match.group(1)
        node_id = f"cargo:{name}"
        entities.append(
            GraphEntity(
                id=node_id,
                type=EntityType.CARGO_CRATE,
                name=name,
                metadata={"source": "Cargo.toml"},
            )
        )
        relationships.append(
            GraphRelationship(
                source_id=repo_id,
                target_id=node_id,
                type=RelationshipType.DEPENDS_ON,
                metadata={"source": "Cargo.toml"},
            )
        )
    return entities, relationships


def scan_environment_yml(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    env_yml = root / "environment.yml"
    if not env_yml.is_file():
        return entities, relationships

    try:
        content = env_yml.read_text(encoding="utf-8")
    except OSError:
        return entities, relationships

    repo_id = _repo_id(root)
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "dependencies:":
            in_deps = True
            continue
        if in_deps and stripped and not stripped.startswith("-") and stripped.endswith(":"):
            break
        if not in_deps or not stripped.startswith("-"):
            continue
        token = stripped.removeprefix("-").strip()
        if not token or token.startswith("#"):
            continue
        name = token.split("=", 1)[0].strip()
        node_id = f"conda:{name}"
        entities.append(
            GraphEntity(
                id=node_id,
                type=EntityType.CONDA_PACKAGE,
                name=name,
                metadata={"source": "environment.yml", "spec": token},
            )
        )
        relationships.append(
            GraphRelationship(
                source_id=repo_id,
                target_id=node_id,
                type=RelationshipType.REQUIRES,
                metadata={"source": "environment.yml"},
            )
        )
    return entities, relationships


def scan_ecosystems(root: Path) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    for fn in (
        scan_package_json,
        scan_dockerfile_system_packages,
        scan_apt_txt,
        scan_cargo_toml,
        scan_environment_yml,
    ):
        e, r = fn(root)
        entities.extend(e)
        relationships.extend(r)
    return entities, relationships
