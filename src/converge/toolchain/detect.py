"""Detect the preferred Python toolchain for a repository."""

from __future__ import annotations

import tomllib
from pathlib import Path


def _has_uv_tool_config(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    with pyproject.open("rb") as handle:
        try:
            data = tomllib.load(handle)
        except tomllib.TOMLDecodeError:
            return False
    tool = data.get("tool", {})
    return isinstance(tool.get("uv"), dict)


def detect_toolchain(root: Path) -> str:
    """Return uv | poetry | pip-tools | pip."""
    if (root / "uv.lock").is_file() or _has_uv_tool_config(root):
        return "uv"
    if (root / "poetry.lock").is_file():
        return "poetry"
    if any(root.glob("requirements*.in")):
        return "pip-tools"
    return "pip"
