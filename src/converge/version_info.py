"""Package and JSON schema versioning for CLI output."""

from __future__ import annotations

import importlib.metadata

JSON_SCHEMA_VERSION = 1


def package_version() -> str:
    try:
        return importlib.metadata.version("converge-cli")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
