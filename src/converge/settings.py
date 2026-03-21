"""Repository-local Converge configuration from pyproject and .converge.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        sub = base.get(key)
        if isinstance(value, dict) and isinstance(sub, dict):
            _merge_dict(sub, value)
        else:
            base[key] = value
    return base


@dataclass(frozen=True)
class ConvergeSettings:
    """Effective settings for scanning, diagnosis, and repair."""

    source_roots: tuple[str, ...] = (".",)
    test_roots: tuple[str, ...] = ("tests", "test", "testing")
    ignore_dir_names: tuple[str, ...] = (
        ".git",
        ".venv",
        "venv",
        "env",
        ".tox",
        "node_modules",
        ".mypy_cache",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
    )
    extra_scan_roots: tuple[str, ...] = ()
    scan_workers: int | None = None
    incremental_scan: bool = False
    skip_type_checking_imports: bool = True
    repair_targets: tuple[str, ...] = ("pyproject",)
    requirements_file: str | None = None
    show_file_progress: bool = False

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ConvergeSettings:
        def tup(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
            raw = data.get(key)
            if raw is None:
                return default
            if isinstance(raw, (list, tuple)):
                return tuple(str(x) for x in raw)
            return default

        workers = data.get("scan_workers")
        scan_workers = int(workers) if isinstance(workers, int) else None
        rf = data.get("requirements_file")
        req_file = str(rf) if isinstance(rf, str) and rf.strip() else None

        return cls(
            source_roots=tup("source_roots", (".",)),
            test_roots=tup("test_roots", ("tests", "test", "testing")),
            ignore_dir_names=tup(
                "ignore_dir_names",
                (
                    ".git",
                    ".venv",
                    "venv",
                    "env",
                    ".tox",
                    "node_modules",
                    ".mypy_cache",
                    "__pycache__",
                    ".pytest_cache",
                    "dist",
                    "build",
                ),
            ),
            extra_scan_roots=tup("extra_scan_roots", ()),
            scan_workers=scan_workers,
            incremental_scan=bool(data.get("incremental_scan", False)),
            skip_type_checking_imports=bool(data.get("skip_type_checking_imports", True)),
            repair_targets=tup("repair_targets", ("pyproject",)),
            requirements_file=req_file,
            show_file_progress=bool(data.get("show_file_progress", False)),
        )


def load_converge_settings(root: Path) -> ConvergeSettings:
    """Load [tool.converge] from pyproject.toml merged over .converge.toml (pyproject wins)."""
    merged: dict[str, Any] = {}
    dotfile = root / ".converge.toml"
    if dotfile.is_file():
        with dotfile.open("rb") as handle:
            dot_data = tomllib.load(handle)
        _merge_dict(merged, dot_data)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as handle:
            pp = tomllib.load(handle)
        tool = pp.get("tool", {}).get("converge", {})
        if isinstance(tool, dict):
            _merge_dict(merged, tool)

    return ConvergeSettings.from_mapping(merged)
