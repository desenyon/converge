"""JSON serialization helpers for CLI --json mode."""

from __future__ import annotations

import json
from typing import Any

from converge.version_info import JSON_SCHEMA_VERSION, package_version


def envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Stable metadata for machine consumers (CI, scripts)."""
    return {
        **payload,
        "schema_version": JSON_SCHEMA_VERSION,
        "tool_version": package_version(),
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def print_json(payload: dict[str, Any]) -> None:
    print(dumps(envelope(payload)), end="")
