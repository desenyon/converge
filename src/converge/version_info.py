"""Package and JSON schema versioning for CLI output."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

JSON_SCHEMA_VERSION = 1


def _source_tree_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject_path.is_file():
        return None
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    return str(version) if version is not None else None


def package_version() -> str:
    source_version = _source_tree_version()
    if source_version is not None:
        return source_version
    try:
        return importlib.metadata.version("converge-cli")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
