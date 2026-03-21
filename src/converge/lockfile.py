"""Lockfile detection and best-effort parsing (uv, poetry)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def _parse_uv_lock_packages(path: Path) -> list[dict[str, str]]:
    """Parse [[package]] entries from a uv.lock file."""
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


def summarize_lockfiles(root: Path) -> dict[str, Any]:
    """Return lockfile paths, sizes, and parsed hints where cheap."""
    out: dict[str, Any] = {"root": str(root), "lockfiles": []}
    candidates = [
        ("uv", root / "uv.lock"),
        ("poetry", root / "poetry.lock"),
        ("pip_tools", root / "requirements.txt.lock"),
    ]
    for name, path in candidates:
        if path.is_file():
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = str(path)
            entry: dict[str, Any] = {"kind": name, "path": rel, "bytes": path.stat().st_size}
            if name == "uv":
                try:
                    entry["resolved_packages"] = _parse_uv_lock_packages(path)
                except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
                    entry["resolved_packages"] = []
            out["lockfiles"].append(entry)
    return out
